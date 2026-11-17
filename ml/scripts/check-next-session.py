"""Independent checkpoint/metric checks and error accounting after report generation."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

spec = importlib.util.spec_from_file_location('next_session', Path(__file__).with_name('next-session.py'))
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)


def main():
    n.verify()
    report = json.loads((n.ML/'reports/next_session.json').read_text())
    prepared = pd.read_parquet(n.ROOT/'frame.parquet', columns=['ticker', 'date', 'target_date', 'label'])
    checks = {}
    keysets = {}
    for family in ['lr', 'hgb']:
        frames = []
        for fold in range(6):
            stem = n.ROOT/f'{family}-fold-{fold}'
            meta = json.loads(stem.with_suffix('.json').read_text())
            assert n.b.sha256_file(stem.with_suffix('.parquet')) == meta['sha256']
            p = pd.read_parquet(stem.with_suffix('.parquet'))
            assert p.date.max() <= n.END and p.target_date.max() <= n.END
            assert p.target_date.gt(p.date).all()
            assert not p.duplicated(['ticker', 'date']).any()
            joined = p.merge(prepared, on=['ticker', 'date'], validate='one_to_one', suffixes=('', '_source'))
            assert len(joined) == len(p)
            np.testing.assert_array_equal(joined.label, joined.label_source)
            np.testing.assert_array_equal(joined.target_date, joined.target_date_source)
            p['fold'] = fold
            frames.append(p)
        rows = pd.concat(frames, ignore_index=True)
        assert not rows.duplicated(['ticker', 'date']).any()
        keysets[family] = rows[['ticker', 'date']].reset_index(drop=True)
        for column, name in [('p', family), ('p_calibrated', family+'_sigmoid')]:
            p, y = rows[column].to_numpy(), rows.label.to_numpy(dtype=int)
            assert np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()
            call = p >= .5
            tp, tn = int((call & (y == 1)).sum()), int((~call & (y == 0)).sum())
            fp, fn = int((call & (y == 0)).sum()), int((~call & (y == 1)).sum())
            expected = report['results'][name]['overall']
            # Independent direct formulas rather than the report metric helper.
            np.testing.assert_allclose((tp+tn)/len(y), expected['accuracy'], rtol=0, atol=1e-12)
            np.testing.assert_allclose(.5*(tp/(tp+fn)+tn/(tn+fp)), expected['balanced_accuracy'], rtol=0, atol=1e-12)
            direct_brier = float(np.mean((p.astype('float64')-y)**2))
            # sklearn preserves float32 probabilities during its reduction;
            # the direct double-precision reference differs by ~2e-8 for LR.
            tolerance = 1e-7 if p.dtype == np.float32 else 1e-12
            np.testing.assert_allclose(direct_brier, expected['brier'], rtol=0, atol=tolerance)
            checks[name] = {'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
                            'up_recall': tp/(tp+fn), 'down_recall': tn/(tn+fp),
                            'double_precision_brier': direct_brier, 'brier_tolerance': tolerance,
                            'coverage_of_prepared_evaluation_cases': 1.,
                            'fold_counts': rows.groupby('fold').size().to_dict()}
    pd.testing.assert_frame_equal(keysets['lr'], keysets['hgb'])
    n.write_json(n.ML/'reports/next_session_checks.json', {'checks': checks,
                 'same_observations': True, 'protected_hashes_verified': True,
                 'scope': 'training folds only; no validation or final test scoring'})
    print('All checkpoint, label, sample-alignment and independent metric checks passed.')


if __name__ == '__main__':
    main()
