"""Offline diagnostic on saved training-fold predictions. No fitting or downloads.

Run with the pinned environment. --check verifies inputs without running analysis.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))
from stocksight_data import baselines as b  # noqa: E402
from stocksight_data.config import CLEAN_FILE, SPLITS  # noqa: E402
from stocksight_data.labels import assign_split, build_labels, trailing_excess  # noqa: E402

MODEL = "hgb_raw_wide_bal"
COVERAGES = (1., .5, .25, .1)
BINS = (0., .4, .45, .5, .55, .6, 1.)
ROOT = ML.parent
CACHE = ROOT / "data" / "research_round2"
OUTPUT = ROOT / "data" / "confidence-analysis"


def verify_inputs() -> dict:
    report = json.loads((ML / "reports/research_round2.json").read_text())
    manifest = report["manifest"]
    if SPLITS["train"][1] != manifest["train_end"]:
        raise ValueError("Training boundary changed since the saved predictions.")
    if b.sha256_file(CLEAN_FILE) != manifest["dataset_sha256"]:
        raise ValueError("Dataset does not match the saved predictions; do not regenerate it.")
    for fold in range(6):
        stem = CACHE / MODEL / f"fold-{fold}"
        meta = json.loads(stem.with_suffix(".json").read_text())
        if not meta.get("reproduction", {}).get("within_1e_6"):
            raise ValueError(f"Fold {fold} was not a verified baseline reproduction.")
        if b.sha256_file(stem.with_suffix(".parquet")) != meta["predictions_sha256"]:
            raise ValueError(f"Saved predictions changed for fold {fold}.")
    return manifest


def thresholds(predictions: pd.DataFrame, fold: int) -> dict[float, float]:
    earlier = predictions.loc[predictions.fold < fold, "p"].to_numpy()
    if not len(earlier):
        raise ValueError("Cutoffs require an earlier fold.")
    if not np.isfinite(earlier).all() or ((earlier < 0) | (earlier > 1)).any():
        raise ValueError("Invalid probabilities in earlier predictions.")
    margin = np.abs(earlier - .5)
    return {c: (0. if c == 1 else float(np.quantile(margin, 1-c))) for c in COVERAGES}


def metrics(y, p) -> dict:
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    if not len(y):
        return {k: None for k in ("accuracy", "balanced_accuracy", "brier", "mean_probability", "observed_beat_rate", "predicted_beat_share")}
    ba = b.balanced_accuracy(y, p)
    return {"accuracy": b.accuracy(y, p), "balanced_accuracy": float(ba) if np.isfinite(ba) else None,
            "brier": b.brier(y, p), "mean_probability": float(p.mean()),
            "observed_beat_rate": float(y.mean()), "predicted_beat_share": float((p >= .5).mean())}


def daily_stats(rows: pd.DataFrame, selected: np.ndarray) -> np.ndarray:
    """Keep every original date, including dates on which the policy abstains completely."""
    y, p = rows.label.to_numpy(dtype=int), rows.p.to_numpy()
    rev, constant = (rows.past5_excess.to_numpy() < 0).astype(float), rows.base_rate.to_numpy()
    majority = (constant >= .5).astype(float)
    _, date_codes = np.unique(rows.date.to_numpy(), return_inverse=True)
    columns = [np.ones(len(y)), y == 1, y == 0]
    for pred in (p, rev, majority):
        call = pred >= .5
        columns += [call == y, call & (y == 1), ~call & (y == 0)]
    columns += [(p-y)**2, (constant-y)**2]
    return np.column_stack([np.bincount(date_codes, weights=np.asarray(v)*selected) for v in columns])


def interval_statistics(totals: np.ndarray) -> dict:
    """Paired improvements; positive accuracy differences and negative Brier are better."""
    x = np.atleast_2d(totals)
    with np.errstate(divide="ignore", invalid="ignore"):
        ba_model = .5 * (x[:, 4]/x[:, 1] + x[:, 5]/x[:, 2])
        ba_rev = .5 * (x[:, 7]/x[:, 1] + x[:, 8]/x[:, 2])
        ba_majority = .5 * (x[:, 10]/x[:, 1] + x[:, 11]/x[:, 2])
        return {"accuracy_minus_reversal": (x[:, 3]-x[:, 6])/x[:, 0],
                "balanced_accuracy_minus_reversal": ba_model-ba_rev,
                "balanced_accuracy_minus_majority": ba_model-ba_majority,
                "brier_minus_constant": (x[:, 12]-x[:, 13])/x[:, 0]}


def uncertainty(fold_stats: list[np.ndarray], draws: int = 1000) -> dict:
    rng = np.random.default_rng(0)
    totals = np.zeros((draws, 14))
    for daily in fold_stats:
        indices = b.moving_block_indices(len(daily), 10, draws, rng)
        totals += daily[indices].sum(axis=1)
    point = interval_statistics(sum((s.sum(axis=0) for s in fold_stats), np.zeros(14)))
    samples = interval_statistics(totals)
    result = {}
    for name, values in samples.items():
        finite = np.isfinite(values)
        p = float(point[name][0])
        result[name] = {"point": p if np.isfinite(p) else None,
                        "ci95": np.percentile(values, [2.5, 97.5]).tolist() if finite.all() else None,
                        "undefined_draws": int((~finite).sum())}
    return result


def evaluate(predictions: pd.DataFrame, draws: int = 1000) -> dict:
    if predictions.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate stock/date predictions.")
    if not np.isfinite(predictions.p).all() or not predictions.p.between(0, 1).all():
        raise ValueError("Invalid saved probabilities.")
    groups = {int(k): g.copy() for k, g in predictions.groupby("fold", sort=True) if k >= 1}
    if not groups:
        raise ValueError("No later folds to evaluate.")
    policies = []
    for coverage in COVERAGES:
        parts, folds, counts = [], [], []
        for fold, rows in groups.items():
            cutoff = thresholds(predictions, fold)[coverage]
            keep = (np.abs(rows.p.to_numpy()-.5) >= cutoff)
            selected = rows.loc[keep]
            folds.append({"fold": fold, "margin_cutoff": cutoff, "earlier_prediction_rows": int((predictions.fold < fold).sum()),
                          "available_rows": len(rows), "selected_rows": len(selected), "coverage": float(keep.mean()),
                          "metrics": metrics(selected.label, selected.p)})
            counts.append(daily_stats(rows, keep))
            parts.append(selected)
        chosen = pd.concat(parts, ignore_index=True)
        y = chosen.label.to_numpy(dtype=int)
        references = {"reversal_5d": (chosen.past5_excess.to_numpy() < 0).astype(float),
                      "majority": (chosen.base_rate.to_numpy() >= .5).astype(float),
                      "constant_probability": chosen.base_rate.to_numpy()}
        reliability = []
        for i, (lo, hi) in enumerate(zip(BINS[:-1], BINS[1:])):
            g = chosen[(chosen.p >= lo) & ((chosen.p <= hi) if i == len(BINS)-2 else (chosen.p < hi))]
            reliability.append({"probability_range": [lo, hi], "rows": len(g),
                                "mean_probability": float(g.p.mean()) if len(g) else None,
                                "observed_beat_rate": float(g.label.mean()) if len(g) else None})
        policies.append({"requested_coverage": coverage, "rows": len(chosen),
                         "actual_coverage": len(chosen)/sum(len(g) for g in groups.values()),
                         "positive_labels": int(y.sum()), "negative_labels": int((y == 0).sum()),
                         "model": metrics(y, chosen.p), "baselines_on_identical_rows": {k: metrics(y, v) for k, v in references.items()},
                         "paired_uncertainty": uncertainty(counts, draws), "folds": folds, "reliability_bins": reliability})
    return {"model": MODEL, "evaluation_folds": sorted(groups), "policies": policies,
            "protocol": {"cutoff": "Quantile of abs(p-0.5) from earlier folds only; no label-based threshold selection.",
                         "ties": "Include all scores equal to the cutoff; achieved coverage may differ from requested coverage.",
                         "bootstrap": "1000 paired 10-date moving-block draws, stratified within folds; retain zero-answer dates.",
                         "draws": draws, "no_automatic_winner": True, "training": False, "validation_scoring": False, "test_scoring": False},
            "limitations": ["Model margins are not calibrated confidence.", "This diagnostic reuses already-examined training-fold predictions.",
                            "Selective metrics do not satisfy the original all-observation promotion gates.",
                            "Intervals are exploratory and not adjusted for examining multiple coverage policies."]}


def load_predictions() -> pd.DataFrame:
    parts = []
    for fold in range(6):
        stem = CACHE / MODEL / f"fold-{fold}"
        meta = json.loads(stem.with_suffix(".json").read_text())
        frame = pd.read_parquet(stem.with_suffix(".parquet"))
        frame["fold"], frame["base_rate"] = fold, meta["reference_base_rate"]
        parts.append(frame)
    saved = pd.concat(parts, ignore_index=True)
    end = pd.Timestamp(SPLITS["train"][1])
    if not saved.date.le(end).all():
        raise ValueError("Saved predictions extend outside training.")
    prices = pd.read_parquet(CLEAN_FILE, columns=["ticker", "date", "adj_close", "bad_bar"], filters=[("date", "<=", end)])
    logging.info("Reconstructing training-period labels; no validation/test prices are loaded.")
    labels = build_labels(prices)
    labels = labels[(assign_split(labels) == "train") & labels.label.notna()]
    labels = labels[["ticker", "date", "label"]]
    past = trailing_excess(prices)
    joined = saved.merge(labels, on=["ticker", "date"], how="left", validate="one_to_one")
    joined = joined.merge(past, on=["ticker", "date"], how="left", validate="one_to_one")
    if joined[["label", "past5_excess"]].isna().any().any():
        raise ValueError("Saved predictions do not align with valid labels and baseline inputs.")
    return joined


def format_percent(value) -> str:
    return "unavailable" if value is None else f"{100*value:.3f}%"


def write_outputs(result: dict) -> None:
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False, default=str)+"\n", encoding="utf-8")
    lines = ["# Confidence diagnostic", "", "No models were trained. Validation and final test were not scored.", "",
             "Cutoffs came from earlier model scores only. 'Confidence' here means distance from 0.5, not a verified probability of correctness.", "",
             "| Requested answer rate | Actual answer rate | Model accuracy | Model balanced accuracy | Reversal balanced accuracy | Selected cases |",
             "| --- | --- | --- | --- | --- | --- |"]
    for policy in result["policies"]:
        lines.append(f"| {policy['requested_coverage']:.0%} | {policy['actual_coverage']:.2%} | {format_percent(policy['model']['accuracy'])} | "
                     f"{format_percent(policy['model']['balanced_accuracy'])} | {format_percent(policy['baselines_on_identical_rows']['reversal_5d']['balanced_accuracy'])} | {policy['rows']:,} |")
    lines += ["", "## Paired balanced-accuracy change versus reversal", ""]
    for policy in result["policies"]:
        value = policy["paired_uncertainty"]["balanced_accuracy_minus_reversal"]
        interval = value["ci95"]
        ci = "unavailable (undefined bootstrap draws)" if interval is None else f"[{100*interval[0]:+.3f}, {100*interval[1]:+.3f}] percentage points"
        point = "unavailable" if value["point"] is None else f"{100*value['point']:+.3f} percentage points"
        lines.append(f"- Requested {policy['requested_coverage']:.0%}: {point}; 95% interval {ci}.")
    lines += ["", "## What to review", "", "Compare accuracy and balanced accuracy with the fraction of cases answered. Compare every policy with baselines on its own selected cases, not on the full population. Check the per-fold results and reliability bins in results.json. A single attractive row is not a validated operating rule.", "",
              "No policy is automatically selected or promoted. These already-examined training folds support an exploratory diagnostic only. The original promotion gates and final-test reservation are unchanged.", ""]
    (OUTPUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify files and hashes only; do not run the analysis.")
    args = parser.parse_args()
    if args.check:
        verify_inputs()
        print("Ready: matching dataset and all six verified prediction files. Analysis was NOT run.")
        return 0
    OUTPUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(OUTPUT / "run.log", encoding="utf-8"), logging.StreamHandler(sys.stdout)])
    start = time.perf_counter()
    try:
        with threadpool_limits(limits=2):
            manifest = verify_inputs()
            logging.info("Inputs verified. Loading one existing model's predictions.")
            predictions = load_predictions()
            logging.info("Evaluating four fixed answer rates. No training or downloads.")
            result = evaluate(predictions)
            result["provenance"] = {"dataset_sha256": manifest["dataset_sha256"], "source": "Saved round-2 reproduced baseline predictions", "elapsed_s": round(time.perf_counter()-start, 2)}
            write_outputs(result)
        logging.info("Done in %.1f seconds. Share %s and results.json.", time.perf_counter()-start, OUTPUT / "summary.md")
        return 0
    except Exception:
        logging.exception("Analysis stopped. No training fallback will run. Share this run.log to diagnose the error.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
