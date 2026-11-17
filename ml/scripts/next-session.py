"""Train-only, bounded next-session research. From repo root: prepare|run|report.

No downloads, serving artifacts, validation access or final-test scoring.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss
from threadpoolctl import threadpool_limits

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
from stocksight_data import baselines as b, modeling as m
from stocksight_data.config import CLEAN_FILE, FEATURES_FILE
from stocksight_data.features import model_features
from stocksight_data.folds import purged_walk_forward
from stocksight_data.labels import _prepare, _window_return
from stocksight_data.research_round2 import DATA_SHA, protected_hashes, write_json

ROOT = CLEAN_FILE.parents[1] / 'next-session'
END = pd.Timestamp('2018-12-31')
FEATURES = model_features()
NAMES = ['lr', 'lr_sigmoid', 'hgb', 'hgb_sigmoid']


def labels(prices):
    prices = prices.copy()
    prices['bad_bar'] = prices.bad_bar | ~np.isfinite(prices.adj_close) | (prices.adj_close <= 0)
    frame = _prepare(prices)
    frame['forward_return'], frame['target_date'] = _window_return(frame, 1)
    frame['previous_return'], _ = _window_return(frame, -1)
    frame['label'] = np.where(frame.forward_return > 0, 1., np.where(frame.forward_return < 0, 0., np.nan))
    return frame[['ticker', 'date', 'target_date', 'forward_return', 'previous_return', 'label']]


def contract():
    return {'target': 'next_session_adjusted_direction_v1', 'end': str(END.date()),
            'features': FEATURES, 'dataset_sha256': b.sha256_file(CLEAN_FILE),
            'features_sha256': b.sha256_file(FEATURES_FILE),
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'preprocessor_sha256': b.sha256_file(ML/'stocksight_data/modeling.py'),
            'labels_sha256': b.sha256_file(ML/'stocksight_data/labels.py'),
            'python': platform.python_version(),
            'packages': {p: version(p) for p in ['numpy', 'pandas', 'scikit-learn', 'pyarrow']},
            'protected': protected_hashes(), 'seed': 0, 'threads': 2,
            'lr': {'C': 1., 'max_iter': 2000, 'class_weight': None},
            'hgb': {'learning_rate': .05, 'max_iter': 200, 'max_leaf_nodes': 15,
                    'min_samples_leaf': 100, 'l2_regularization': 1., 'early_stopping': False},
            'calibration_sessions': 252, 'configurations': NAMES}


def verify():
    saved = json.loads((ROOT/'manifest.json').read_text())
    if saved != contract():
        raise ValueError('Frozen inputs/source/environment changed; do not mix runs.')
    for key, name in [('frame_sha256', 'frame.parquet'), ('audit_sha256', 'audit.json')]:
        meta = json.loads((ROOT/'prepared.json').read_text())
        if b.sha256_file(ROOT/name) != meta[key]:
            raise ValueError(f'Prepared {name} changed')


def prepare():
    if (ROOT/'manifest.json').exists():
        verify()
        print('Prepared inputs already verified.', flush=True)
        return
    if b.sha256_file(CLEAN_FILE) != DATA_SHA:
        raise ValueError('Snapshot mismatch')
    ROOT.mkdir(parents=True, exist_ok=True)
    prices = pd.read_parquet(CLEAN_FILE, columns=['ticker', 'date', 'adj_close', 'bad_bar'], filters=[('date', '<=', END)])
    lab = labels(prices)
    audit = {'rows': len(lab), 'unchanged': int((lab.forward_return == 0).sum()),
             'invalid_forward': int(lab.forward_return.isna().sum()), 'traces': []}
    # Independent endpoint trace against the actual source, including a boundary.
    examples = pd.concat([lab[lab.label.notna()].groupby('ticker').head(1).head(4),
                          lab[lab.ticker == 'AAPL'].tail(7)])
    for row in examples.itertuples():
        if pd.isna(row.forward_return):
            continue
        own = prices[prices.ticker == row.ticker].set_index('date')
        actual = own.loc[row.target_date, 'adj_close']/own.loc[row.date, 'adj_close']-1
        np.testing.assert_allclose(actual, row.forward_return, rtol=0, atol=1e-12)
        audit['traces'].append({'ticker': row.ticker, 'date': row.date, 'target_date': row.target_date,
                                'independent_return': actual, 'label': row.label})
    features = pd.read_parquet(FEATURES_FILE, columns=['ticker', 'date', *FEATURES], filters=[('date', '<=', END)])
    frame = features.merge(lab, on=['ticker', 'date'], validate='one_to_one')
    frame = frame[frame.label.notna() & frame.previous_return.notna() & frame.target_date.le(END)].copy()
    assert frame.date.max() <= END and frame.target_date.max() <= END
    frame.to_parquet(ROOT/'frame.parquet', index=False)
    audit['eligible_rows'] = len(frame)
    write_json(ROOT/'audit.json', audit)
    write_json(ROOT/'prepared.json', {'frame_sha256': b.sha256_file(ROOT/'frame.parquet'),
                                     'audit_sha256': b.sha256_file(ROOT/'audit.json')})
    write_json(ROOT/'manifest.json', contract())
    print(f'Prepared {len(frame):,} training-only examples; audit saved.', flush=True)


def partition(rows):
    dates = np.sort(rows.date.unique())
    if len(dates) <= 504:
        raise ValueError('Insufficient training history')
    cutoff = pd.Timestamp(dates[-252])
    # Strictly earlier target, not merely an earlier observation.
    base = rows[rows.target_date < cutoff]
    calibration = rows[rows.date >= cutoff]
    assert base.target_date.max() < calibration.date.min()
    return base, calibration


def calibrate(p, y):
    logits = np.log(np.clip(p, 1e-6, 1-1e-6)/np.clip(1-p, 1e-6, 1))[:, None]
    return LogisticRegression(C=1e6, max_iter=1000, random_state=0).fit(logits, y)


def calibrated(model, p):
    p = np.clip(p, 1e-6, 1-1e-6)
    return model.predict_proba(np.log(p/(1-p))[:, None])[:, 1]


def run(pilot=False):
    verify()
    frame = pd.read_parquet(ROOT/'frame.parquet')
    folds = purged_walk_forward(frame)
    for fold in folds[:1] if pilot else folds:
        for family in ['lr', 'hgb']:
            stem = ROOT/f'{family}-fold-{fold["fold"]}'
            if stem.with_suffix('.json').exists():
                meta = json.loads(stem.with_suffix('.json').read_text())
                if b.sha256_file(stem.with_suffix('.parquet')) != meta['sha256']:
                    raise ValueError('Checkpoint changed')
                continue
            started = time.perf_counter()
            base, cal = partition(frame.loc[fold['train_index']])
            ev = frame.loc[fold['eval_index']]
            pre = m.Preprocessor('winsor' if family == 'lr' else 'raw', FEATURES).fit(base)
            est = (LogisticRegression(**contract()['lr'], random_state=0) if family == 'lr' else
                   HistGradientBoostingClassifier(**contract()['hgb'], random_state=0))
            est.fit(pre.transform(base), base.label.astype(int))
            if family == 'lr' and est.n_iter_[0] >= 2000:
                raise RuntimeError('LR did not converge; record failure, do not silently tune')
            p = est.predict_proba(pre.transform(ev))[:, 1]
            mapper = calibrate(est.predict_proba(pre.transform(cal))[:, 1], cal.label.astype(int))
            out = ev[['ticker', 'date', 'target_date', 'label', 'previous_return', 'vol_21d', 'dist_ma_200']].copy()
            out['p'], out['p_calibrated'] = p, calibrated(mapper, p)
            rate = float(base.label.mean())
            out['rate'] = rate
            out['vol_group'] = np.searchsorted(base.vol_21d.quantile([1/3, 2/3]).to_numpy(), out.vol_21d)
            out.loc[out.vol_21d.isna(), 'vol_group'] = -1
            out.to_parquet(stem.with_suffix('.parquet'), index=False)
            write_json(stem.with_suffix('.json'), {'sha256': b.sha256_file(stem.with_suffix('.parquet')),
                        'fold': fold['fold'], 'family': family, 'seconds': time.perf_counter()-started,
                        'fit_rows': len(base), 'calibration_rows': len(cal), 'eval_rows': len(ev),
                        'fit_target_end': base.target_date.max(), 'calibration_start': cal.date.min()})
            print(f'{family} fold {fold["fold"]} complete in {time.perf_counter()-started:.1f}s', flush=True)


def metrics(y, p):
    return {'accuracy': accuracy_score(y, p >= .5),
            'balanced_accuracy': balanced_accuracy_score(y, p >= .5) if len(np.unique(y)) == 2 else None,
            'brier': brier_score_loss(y, p), 'log_loss': log_loss(y, np.clip(p, 1e-6, 1-1e-6), labels=[0, 1]),
            'rows': len(y), 'up_rate': float(np.mean(y))}


def references(rows):
    majority = (rows.rate.to_numpy() >= .5).astype(float)
    prev = rows.previous_return.to_numpy()
    return {'always_up': np.ones(len(rows)), 'majority': majority,
            'momentum': np.where(prev == 0, majority, (prev > 0).astype(float)),
            'reversal': np.where(prev == 0, majority, (prev < 0).astype(float))}


def uncertainty(parts, p_column, block):
    # Counts per date: n,pos,neg, model TP/TN then baseline TP/TN pairs.
    totals = np.zeros((5000, 13))
    rng = np.random.default_rng(0)
    for rows in parts:
        y = rows.label.to_numpy()
        pred = rows[p_column].to_numpy() >= .5
        cols = [np.ones(len(y)), y == 1, y == 0, pred & (y == 1), ~pred & (y == 0)]
        for p in references(rows).values():
            cols += [(p >= .5) & (y == 1), (p < .5) & (y == 0)]
        _, codes = np.unique(rows.date, return_inverse=True)
        daily = np.column_stack([np.bincount(codes, weights=x) for x in cols])
        indices = b.moving_block_indices(len(daily), block, 5000, rng)
        totals += daily[indices].sum(axis=1)
    result = {}
    for i, name in enumerate(references(parts[0])):
        delta = .5*((totals[:, 3]-totals[:, 5+2*i])/totals[:, 1] +
                     (totals[:, 4]-totals[:, 6+2*i])/totals[:, 2])
        assert np.isfinite(delta).all()
        # Four configurations x four baseline contrasts: simultaneous conservative screen.
        result[name] = {'ci95': np.quantile(delta, [.025, .975]).tolist(),
                        'adjusted_lower': float(np.quantile(delta, .025/16))}
    return result


def report():
    verify()
    results = {}
    for family in ['lr', 'hgb']:
        parts = []
        for fold in range(6):
            stem = ROOT/f'{family}-fold-{fold}'
            meta = json.loads(stem.with_suffix('.json').read_text())
            if meta['sha256'] != b.sha256_file(stem.with_suffix('.parquet')):
                raise ValueError('Checkpoint changed')
            part = pd.read_parquet(stem.with_suffix('.parquet'))
            part['fold'] = fold
            parts.append(part)
        rows = pd.concat(parts, ignore_index=True)
        for column, name in [('p', family), ('p_calibrated', family+'_sigmoid')]:
            baseline = {k: metrics(rows.label, p) for k, p in references(rows).items()}
            baseline['constant_probability'] = metrics(rows.label, rows.rate)
            overall = metrics(rows.label, rows[column])
            strong = max(references(rows), key=lambda k: baseline[k]['balanced_accuracy'])
            folds = [metrics(p.label, p[column]) for p in parts]
            intervals = {str(block): uncertainty(parts, column, block) for block in [5, 10, 21]}
            stable = sum(metrics(p.label, p[column])['balanced_accuracy'] >
                         metrics(p.label, references(p)[strong])['balanced_accuracy'] for p in parts)
            promising = (overall['accuracy'] > baseline['majority']['accuracy'] and
                         overall['brier'] <= baseline['constant_probability']['brier'] and stable >= 4 and
                         all(x['adjusted_lower'] > 0 for x in intervals['10'].values()))
            reliability = []
            for lo, hi in zip([0, .4, .45, .5, .55, .6], [.4, .45, .5, .55, .6, 1.000001]):
                g = rows[(rows[column] >= lo) & (rows[column] < hi)]
                reliability.append({'range': [lo, min(hi, 1)], 'rows': len(g),
                                     'mean_p': float(g[column].mean()) if len(g) else None,
                                     'up_rate': float(g.label.mean()) if len(g) else None})
            slices = {}
            for key in ['ticker', 'vol_group']:
                slices[key] = {str(k): {'model': metrics(g.label, g[column]),
                              'baselines': {n: metrics(g.label, p) for n, p in references(g).items()}}
                               for k, g in rows.groupby(key)}
            rows['trend'] = np.where(rows.dist_ma_200.isna(), 'unavailable',
                                     np.where(rows.dist_ma_200 >= 0, 'above_ma200', 'below_ma200'))
            slices['trend'] = {k: {'model': metrics(g.label, g[column]),
                                  'baselines': {n: metrics(g.label, p) for n, p in references(g).items()}}
                               for k, g in rows.groupby('trend')}
            results[name] = {'overall': overall, 'baselines': baseline, 'folds': folds,
                             'intervals': intervals, 'folds_beating_strongest': stable,
                             'promising': promising, 'reliability': reliability, 'diagnostics_only': slices}
    eligible = [k for k in NAMES if results[k]['promising']]
    eligible.sort(key=lambda k: (results[k]['overall']['brier'], -results[k]['overall']['balanced_accuracy'], NAMES.index(k)))
    output = {'results': results, 'candidate_for_review': eligible[0] if eligible else None,
              'validation_scored': False, 'test_scored': False, 'promotion': False,
              'screen': 'Bonferroni across 4 configurations and 4 direction baselines; 5000 date-block draws',
              'audit': json.loads((ROOT/'audit.json').read_text())}
    write_json(ML/'reports/next_session.json', output)
    lines = ['# Next-session direction results', '', 'Training-period walk-forward research only. No validation/test scored.', '',
             '| Configuration | Accuracy | Balanced accuracy | Brier | Promising |', '| --- | --- | --- | --- | --- |']
    for name, value in results.items():
        v = value['overall']
        lines.append(f'| {name} | {v["accuracy"]:.3%} | {v["balanced_accuracy"]:.3%} | {v["brier"]:.6f} | {value["promising"]} |')
    lines += ['', f'Candidate for later review: {output["candidate_for_review"]}. No serving promotion.',
              '', 'Per-stock/group scores are descriptive, not a list of recommended stocks. Current-constituent survivorship and adjusted-data limitations remain.']
    (ML/'docs/NEXT_SESSION_RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'run', 'report'])
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    lock = ROOT/'run.lock'
    # Exclusive owner; retain attempts even after a failed run.
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(descriptor)
    status = 'interrupted'
    try:
        with threadpool_limits(limits=2):
            if args.stage == 'prepare': prepare()
            elif args.stage == 'run': run(args.pilot)
            else: report()
        status = 'completed'
    except Exception:
        status = traceback.format_exc()
        raise
    finally:
        with (ROOT/'attempts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stage': args.stage, 'pilot': args.pilot, 'status': status})+'\n')
        lock.unlink()


if __name__ == '__main__':
    main()
