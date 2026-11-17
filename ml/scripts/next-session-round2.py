"""Bounded next-session round 2: market context, recency, and tree families.

Stages: prepare, run [--pilot], report. Training-period folds only. This module
never downloads data, scores validation/final test, exports a model, or changes
the application.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss, roc_auc_score
from threadpoolctl import threadpool_limits

ML = Path(__file__).resolve().parents[1]
REPO = ML.parent
sys.path.insert(0, str(ML))

from stocksight_data import baselines as b, modeling as m  # noqa: E402
from stocksight_data.config import CLEAN_FILE, FEATURES_FILE, MIN_TICKERS_PER_DATE  # noqa: E402
from stocksight_data.features import model_features  # noqa: E402
from stocksight_data.folds import purged_walk_forward  # noqa: E402
from stocksight_data.research_round2 import DATA_SHA, protected_hashes, write_json  # noqa: E402

END = pd.Timestamp("2018-12-31")
OUTPUT = Path(os.environ.get("STOCKSIGHT_EXPERIMENT_DIR", REPO / "data" / "next-session-round2"))
PRIOR = Path(os.environ.get("STOCKSIGHT_PRIOR_NEXT_DIR", CLEAN_FILE.parents[1] / "next-session"))
BASE_FEATURES = tuple(model_features())
MARKET_FEATURES = (
    "mkt_ret_1d",
    "mkt_ret_5d",
    "mkt_ret_21d",
    "mkt_vol_21d",
    "breadth_1d",
    "breadth_5d",
    "xs_dispersion_21d",
)
ALL_FEATURES = (*BASE_FEATURES, *MARKET_FEATURES)
REFERENCE = "hgb_reference"
PACKAGES = ("numpy", "pandas", "pyarrow", "scikit-learn", "scipy")


@dataclass(frozen=True)
class Configuration:
    name: str
    family: str
    window_years: int | None
    params: dict


def configurations() -> tuple[Configuration, ...]:
    standard = {
        "learning_rate": 0.05,
        "max_iter": 200,
        "max_leaf_nodes": 15,
        "min_samples_leaf": 100,
        "l2_regularization": 1.0,
        "early_stopping": False,
    }
    deep = {
        "learning_rate": 0.03,
        "max_iter": 400,
        "max_leaf_nodes": 31,
        "min_samples_leaf": 250,
        "l2_regularization": 2.0,
        "max_features": 0.8,
        "early_stopping": False,
    }
    forest = {
        "n_estimators": 300,
        "criterion": "log_loss",
        "max_depth": 10,
        "min_samples_leaf": 500,
        "max_features": "sqrt",
        "n_jobs": 2,
    }
    return (
        Configuration("hgb_market_expanding", "hgb", None, standard),
        Configuration("hgb_market_10y", "hgb", 10, standard),
        Configuration("hgb_deep_market_10y", "hgb", 10, deep),
        Configuration("rf_market_10y", "rf", 10, {**forest, "max_samples": 0.2}),
        Configuration("extra_market_10y", "extra", 10, forest),
    )


def source_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def prior_metadata() -> tuple[dict, dict]:
    manifest = json.loads((PRIOR / "manifest.json").read_text())
    prepared = json.loads((PRIOR / "prepared.json").read_text())
    if manifest["dataset_sha256"] != DATA_SHA:
        raise ValueError("Prior next-session experiment used a different dataset.")
    if b.sha256_file(PRIOR / "frame.parquet") != prepared["frame_sha256"]:
        raise ValueError("Prior prepared frame changed.")
    for fold in range(6):
        stem = PRIOR / f"hgb-fold-{fold}"
        meta = json.loads(stem.with_suffix(".json").read_text())
        if b.sha256_file(stem.with_suffix(".parquet")) != meta["sha256"]:
            raise ValueError(f"Prior reference predictions changed for fold {fold}.")
    return manifest, prepared


def contract() -> dict:
    prior, prepared = prior_metadata()
    if b.sha256_file(CLEAN_FILE) != DATA_SHA:
        raise ValueError("Dataset does not match the frozen snapshot.")
    return {
        "target": "next_session_adjusted_direction_v1",
        "development_end": str(END.date()),
        "dataset_sha256": DATA_SHA,
        "features_sha256": b.sha256_file(FEATURES_FILE),
        "prior_frame_sha256": prepared["frame_sha256"],
        "prior_source_sha256": prior["source_sha256"],
        "source_sha256": source_hash(),
        "environment": {"python": platform.python_version(), **{p: version(p) for p in PACKAGES}},
        "base_features": list(BASE_FEATURES),
        "market_features": list(MARKET_FEATURES),
        "configurations": [asdict(c) for c in configurations()],
        "reference": REFERENCE,
        "calibration_holdout_sessions_preserved_for_comparability": 252,
        "scoring_folds": list(range(6)),
        "threads": 2,
        "seed": 0,
        "minimum_cross_section": MIN_TICKERS_PER_DATE,
        "bootstrap": {"draws": 5000, "primary_block_sessions": 10, "sensitivity": [5, 21]},
        "protected_files": protected_hashes(),
        "no_validation_or_test_scoring": True,
    }


def derive_market_context(features: pd.DataFrame, minimum: int = MIN_TICKERS_PER_DATE) -> pd.DataFrame:
    """One row/date, calculated before label eligibility is joined."""
    required = {"date", "ret_1d", "ret_5d", "mkt_ret_21d", "mkt_vol_21d", "xs_dispersion_21d"}
    missing = required - set(features)
    if missing:
        raise ValueError(f"Missing context inputs: {sorted(missing)}")
    work = features[list(required)].copy()
    work["date"] = pd.to_datetime(work.date).astype("datetime64[ns]").dt.normalize()
    by_date = work.groupby("date", sort=True)
    out = pd.DataFrame(index=by_date.size().index)
    for horizon in (1, 5):
        source = work[f"ret_{horizon}d"]
        count = source.groupby(work.date).count()
        out[f"n_ret_{horizon}d"] = count
        out[f"mkt_ret_{horizon}d"] = source.groupby(work.date).mean().where(count >= minimum)
        breadth = source.gt(0).where(source.notna()).groupby(work.date).mean()
        out[f"breadth_{horizon}d"] = breadth.where(count >= minimum)
    for column in ("mkt_ret_21d", "mkt_vol_21d", "xs_dispersion_21d"):
        if by_date[column].nunique(dropna=True).gt(1).any():
            raise ValueError(f"{column} is not constant within date")
        out[column] = by_date[column].first()
    return out.reset_index()


def verify() -> None:
    frozen = json.loads((OUTPUT / "manifest.json").read_text())
    if frozen != contract():
        raise ValueError("Frozen source, data, environment, or configurations changed.")
    prepared = json.loads((OUTPUT / "prepared.json").read_text())
    for key, filename in (("context_sha256", "market_context.parquet"), ("audit_sha256", "audit.json")):
        if b.sha256_file(OUTPUT / filename) != prepared[key]:
            raise ValueError(f"Prepared {filename} changed.")


def prepare() -> None:
    if (OUTPUT / "manifest.json").exists():
        verify()
        print("Prepared inputs already verified.", flush=True)
        return
    OUTPUT.mkdir(parents=True, exist_ok=True)
    columns = ["date", "ret_1d", "ret_5d", "mkt_ret_21d", "mkt_vol_21d", "xs_dispersion_21d"]
    feature_rows = pd.read_parquet(FEATURES_FILE, columns=columns, filters=[("date", "<=", END)])
    context = derive_market_context(feature_rows)
    prior = pd.read_parquet(PRIOR / "frame.parquet", columns=["ticker", "date", "target_date", "label"])
    before = len(prior)
    joined = prior.merge(context, on="date", how="left", validate="many_to_one")
    if len(joined) != before or not joined.target_date.le(END).all():
        raise ValueError("Context join changed prior eligibility or crossed development end.")
    context.to_parquet(OUTPUT / "market_context.parquet", index=False)
    sample_dates = [pd.Timestamp(x) for x in ("2006-12-29", "2012-12-31", "2018-12-28")]
    traces = []
    for date in sample_dates:
        source = feature_rows[feature_rows.date == date]
        actual = context[context.date == date].iloc[0]
        for horizon in (1, 5):
            valid = source[f"ret_{horizon}d"].dropna()
            # Source returns are float32; groupby reduction order can differ by ~1e-10.
            np.testing.assert_allclose(actual[f"mkt_ret_{horizon}d"], valid.mean(), rtol=0, atol=1e-8)
            np.testing.assert_allclose(actual[f"breadth_{horizon}d"], valid.gt(0).mean(), rtol=0, atol=1e-12)
        traces.append({"date": date, "rows_before_labels": len(source),
                       "n_ret_1d": actual.n_ret_1d, "n_ret_5d": actual.n_ret_5d,
                       **{column: actual[column] for column in MARKET_FEATURES}})
    audit = {
        "feature_rows_before_label_join": len(feature_rows),
        "prior_eligible_rows": before,
        "joined_eligible_rows": len(joined),
        "dates": len(context),
        "traces": traces,
        "validation_scored": False,
        "test_scored": False,
    }
    write_json(OUTPUT / "audit.json", audit)
    write_json(OUTPUT / "prepared.json", {
        "context_sha256": b.sha256_file(OUTPUT / "market_context.parquet"),
        "audit_sha256": b.sha256_file(OUTPUT / "audit.json"),
    })
    write_json(OUTPUT / "manifest.json", contract())
    print(f"Prepared {len(context):,} date contexts for {before:,} common examples.", flush=True)


def load_frame() -> pd.DataFrame:
    verify()
    frame = pd.read_parquet(PRIOR / "frame.parquet")
    context = pd.read_parquet(OUTPUT / "market_context.parquet")
    joined = frame.merge(context[["date", *MARKET_FEATURES]], on="date", how="left", validate="many_to_one")
    if len(joined) != len(frame) or not joined.target_date.le(END).all():
        raise ValueError("Common evaluation frame changed.")
    return joined


def fit_partition(rows: pd.DataFrame, years: int | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = np.sort(rows.date.unique())
    if len(dates) <= 504:
        raise ValueError("Insufficient chronological history.")
    calibration_start = pd.Timestamp(dates[-252])
    base = rows[rows.target_date < calibration_start]
    calibration = rows[rows.date >= calibration_start]
    if years is not None:
        start = base.date.max() - pd.DateOffset(years=years)
        base = base[base.date > start]
    if base.target_date.max() >= calibration.date.min():
        raise ValueError("Training target crosses the preserved holdout boundary.")
    return base, calibration


def estimator(config: Configuration):
    params = {**config.params, "random_state": 0}
    if config.family == "hgb":
        return HistGradientBoostingClassifier(**params)
    if config.family == "rf":
        return RandomForestClassifier(**params)
    if config.family == "extra":
        return ExtraTreesClassifier(**params)
    raise ValueError(config.family)


def run(pilot: bool = False) -> None:
    frame = load_frame()
    folds = purged_walk_forward(frame)
    selected_folds = folds[:1] if pilot else folds
    for fold in selected_folds:
        for config in configurations():
            stem = OUTPUT / config.name / f"fold-{fold['fold']}"
            if stem.with_suffix(".json").exists():
                meta = json.loads(stem.with_suffix(".json").read_text())
                if b.sha256_file(stem.with_suffix(".parquet")) != meta["predictions_sha256"]:
                    raise ValueError(f"Checkpoint changed: {config.name} fold {fold['fold']}")
                continue
            started = time.perf_counter()
            base, calibration = fit_partition(frame.loc[fold["train_index"]], config.window_years)
            evaluation = frame.loc[fold["eval_index"]]
            model = estimator(config)
            model.fit(base[list(ALL_FEATURES)], base.label.astype(int))
            probabilities = model.predict_proba(evaluation[list(ALL_FEATURES)])[:, 1]
            out = evaluation[["ticker", "date", "target_date", "label", "previous_return"]].copy()
            out["p"] = probabilities.astype("float32")
            out["rate"] = float(base.label.mean())
            stem.parent.mkdir(parents=True, exist_ok=True)
            out.to_parquet(stem.with_suffix(".parquet"), index=False)
            elapsed = time.perf_counter() - started
            write_json(stem.with_suffix(".json"), {
                "configuration": config.name,
                "fold": fold["fold"],
                "seconds": elapsed,
                "fit_rows": len(base),
                "fit_dates": base.date.nunique(),
                "fit_start": base.date.min(),
                "fit_target_end": base.target_date.max(),
                "preserved_holdout_rows": len(calibration),
                "evaluation_rows": len(evaluation),
                "predictions_sha256": b.sha256_file(stem.with_suffix(".parquet")),
            })
            print(f"{config.name} fold {fold['fold']} complete in {elapsed:.1f}s", flush=True)


def metrics(rows: pd.DataFrame, p) -> dict:
    y = rows.label.to_numpy(dtype=int)
    p = np.asarray(p, dtype=float)
    call = p >= 0.5
    return {
        "rows": len(y),
        "accuracy": accuracy_score(y, call),
        "balanced_accuracy": balanced_accuracy_score(y, call),
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6), labels=[0, 1]),
        "auc": roc_auc_score(y, p),
        "mean_daily_auc": m.per_date_auc(rows.date, y, p),
        "up_rate": float(y.mean()),
        "predicted_up_share": float(call.mean()),
    }


def references(rows: pd.DataFrame) -> dict[str, np.ndarray]:
    rate = rows.rate.to_numpy(dtype=float)
    majority = (rate >= 0.5).astype(float)
    previous = rows.previous_return.to_numpy(dtype=float)
    return {
        "always_up": np.ones(len(rows)),
        "majority": majority,
        "momentum": np.where(previous == 0, majority, (previous > 0).astype(float)),
        "reversal": np.where(previous == 0, majority, (previous < 0).astype(float)),
        "constant_probability": rate,
    }


def reference_parts() -> list[pd.DataFrame]:
    parts = []
    for fold in range(6):
        stem = PRIOR / f"hgb-fold-{fold}"
        meta = json.loads(stem.with_suffix(".json").read_text())
        if b.sha256_file(stem.with_suffix(".parquet")) != meta["sha256"]:
            raise ValueError("Reference checkpoint changed.")
        part = pd.read_parquet(stem.with_suffix(".parquet"))
        part["fold"] = fold
        parts.append(part)
    return parts


def candidate_parts(name: str) -> list[pd.DataFrame]:
    parts = []
    for fold in range(6):
        stem = OUTPUT / name / f"fold-{fold}"
        meta = json.loads(stem.with_suffix(".json").read_text())
        if b.sha256_file(stem.with_suffix(".parquet")) != meta["predictions_sha256"]:
            raise ValueError(f"Candidate checkpoint changed: {name} fold {fold}")
        part = pd.read_parquet(stem.with_suffix(".parquet"))
        part["fold"] = fold
        parts.append(part)
    return parts


def uncertainty(candidate: list[pd.DataFrame], reference: list[pd.DataFrame], block: int) -> dict:
    rng = np.random.default_rng(0)
    totals = np.zeros((5000, 15))
    point = np.zeros(15)
    for current, baseline in zip(candidate, reference, strict=True):
        merged = current.merge(baseline[["ticker", "date", "p"]], on=["ticker", "date"],
                               validate="one_to_one", suffixes=("", "_reference"))
        y = merged.label.to_numpy(dtype=int)
        cand = merged.p.to_numpy() >= 0.5
        ref = merged.p_reference.to_numpy() >= 0.5
        rev = merged.previous_return.to_numpy() < 0
        const = merged.rate.to_numpy(dtype=float)
        _, date_codes = np.unique(merged.date, return_inverse=True)
        columns = [np.ones(len(y)), y == 1, y == 0]
        for call in (cand, ref, rev):
            columns += [call == y, call & (y == 1), ~call & (y == 0)]
        columns += [(merged.p.to_numpy() - y) ** 2,
                    (merged.p_reference.to_numpy() - y) ** 2,
                    (const - y) ** 2]
        daily = np.column_stack([np.bincount(date_codes, weights=np.asarray(x)) for x in columns])
        indices = b.moving_block_indices(len(daily), block, 5000, rng)
        totals += daily[indices].sum(axis=1)
        point += daily.sum(axis=0)

    def contrasts(x):
        x = np.atleast_2d(x)
        ba_cand = 0.5 * (x[:, 4] / x[:, 1] + x[:, 5] / x[:, 2])
        ba_ref = 0.5 * (x[:, 7] / x[:, 1] + x[:, 8] / x[:, 2])
        ba_rev = 0.5 * (x[:, 10] / x[:, 1] + x[:, 11] / x[:, 2])
        return {
            "balanced_accuracy_minus_reference": ba_cand - ba_ref,
            "balanced_accuracy_minus_reversal": ba_cand - ba_rev,
            "accuracy_minus_reference": (x[:, 3] - x[:, 6]) / x[:, 0],
            "brier_minus_reference": (x[:, 12] - x[:, 13]) / x[:, 0],
            "brier_minus_constant": (x[:, 12] - x[:, 14]) / x[:, 0],
        }

    samples = contrasts(totals)
    points = contrasts(point)
    result = {}
    for name, values in samples.items():
        result[name] = {
            "point": float(points[name][0]),
            "ci95": np.quantile(values, [0.025, 0.975]).tolist(),
            "multiplicity_adjusted_lower": float(np.quantile(values, 0.025 / 10)) if "balanced" in name else None,
        }
    return result


def selective(rows: pd.DataFrame) -> dict:
    mask = (rows.p <= 0.4) | (rows.p >= 0.6)
    selected = rows[mask]
    return {
        "rule": "p<=0.4 or p>=0.6, fixed before round-2 fitting",
        "coverage": float(mask.mean()),
        "metrics": metrics(selected, selected.p) if len(selected) else None,
    }


def report() -> None:
    verify()
    reference = reference_parts()
    reference_all = pd.concat(reference, ignore_index=True)
    baseline_metrics = {name: metrics(reference_all, values) for name, values in references(reference_all).items()}
    results = {
        REFERENCE: {
            "overall": metrics(reference_all, reference_all.p),
            "folds": [metrics(x, x.p) for x in reference],
            "selective": selective(reference_all),
        }
    }
    for config in configurations():
        parts = candidate_parts(config.name)
        rows = pd.concat(parts, ignore_index=True)
        strongest = "reversal"
        intervals = {str(block): uncertainty(parts, reference, block) for block in (5, 10, 21)}
        fold_metrics = [metrics(x, x.p) for x in parts]
        folds_beating_reversal = sum(
            metrics(x, x.p)["balanced_accuracy"] > metrics(x, references(x)[strongest])["balanced_accuracy"]
            for x in parts
        )
        overall = metrics(rows, rows.p)
        primary = intervals["10"]
        qualifies = (
            overall["balanced_accuracy"] - baseline_metrics["reversal"]["balanced_accuracy"] >= 0.005
            and primary["balanced_accuracy_minus_reversal"]["multiplicity_adjusted_lower"] > 0
            and primary["balanced_accuracy_minus_reference"]["multiplicity_adjusted_lower"] > 0
            and overall["accuracy"] > baseline_metrics["always_up"]["accuracy"]
            and overall["brier"] < baseline_metrics["constant_probability"]["brier"]
            and folds_beating_reversal >= 4
        )
        results[config.name] = {
            "configuration": asdict(config),
            "overall": overall,
            "folds": fold_metrics,
            "folds_beating_reversal": folds_beating_reversal,
            "uncertainty": intervals,
            "selective": selective(rows),
            "qualifies_for_later_review": qualifies,
        }
    qualified = [c.name for c in configurations() if results[c.name]["qualifies_for_later_review"]]
    qualified.sort(key=lambda name: (results[name]["overall"]["brier"],
                                     -results[name]["overall"]["balanced_accuracy"]))
    output = {
        "baseline_metrics": baseline_metrics,
        "results": results,
        "candidate_for_later_review": qualified[0] if qualified else None,
        "selection_rule": ">=0.5pp BA over reversal; adjusted positive BA contrasts vs reversal/reference; accuracy, Brier, and 4/6-fold gates",
        "validation_scored": False,
        "test_scored": False,
        "promotion": False,
        "audit": json.loads((OUTPUT / "audit.json").read_text()),
    }
    write_json(ML / "reports" / "next_session_round2.json", output)
    lines = [
        "# Next-session round 2 results",
        "",
        "Training-period walk-forward research only. Validation/final test were not scored.",
        "",
        "| Configuration | Accuracy | Balanced accuracy | AUC | Brier | Later review? |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, value in results.items():
        score = value["overall"]
        lines.append(f"| {name} | {score['accuracy']:.3%} | {score['balanced_accuracy']:.3%} | "
                     f"{score['auc']:.3%} | {score['brier']:.6f} | "
                     f"{value.get('qualifies_for_later_review', False)} |")
    lines += ["", f"Candidate for later review: {output['candidate_for_later_review']}.", "",
              "The fixed extreme-probability diagnostic is exploratory and cannot select a model."]
    (ML / "docs" / "NEXT_SESSION_ROUND2_RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run", "report"))
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    lock = OUTPUT / "run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another run may own {lock}") from exc
    os.close(descriptor)
    status = "interrupted"
    try:
        with threadpool_limits(limits=2):
            if args.stage == "prepare":
                prepare()
            elif args.stage == "run":
                run(args.pilot)
            else:
                report()
        status = "completed"
        return 0
    except Exception:
        status = traceback.format_exc()
        raise
    finally:
        with (OUTPUT / "attempts.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"stage": args.stage, "pilot": args.pilot, "status": status}) + "\n")
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
