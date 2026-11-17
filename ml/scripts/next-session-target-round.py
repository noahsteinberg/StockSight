"""Fixed, train-only continuous-target discovery. No serving or protected scoring."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
SPEC = importlib.util.spec_from_file_location("target_round_helpers", ML / "scripts/next-session-round2.py")
helpers = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helpers
SPEC.loader.exec_module(helpers)
b = helpers.b
write_json = helpers.write_json
OUTPUT = Path(os.environ.get("STOCKSIGHT_TARGET_DIR", ML.parent / "data/next-session-target-round"))
NAMES = ("absolute_return_hgb", "excess_return_hgb", "combined_market_stock")
PARAMS = dict(learning_rate=0.05, max_iter=200, max_leaf_nodes=15,
              min_samples_leaf=100, l2_regularization=1.0, early_stopping=False,
              loss="squared_error", random_state=0)
PERCENTILES = (0.5, 99.5)


def contract():
    prior, prepared = helpers.prior_metadata()
    if b.sha256_file(helpers.CLEAN_FILE) != helpers.DATA_SHA:
        raise ValueError("Frozen cleaned snapshot changed")
    sources = [Path(__file__), ML / "scripts/next-session-round2.py",
               *sorted((ML / "stocksight_data").glob("*.py"))]
    return {
        "target": "continuous_next_session_target_discovery_v1",
        "development_end": "2018-12-31", "dataset_sha256": helpers.DATA_SHA,
        "features_sha256": b.sha256_file(helpers.FEATURES_FILE),
        "prior_frame_sha256": prepared["frame_sha256"],
        "prior_source_sha256": prior["source_sha256"],
        "sources": {str(p.relative_to(ML)): b.sha256_file(p) for p in sources},
        "environment": {"python": platform.python_version(), **{p: version(p) for p in helpers.PACKAGES}},
        "stock_features": list(helpers.BASE_FEATURES), "market_features": list(helpers.MARKET_FEATURES),
        "configurations": list(NAMES), "hgb": PARAMS, "ridge_alpha": 1.0,
        "target_clip_percentiles": list(PERCENTILES), "calibration_sessions": 252,
        "probability_mapping": "score standardization and logistic C=1 on calibration block only",
        "market_target": "equal-weight prior-frame eligible stocks grouped by observation AND target session; minimum 150",
        "bootstrap": {"draws": 5000, "blocks": [5, 10, 21], "primary": 10, "seed": 0},
        "protected": helpers.protected_hashes(), "threads": 2,
        "validation_scored": False, "test_scored": False, "promotion": False,
    }


def market_targets(frame, minimum=150):
    """Eligible stock set is fixed before fitting; future returns are targets only."""
    keys = ["date", "target_date"]
    if frame.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate stock/date")
    if frame.groupby("date").target_date.nunique().gt(1).any():
        raise ValueError("A date contains mismatched target sessions")
    if (frame.target_date <= frame.date).any():
        raise ValueError("Target must follow observation")
    grouped = frame.groupby(keys, sort=True)
    market = grouped.agg(market_return=("forward_return", "mean"),
                         market_previous=("previous_return", "mean"),
                         market_count=("forward_return", "count")).reset_index()
    market.loc[market.market_count < minimum, ["market_return", "market_previous"]] = np.nan
    return market


def assert_training_only(frame):
    if frame.empty or frame[["date", "target_date"]].isna().any().any():
        raise ValueError("Missing training dates")
    if frame.date.max() > helpers.END or frame.target_date.max() > helpers.END:
        raise ValueError("Protected-period row rejected")
    if not np.isfinite(frame.forward_return).all():
        raise ValueError("Nonfinite target")


def prepare():
    if (OUTPUT / "manifest.json").exists():
        verify()
        print("Prepared inputs verified", flush=True)
        return
    frozen = contract()
    frame = pd.read_parquet(helpers.PRIOR / "frame.parquet")
    assert_training_only(frame)
    market = market_targets(frame)
    frame = frame.merge(market, on=["date", "target_date"], validate="many_to_one")
    # Fail rather than silently drop dates and change the archived comparison sample.
    if frame.market_return.isna().any():
        raise ValueError("Sparse eligible universe; review instead of changing common observations")
    columns = ["date", "ret_1d", "ret_5d", "mkt_ret_21d", "mkt_vol_21d", "xs_dispersion_21d"]
    features = pd.read_parquet(helpers.FEATURES_FILE, columns=columns, filters=[("date", "<=", helpers.END)])
    context = helpers.derive_market_context(features)
    frame = frame.merge(context[["date", *helpers.MARKET_FEATURES]], on="date", validate="many_to_one")
    frame["excess_return"] = frame.forward_return - frame.market_return
    for fold in helpers.purged_walk_forward(frame):
        ev = frame.loc[fold["eval_index"]]
        train = frame.loc[fold["train_index"]]
        if train.target_date.max() >= ev.date.min():
            raise ValueError("Outer fold target crosses evaluation boundary")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(OUTPUT / "frame.parquet", index=False)
    write_json(OUTPUT / "prepared.json", {"frame_sha256": b.sha256_file(OUTPUT / "frame.parquet"),
               "rows": len(frame), "dates": frame.date.nunique(),
               "market_count_min": int(frame.market_count.min()),
               "market_reconstruction_max_error": float(np.abs(frame.excess_return + frame.market_return - frame.forward_return).max())})
    write_json(OUTPUT / "manifest.json", frozen)
    print(f"Prepared {len(frame):,} common training-only rows", flush=True)


def verify():
    if json.loads((OUTPUT / "manifest.json").read_text()) != contract():
        raise ValueError("Source, data, environment or protocol changed; do not mix runs")
    meta = json.loads((OUTPUT / "prepared.json").read_text())
    if b.sha256_file(OUTPUT / "frame.parquet") != meta["frame_sha256"]:
        raise ValueError("Prepared targets changed")


def clip_target(y):
    bounds = np.percentile(np.asarray(y), PERCENTILES)
    return np.clip(y, *bounds), bounds.tolist()


def fit_mapper(score, label):
    """The calibration block alone learns all probability-mapping parameters."""
    if len(np.unique(label)) != 2 or not np.isfinite(score).all():
        raise ValueError("Calibration requires finite scores and both classes")
    mapper = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000, random_state=0))
    mapper.fit(np.asarray(score).reshape(-1, 1), label)
    if mapper[-1].n_iter_[0] >= 1000:
        raise ValueError("Probability mapping did not converge")
    return mapper


def checkpoint(fold):
    stem = OUTPUT / f"fold-{fold}"
    if not stem.with_suffix(".json").exists():
        return None
    meta = json.loads(stem.with_suffix(".json").read_text())
    if meta["fold"] != fold or b.sha256_file(stem.with_suffix(".parquet")) != meta["sha256"]:
        raise ValueError(f"Checkpoint {fold} changed")
    return meta


def log_attempt(**entry):
    with (OUTPUT / "attempts.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **entry}) + "\n")


def run(pilot=False):
    verify()
    frame = pd.read_parquet(OUTPUT / "frame.parquet")
    assert_training_only(frame)
    folds = helpers.purged_walk_forward(frame)
    for fold in folds[:1] if pilot else folds:
        number = fold["fold"]
        if checkpoint(number):
            print(f"Fold {number}: verified checkpoint; skipped", flush=True)
            continue
        started = time.perf_counter()
        base, cal = helpers.fit_partition(frame.loc[fold["train_index"]], None)
        ev = frame.loc[fold["eval_index"]]
        if cal.target_date.max() >= ev.date.min():
            raise ValueError("Calibration crosses outer boundary")
        out = ev[["ticker", "date", "target_date", "label", "forward_return", "previous_return",
                  "market_return", "market_previous", "excess_return"]].copy()
        out["rate"] = float(base.label.mean())
        scores_cal = {}
        fit_details = {}
        for name, target in zip(NAMES[:2], ("forward_return", "excess_return"), strict=True):
            log_attempt(stage="fit", fold=number, configuration=name, status="started")
            fit_start = time.perf_counter()
            y, bounds = clip_target(base[target])
            model = HistGradientBoostingRegressor(**PARAMS)
            model.fit(base[list(helpers.BASE_FEATURES)].to_numpy(dtype="float32"), y)
            scores_cal[name] = model.predict(cal[list(helpers.BASE_FEATURES)].to_numpy(dtype="float32"))
            out[name] = model.predict(ev[list(helpers.BASE_FEATURES)].to_numpy(dtype="float32"))
            fit_details[name] = {"clip_bounds": bounds, "seconds": time.perf_counter() - fit_start}
            del model
            log_attempt(stage="fit", fold=number, configuration=name, status="completed", **fit_details[name])
            print(f"{name} fold {number} fitted in {fit_details[name]['seconds']:.1f}s", flush=True)
        # One market training row per date: no stock-count weighting of Ridge.
        market_fit = base.drop_duplicates("date").sort_values("date")
        ridge_y, ridge_bounds = clip_target(market_fit.market_return)
        ridge = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(), Ridge(alpha=1.0))
        ridge.fit(market_fit[list(helpers.MARKET_FEATURES)], ridge_y)
        out["market_score"] = ridge.predict(ev[list(helpers.MARKET_FEATURES)])
        out[NAMES[2]] = out[NAMES[1]] + out.market_score
        scores_cal[NAMES[2]] = scores_cal[NAMES[1]] + ridge.predict(cal[list(helpers.MARKET_FEATURES)])
        mappings = {}
        for name in NAMES:
            # Excess-return probability has relative semantics. Never call it P(up).
            labels = (cal.excess_return > 0).astype(int) if name == NAMES[1] else cal.label.astype(int)
            mapper = fit_mapper(scores_cal[name], labels)
            out[f"p_{name}"] = mapper.predict_proba(out[[name]].to_numpy())[:, 1]
            mappings[name] = {"mean": float(mapper[0].mean_[0]), "scale": float(mapper[0].scale_[0]),
                              "coefficient": float(mapper[1].coef_[0, 0]), "intercept": float(mapper[1].intercept_[0])}
        out["relative_rate"] = float((base.excess_return > 0).mean())
        if not np.isfinite(out[[*NAMES, *[f"p_{n}" for n in NAMES]]]).all().all():
            raise ValueError("Nonfinite predictions")
        stem = OUTPUT / f"fold-{number}"
        temporary = stem.with_suffix(".parquet.tmp")
        out.to_parquet(temporary, index=False)
        temporary.replace(stem.with_suffix(".parquet"))
        write_json(stem.with_suffix(".json"), {
            "fold": number, "sha256": b.sha256_file(stem.with_suffix(".parquet")),
            "seconds": time.perf_counter() - started, "fit_rows": len(base), "fit_dates": base.date.nunique(),
            "fit_target_end": base.target_date.max(), "calibration_start": cal.date.min(),
            "calibration_target_end": cal.target_date.max(), "calibration_sessions": cal.date.nunique(),
            "evaluation_start": ev.date.min(), "evaluation_rows": len(ev), "models": fit_details,
            "ridge_fit_dates": len(market_fit), "ridge_clip_bounds": ridge_bounds,
            "probability_mappings": mappings,
        })
        print(f"Fold {number} complete: 3 outputs, 2 HGB fits, {time.perf_counter()-started:.1f}s", flush=True)


def daily_rank(rows, name):
    result = []
    for date, group in rows.groupby("date", sort=True):
        score = group[name]
        actual = group.forward_return
        count = max(1, len(group) // 10)
        # Stable tie-break for reproducibility; constant scores have no ranking evidence.
        order = group.sort_values([name, "ticker"])
        varying = score.nunique() > 1 and actual.nunique() > 1
        ic = score.rank().corr(actual.rank()) if varying else np.nan
        spread = order.forward_return.iloc[-count:].mean() - order.forward_return.iloc[:count].mean() if varying else np.nan
        result.append({"date": date, "ic": ic, "spread": spread})
    return pd.DataFrame(result)


def metrics(rows, name):
    relative = name == NAMES[1]
    y = (rows.excess_return > 0).to_numpy(int) if relative else rows.label.to_numpy(int)
    score = rows[name].to_numpy()
    p = rows[f"p_{name}"].to_numpy()
    rank = daily_rank(rows, name)
    return {"rows": len(rows), "direction_target": "relative" if relative else "absolute",
            "accuracy": float(accuracy_score(y, score > 0)),
            "balanced_accuracy": float(balanced_accuracy_score(y, score > 0)),
            "auc": float(roc_auc_score(y, score)) if len(np.unique(y)) == 2 else None,
            "brier_diagnostic_calibrated": float(brier_score_loss(y, p)),
            "predicted_positive_share": float((score > 0).mean()), "coverage": 1.0,
            "mean_daily_spearman_rank_ic": float(rank.ic.mean()) if rank.ic.notna().any() else None,
            "mean_daily_decile_spread": float(rank.spread.mean()) if rank.spread.notna().any() else None,
            "rank_dates": int(rank.ic.notna().sum())}


def daily_statistics(rows, name):
    relative = name == NAMES[1]
    y = (rows.excess_return > 0).to_numpy(int) if relative else rows.label.to_numpy(int)
    call = rows[name].to_numpy() > 0
    previous = rows.previous_return.to_numpy() - (rows.market_previous.to_numpy() if relative else 0)
    rate = rows.relative_rate.to_numpy() if relative else rows.rate.to_numpy()
    reversal = np.where(previous == 0, rate >= 0.5, previous < 0)
    reference = rows.reference_p.to_numpy() >= 0.5
    _, codes = np.unique(rows.date, return_inverse=True)
    columns = [np.ones(len(y)), y == 1, y == 0, call == y, call & (y == 1), ~call & (y == 0),
               reversal == y, reversal & (y == 1), ~reversal & (y == 0),
               reference == y, reference & (y == 1), ~reference & (y == 0),
               (rows[f"p_{name}"].to_numpy() - y) ** 2, (rate - y) ** 2,
               y == 1, (rows.reference_p.to_numpy() - y) ** 2]
    daily = np.column_stack([np.bincount(codes, weights=np.asarray(x)) for x in columns])
    rank = daily_rank(rows, name)
    return np.column_stack([daily, rank.ic.fillna(0), rank.ic.notna(), rank.spread.fillna(0), rank.spread.notna()])


def contrasts(x, relative=False):
    x = np.atleast_2d(x)
    ba = 0.5 * (x[:, 4] / x[:, 1] + x[:, 5] / x[:, 2])
    rev = 0.5 * (x[:, 7] / x[:, 1] + x[:, 8] / x[:, 2])
    result = {"balanced_accuracy_minus_reversal": ba - rev,
              "accuracy_minus_always_positive": (x[:, 3] - x[:, 14]) / x[:, 0],
              "brier_minus_fit_rate": (x[:, 12] - x[:, 13]) / x[:, 0],
              "mean_daily_spearman_rank_ic": np.divide(x[:, 16], x[:, 17], out=np.zeros(len(x)), where=x[:, 17] > 0),
              "mean_daily_decile_spread": np.divide(x[:, 18], x[:, 19], out=np.zeros(len(x)), where=x[:, 19] > 0)}
    if not relative:
        result["balanced_accuracy_minus_hgb_reference"] = ba - 0.5 * (x[:, 10] / x[:, 1] + x[:, 11] / x[:, 2])
        result["brier_minus_hgb_reference"] = (x[:, 12] - x[:, 15]) / x[:, 0]
    return result


def uncertainty(daily_parts, relative, block, draws=5000):
    rng = np.random.default_rng(0)
    totals = np.zeros((draws, 20))
    point = np.zeros(20)
    for daily in daily_parts:
        indices = b.moving_block_indices(len(daily), block, draws, rng)
        # Chunk to avoid a several-GB (draws x dates x statistics) allocation.
        for start in range(0, draws, 100):
            totals[start:start+100] += daily[indices[start:start+100]].sum(axis=1)
        point += daily.sum(axis=0)
    observed = contrasts(point, relative)
    return {key: {"point": float(observed[key][0]), "ci95": np.quantile(value, [0.025, 0.975]).tolist(),
                  "adjusted_lower": float(np.quantile(value, 0.025 / 6))}
            for key, value in contrasts(totals, relative).items()}


def report(pilot=False):
    verify()
    parts = []
    numbers = range(1) if pilot else range(6)
    for number in numbers:
        if not checkpoint(number):
            raise ValueError(f"Missing fold {number}; full report requires all six folds")
        rows = pd.read_parquet(OUTPUT / f"fold-{number}.parquet")
        stem = helpers.PRIOR / f"hgb-fold-{number}"
        reference = pd.read_parquet(stem.with_suffix(".parquet"), columns=["ticker", "date", "target_date", "label", "p"])
        joined = rows.merge(reference, on=["ticker", "date", "target_date", "label"], validate="one_to_one", suffixes=("", "_reference"))
        if len(joined) != len(rows) or len(joined) != len(reference):
            raise ValueError("Archived reference and new evaluation keys differ")
        joined["reference_p"] = joined.p
        parts.append(joined)
    all_rows = pd.concat(parts, ignore_index=True)
    results = {}
    for name in NAMES:
        print(f"Reporting {name}", flush=True)
        fold_metrics = [metrics(p, name) for p in parts]
        daily = [daily_statistics(p, name) for p in parts]
        intervals = {} if pilot else {str(block): uncertainty(daily, name == NAMES[1], block) for block in (5, 10, 21)}
        relative = name == NAMES[1]
        baselines = []
        for part in parts:
            y = (part.excess_return > 0).to_numpy(int) if relative else part.label.to_numpy(int)
            rate = part.relative_rate.to_numpy() if relative else part.rate.to_numpy()
            prev = part.previous_return.to_numpy() - (part.market_previous.to_numpy() if relative else 0)
            reversal = np.where(prev == 0, rate >= 0.5, prev < 0)
            baselines.append({"always_positive_accuracy": float(y.mean()),
                              "reversal_balanced_accuracy": float(balanced_accuracy_score(y, reversal)),
                              "fit_rate_brier": float(brier_score_loss(y, rate)),
                              "hgb_reference_balanced_accuracy": None if relative else float(balanced_accuracy_score(y, part.reference_p >= 0.5))})
        wins = sum(m["balanced_accuracy"] > base["reversal_balanced_accuracy"] for m, base in zip(fold_metrics, baselines, strict=True))
        rank_positive = sum(m["mean_daily_spearman_rank_ic"] is not None and m["mean_daily_spearman_rank_ic"] > 0 for m in fold_metrics)
        flags = {}
        if not pilot:
            primary = intervals["10"]
            flags["direction_for_later_review"] = (not relative and
                primary["balanced_accuracy_minus_reversal"]["point"] >= 0.005 and
                primary["balanced_accuracy_minus_reversal"]["adjusted_lower"] > 0 and
                primary["balanced_accuracy_minus_hgb_reference"]["adjusted_lower"] > 0 and
                primary["accuracy_minus_always_positive"]["point"] > 0 and
                primary["brier_minus_fit_rate"]["point"] < 0 and wins >= 4)
            flags["ranking_hypothesis_for_later_review"] = (rank_positive >= 4 and
                all(m["mean_daily_spearman_rank_ic"] is not None and m["mean_daily_spearman_rank_ic"] > 0 for m in fold_metrics[-2:]) and
                all(intervals[str(block)][key]["adjusted_lower"] > 0
                    for block in (5, 10, 21) for key in ("mean_daily_spearman_rank_ic", "mean_daily_decile_spread")))
        results[name] = {"overall": metrics(all_rows, name), "folds": fold_metrics,
                         "baseline_folds": baselines, "folds_beating_reversal": wins,
                         "positive_rank_ic_folds": rank_positive, "review_flags": flags,
                         "uncertainty": intervals, "promotion": False}
    reference_rank_rows = all_rows[["ticker", "date", "forward_return", "reference_p", "previous_return"]].copy()
    reference_rank_rows["reference_score"] = all_rows.reference_p
    reference_rank_rows["reversal_score"] = -all_rows.previous_return
    rank_baselines = {}
    for baseline in ("reference_score", "reversal_score"):
        ranks = daily_rank(reference_rank_rows, baseline)
        rank_baselines[baseline] = {
            "mean_daily_spearman_rank_ic": float(ranks.ic.mean()) if ranks.ic.notna().any() else None,
            "mean_daily_decile_spread": float(ranks.spread.mean()) if ranks.spread.notna().any() else None,
            "rank_dates": int(ranks.ic.notna().sum()),
        }
    output = {"pilot_only": pilot, "completed_folds": len(parts), "results": results,
              "ranking_baselines": rank_baselines,
              "validation_scored": False, "test_scored": False, "promotion": False,
              "decision": "Human review required; target discovery never promotes a serving model",
              "protocol": json.loads((OUTPUT / "manifest.json").read_text())}
    title = "pilot" if pilot else "results"
    write_json(OUTPUT / f"{title}.json", output)
    lines = ["# Next-session continuous-target round" + (" pilot" if pilot else ""), "",
             "Training-period research only. Diagnostic probabilities are not deployable confidence.", "",
             "| Configuration | Direction target | Accuracy | Balanced accuracy | AUC | Brier | Rank IC | Decile spread |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, result in results.items():
        m = result["overall"]
        lines.append(f"| {name} | {m['direction_target']} | {m['accuracy']:.3%} | {m['balanced_accuracy']:.3%} | "
                     f"{m['auc']:.5f} | {m['brier_diagnostic_calibrated']:.6f} | {m['mean_daily_spearman_rank_ic']} | {m['mean_daily_decile_spread']} |")
    lines += ["", "Direction uses raw score > 0; Brier uses calibration-block-only logistic mapping.",
              "Excess-return direction means outperform, not price up. Ranking uses realized absolute return, whose within-date ordering equals excess return.",
              "Decile spread is gross/descriptive, not an executable trading return. All outcomes are unclipped.",
              "No validation/final-test scoring, model export, or promotion. Review every fold and block interval before deciding next steps."]
    (OUTPUT / f"{title}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not pilot:
        write_json(ML / "reports/next_session_target_round.json", output)
        (ML / "docs/NEXT_SESSION_TARGET_ROUND_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run", "report"))
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    lock = OUTPUT / "run.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "stage": args.stage}))
    status = "interrupted"
    try:
        log_attempt(stage=args.stage, pilot=args.pilot, status="started")
        with threadpool_limits(limits=2):
            if args.stage == "prepare":
                prepare()
            elif args.stage == "run":
                run(args.pilot)
            else:
                report(args.pilot)
        status = "completed"
    except Exception:
        status = traceback.format_exc()
        raise
    finally:
        log_attempt(stage=args.stage, pilot=args.pilot, status=status)
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
