"""Train-only feature report: coverage, distributions, redundancy and univariate signal.

Usage (from ml/):  python -m stocksight_data.feature_report   (after `python -m stocksight_data.features`)

Anything that looks at outcomes uses the TRAIN split only (contract 3.5: selection
happens inside train). Validation appears only as a coverage count (share of labelled
rows with a value); its labels are never read here.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .baselines import moving_block_indices, sha256_file
from .config import (
    BOOTSTRAP_BLOCK_SESSIONS,
    CLEAN_FILE,
    FEATURE_REPORT,
    FEATURES_FILE,
    MIN_TICKERS_PER_DATE,
    REPORTS_DIR,
    SPLITS,
)
from .features import FEATURES
from .labels import assign_split, label_frame

MIN_TICKERS_FOR_IC = 30
CORR_SAMPLE = 300_000
REDUNDANT_ABS_RHO = 0.9


def daily_rank_ic(frame: pd.DataFrame, feature: str, target: str = "excess_ret") -> pd.Series:
    """Spearman correlation between a feature and the target across tickers, per date."""
    d = frame[["date", feature, target]].dropna()
    by_date = d.groupby("date")
    rx = by_date[feature].rank()
    ry = by_date[target].rank()
    rx = rx - rx.groupby(d["date"]).transform("mean")
    ry = ry - ry.groupby(d["date"]).transform("mean")
    num = (rx * ry).groupby(d["date"]).sum()
    den = np.sqrt((rx**2).groupby(d["date"]).sum() * (ry**2).groupby(d["date"]).sum())
    n = by_date.size()
    return (num / den).where((n >= MIN_TICKERS_FOR_IC) & (den > 0)).dropna()


def block_ci_of_mean(series: pd.Series, block: int = BOOTSTRAP_BLOCK_SESSIONS, n_boot: int = 1000, seed: int = 0):
    """(low, high, se): 95% moving-block bootstrap CI and standard error of the mean of a date-ordered series."""
    values = series.sort_index().to_numpy()
    idx = moving_block_indices(len(values), block, n_boot, np.random.default_rng(seed))
    means = values[idx].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high), float(means.std(ddof=1))


def benjamini_hochberg(pvalues: dict[str, float], q: float = 0.05) -> dict[str, bool]:
    """Which hypotheses survive Benjamini-Hochberg false-discovery control at level q."""
    names = sorted(pvalues, key=pvalues.get)
    m = len(names)
    passed_rank = 0
    for k, name in enumerate(names, start=1):
        if pvalues[name] <= q * k / m:
            passed_rank = k
    return {name: (i < passed_rank) for i, name in enumerate(names)}


def train_label_frame(prices: pd.DataFrame, min_tickers: int = MIN_TICKERS_PER_DATE) -> pd.DataFrame:
    """Labelled TRAIN rows only, computed from prices cut at the train end date.

    Validation and test outcomes are never computed: the price data they would need
    is not passed in. (The 5-session purge makes train labels end by the train end.)
    """
    train_end = pd.Timestamp(SPLITS["train"][1])
    labels = label_frame(prices[prices["date"] <= train_end], min_tickers=min_tickers)
    labels["split"] = assign_split(labels)
    keep = (labels["split"] == "train") & (labels["status"] == "labelled")
    return labels.loc[keep, ["ticker", "date", "excess_ret"]].reset_index(drop=True)


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    prices = pd.read_parquet(CLEAN_FILE, columns=["ticker", "date", "adj_close", "bad_bar"])
    feats = pd.read_parquet(FEATURES_FILE)
    names = list(FEATURES)
    train = train_label_frame(prices).merge(feats, on=["ticker", "date"], how="left", validate="one_to_one")

    val_lo, val_hi = (pd.Timestamp(d) for d in SPLITS["validation"])
    val_rows = feats[feats["date"].between(val_lo, val_hi)]  # features only, no labels
    coverage = {
        "train_labelled_rows": {n: float(train[n].notna().mean()) for n in names},
        "validation_all_rows": {n: float(val_rows[n].notna().mean()) for n in names},
    }

    stats = {}
    for n in names:
        s = train[n].dropna()
        stats[n] = {
            "mean": float(s.mean()),
            "std": float(s.std()),
            "p01": float(s.quantile(0.01)),
            "p50": float(s.median()),
            "p99": float(s.quantile(0.99)),
            "share_beyond_10_sd": float(((s - s.mean()).abs() > 10 * s.std()).mean()),
        }

    sample = train[names].sample(min(CORR_SAMPLE, len(train)), random_state=0)
    rho = sample.rank().corr()
    pairs = [
        {"a": a, "b": b, "spearman": round(float(rho.loc[a, b]), 3)}
        for i, a in enumerate(names)
        for b in names[i + 1 :]
        if abs(rho.loc[a, b]) >= REDUNDANT_ABS_RHO
    ]

    signal = {}
    pvalues = {}
    for n in names:
        if FEATURES[n].scope == "market":
            signal[n] = {"note": "constant across tickers on a date; no cross-sectional IC"}
            continue
        ic = daily_rank_ic(train, n)
        low, high, se = block_ci_of_mean(ic)
        pvalues[n] = math.erfc(abs(ic.mean() / se) / math.sqrt(2))  # two-sided, normal approximation
        early, late = ic[ic.index.year <= 2009], ic[ic.index.year >= 2010]
        signal[n] = {
            "mean_ic": float(ic.mean()),
            "ci95": [low, high],
            "p_value": pvalues[n],
            "significant_unadjusted": bool(low > 0 or high < 0),
            "caveat": FEATURES[n].caveat,
            "ic_2000_2009": float(early.mean()),
            "ic_2010_2018": float(late.mean()),
            "same_sign_both_halves": bool(np.sign(early.mean()) == np.sign(late.mean())),
            "share_dates_positive": float((ic > 0).mean()),
            "dates": int(len(ic)),
        }

    survives = benjamini_hochberg(pvalues)
    for n, ok in survives.items():
        signal[n]["significant_bh_fdr05"] = ok

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_sha256": sha256_file(CLEAN_FILE),
        "features_sha256": sha256_file(FEATURES_FILE),
        "scope": "train split only for stats, correlations and IC (labels computed from prices <= train end); validation only as feature coverage, no labels",
        "ic_definition": "per-date Spearman(feature, excess_ret) over labelled train rows, dates with >= 30 tickers; "
        f"CI = moving-block bootstrap of the mean, block {BOOTSTRAP_BLOCK_SESSIONS}",
        "features": {n: {"family": FEATURES[n].family, "scope": FEATURES[n].scope, "lookback": FEATURES[n].lookback,
                         "hypothesis": FEATURES[n].hypothesis} for n in names},
        "coverage": coverage,
        "train_stats": stats,
        "redundant_pairs": pairs,
        "train_signal": signal,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FEATURE_REPORT.write_text(json.dumps(report, indent=2))

    ranked = sorted(
        (n for n in names if "mean_ic" in signal[n]), key=lambda n: abs(signal[n]["mean_ic"]), reverse=True
    )
    print(f"Train-only univariate signal (per-date rank IC vs excess return), {len(train):,} train rows; * = BH FDR 5%")
    print(f"  {'feature':<20}{'mean IC':>9}{'95% CI':>20}{'00-09':>8}{'10-18':>8}{'cov tr':>8}{'cov va':>8}")
    for n in ranked:
        s = signal[n]
        star = "*" if s["significant_bh_fdr05"] else " "
        flip = "" if s["same_sign_both_halves"] else "  sign flips"
        print(
            f"  {n:<20}{s['mean_ic']:>+9.4f}{star} [{s['ci95'][0]:+.4f}, {s['ci95'][1]:+.4f}]"
            f"{s['ic_2000_2009']:>+8.4f}{s['ic_2010_2018']:>+8.4f}"
            f"{coverage['train_labelled_rows'][n]:>8.3f}{coverage['validation_all_rows'][n]:>8.3f}{flip}"
            + ("  [survivorship]" if s["caveat"] else "")
        )
    print(f"\nRedundant pairs (|Spearman| >= {REDUNDANT_ABS_RHO}): {len(pairs)}")
    for p in pairs:
        print(f"  {p['a']} ~ {p['b']}: {p['spearman']:+.3f}")
    heavy = {n: s["share_beyond_10_sd"] for n, s in stats.items() if s["share_beyond_10_sd"] > 1e-4}
    print(f"\nHeavy tails (share beyond 10 sd > 0.01%): {json.dumps({k: round(v, 5) for k, v in heavy.items()})}")
    print(f"\nReport: {FEATURE_REPORT}")


if __name__ == "__main__":
    main()
