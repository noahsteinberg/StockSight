"""Naive baselines, evaluation metrics, block bootstrap and promotion gates.

Implements ml/docs/prediction-contract.md sections 4-5 (ADR-0005) for the 5-session
market-relative target (ADR-0004).

Usage (from ml/):
    python -m stocksight_data.baselines                  # train + validation -> baselines.json
    python -m stocksight_data.baselines --freeze-gates   # also write gates_frozen.json (once)
    python -m stocksight_data.baselines --include-test   # final run only -> baselines_test.json

Models are judged with `gate_model(frame, p_model, load_frozen_gates(...))`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from importlib import metadata

import numpy as np
import pandas as pd

from .config import (
    BASELINES_REPORT,
    BOOTSTRAP_BLOCK_SESSIONS,
    CLEAN_FILE,
    CLEAN_LOG_FILE,
    GATES_FILE,
    LABEL_HORIZON,
    MARKET_BENCHMARK,
    MIN_TICKERS_PER_DATE,
    REPORTS_DIR,
    SPLITS,
    TEST_ACCESS_LOG,
    TEST_REPORT,
)
from .labels import assign_split, label_frame, trailing_excess

BASELINES = ["always_beat", "momentum_5d", "reversal_5d"]
N_BOOT = 1000
SEED = 0


# --------------------------------------------------------------------- metrics
def _hard(p) -> np.ndarray:
    """Probabilities to calls; p >= 0.5 counts as "beats the market"."""
    return (np.asarray(p, dtype=float) >= 0.5).astype(int)


def accuracy(y, p) -> float:
    return float((_hard(p) == np.asarray(y)).mean())


def balanced_accuracy(y, p) -> float:
    """Mean of recall on label-1 rows and recall on label-0 rows (0.5 = no skill).

    NaN if either class is absent, which makes threshold comparisons fail closed.
    """
    y, yhat = np.asarray(y), _hard(p)
    pos = y == 1
    if pos.all() or not pos.any():
        return float("nan")
    return float(0.5 * ((yhat[pos] == 1).mean() + (yhat[~pos] == 0).mean()))


def brier(y, p) -> float:
    return float(np.mean((np.asarray(p, dtype=float) - np.asarray(y)) ** 2))


def confusion(y, p) -> dict[str, int]:
    y, yhat = np.asarray(y), _hard(p)
    return {
        "true_beat": int(((yhat == 1) & (y == 1)).sum()),
        "false_beat": int(((yhat == 1) & (y == 0)).sum()),
        "true_lag": int(((yhat == 0) & (y == 0)).sum()),
        "false_lag": int(((yhat == 0) & (y == 1)).sum()),
    }


# ------------------------------------------------------------------- baselines
def baseline_predictions(past5_excess, majority_class: int) -> dict[str, np.ndarray]:
    """Predicted probability of beating the market for each naive baseline.

    always_beat: the training majority class. momentum_5d: beat if the stock beat the
    market over the last 5 sessions. reversal_5d: beat if it lagged. A trailing excess
    of exactly zero predicts "no beat" for both momentum and reversal.
    """
    past = np.asarray(past5_excess, dtype=float)
    return {
        "always_beat": np.full(len(past), float(majority_class)),
        "momentum_5d": (past > 0).astype(float),
        "reversal_5d": (past < 0).astype(float),
    }


# ------------------------------------------------------------------- bootstrap
def moving_block_indices(n_dates: int, block: int, n_boot: int, rng: np.random.Generator) -> np.ndarray:
    """(n_boot, n_dates) date indices built from contiguous blocks of `block` dates."""
    block = max(1, min(block, n_dates))
    n_blocks = -(-n_dates // block)
    starts = rng.integers(0, n_dates - block + 1, size=(n_boot, n_blocks))
    return (starts[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :n_dates]


def bootstrap_balanced_accuracy_diff(
    dates, y, p_model, p_base, n_boot: int = N_BOOT, seed: int = SEED, block: int = BOOTSTRAP_BLOCK_SESSIONS
):
    """(low, high, point) 95% CI of balanced_accuracy(model) - balanced_accuracy(base).

    Moving-block bootstrap over chronologically sorted dates: contiguous blocks of
    `block` dates are drawn with replacement, and every ticker of a drawn date comes
    with it. Blocks matter because adjacent 5-session labels share 4 return days.
    Raises if any draw is undefined (e.g. contains no positives) instead of dropping it.
    """
    y = np.asarray(y)
    _, codes = np.unique(np.asarray(dates), return_inverse=True)  # sorted, so blocks are contiguous in time
    n_dates = codes.max() + 1

    def per_date(p):
        yhat = _hard(p)
        return (
            np.bincount(codes, weights=(yhat == 1) & (y == 1), minlength=n_dates),
            np.bincount(codes, weights=(yhat == 0) & (y == 0), minlength=n_dates),
        )

    pos = np.bincount(codes, weights=y == 1, minlength=n_dates)
    neg = np.bincount(codes, weights=y == 0, minlength=n_dates)
    tp_m, tn_m = per_date(p_model)
    tp_b, tn_b = per_date(p_base)

    def bal(weights, tp, tn):
        with np.errstate(invalid="ignore", divide="ignore"):
            return 0.5 * (weights @ tp / (weights @ pos) + weights @ tn / (weights @ neg))

    ones = np.ones(n_dates)
    point = float(bal(ones, tp_m, tn_m) - bal(ones, tp_b, tn_b))
    idx = moving_block_indices(n_dates, block, n_boot, np.random.default_rng(seed))
    w = np.stack([np.bincount(row, minlength=n_dates) for row in idx]).astype(float)
    diffs = bal(w, tp_m, tn_m) - bal(w, tp_b, tn_b)
    n_nan = int(np.isnan(diffs).sum())
    if n_nan:
        raise ValueError(f"{n_nan} of {n_boot} bootstrap draws were undefined (a class was missing)")
    low, high = np.percentile(diffs, [2.5, 97.5])
    return float(low), float(high), point


# ----------------------------------------------------------------------- gates
def check_gates(
    *,
    bal_acc: float,
    best_baseline: str,
    best_baseline_bal_acc: float,
    ci_low: float,
    ci_vs: str,
    acc: float,
    always_beat_acc: float,
    brier: float,
    constant_brier: float,
    yearly_bal_acc: dict[int, float],
) -> dict[str, bool]:
    """Promotion gates from the prediction contract, section 5. All must pass.

    The significance gate passes only if the CI was computed against the best baseline
    (`ci_vs == best_baseline`); a CI against any other baseline does not count.
    """
    gates = {
        "beats_best_baseline": bal_acc > best_baseline_bal_acc,
        "significant": ci_vs == best_baseline and ci_low > 0,
        "accuracy_at_least_always_beat": acc >= always_beat_acc,
        "better_than_constant_brier": brier < constant_brier,
        "no_year_below_half": all(v >= 0.5 for v in yearly_bal_acc.values()),
    }
    gates["passed"] = all(gates.values())
    return gates


def gate_model(frame: pd.DataFrame, p_model, gates: dict) -> dict:
    """Judge a model on validation rows using the frozen gate rules.

    `frame` holds validation rows with columns date, label, past5_excess; `p_model` is
    aligned with it. The model and every baseline are scored on the same rows (label,
    past5_excess and p_model all present), and the thresholds are recomputed on those
    rows with the frozen rules (best baseline, majority class, constant probability).
    """
    p_model = np.asarray(p_model, dtype=float)
    if len(p_model) != len(frame):
        raise ValueError("p_model must be aligned with frame")
    keep = (frame["label"].notna() & frame["past5_excess"].notna()).to_numpy() & ~np.isnan(p_model)
    rows, p = frame[keep], p_model[keep]
    y = rows["label"].astype(int).to_numpy()
    base = baseline_predictions(rows["past5_excess"], gates["majority_class"])
    best = gates["best_baseline"]
    constant = np.full(len(y), gates["train_beat_rate"])

    low, high, point = bootstrap_balanced_accuracy_diff(
        rows["date"].to_numpy(), y, p, base[best], n_boot=gates["n_boot"], seed=gates["seed"], block=gates["block"]
    )
    model = {"accuracy": accuracy(y, p), "balanced_accuracy": balanced_accuracy(y, p), "brier": brier(y, p)}
    thresholds = {
        "best_baseline_bal_acc": balanced_accuracy(y, base[best]),
        "always_beat_acc": accuracy(y, base["always_beat"]),
        "constant_brier": brier(y, constant),
    }
    yearly = {
        int(yr): balanced_accuracy(g["label"].astype(int), p[rows.index.get_indexer(g.index)])
        for yr, g in rows.groupby(rows["date"].dt.year)
    }
    result = check_gates(
        bal_acc=model["balanced_accuracy"],
        best_baseline=best,
        best_baseline_bal_acc=thresholds["best_baseline_bal_acc"],
        ci_low=low,
        ci_vs=best,
        acc=model["accuracy"],
        always_beat_acc=thresholds["always_beat_acc"],
        brier=model["brier"],
        constant_brier=thresholds["constant_brier"],
        yearly_bal_acc=yearly,
    )
    return {
        "rows": int(len(rows)),
        "coverage_of_frozen_rows": len(rows) / gates["reference"]["rows"],
        "model": model,
        "thresholds_on_these_rows": thresholds,
        f"model_minus_{best}_bal_acc": {"point": point, "ci95": [low, high]},
        "yearly_bal_acc": yearly,
        "gates": result,
    }


# ------------------------------------------------------------------ evaluation
def evaluate_split(frame: pd.DataFrame, train_beat_rate: float, majority_class: int, thresholds: bool = True) -> dict:
    """Baseline metrics on one split's scorable rows (label and past5_excess present)."""
    y = frame["label"].astype(int).to_numpy()
    preds = baseline_predictions(frame["past5_excess"], majority_class)
    out = {
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()),
        "tickers": int(frame["ticker"].nunique()),
        "beat_rate": float(y.mean()),
        "baselines": {},
    }
    for name in BASELINES:
        out["baselines"][name] = {
            "accuracy": accuracy(y, preds[name]),
            "balanced_accuracy": balanced_accuracy(y, preds[name]),
            "brier": brier(y, preds[name]),
            "confusion": confusion(y, preds[name]),
        }
    constant = np.full(len(y), train_beat_rate)
    out["baselines"]["constant_prob"] = {
        "p": train_beat_rate,
        "accuracy": accuracy(y, constant),
        "balanced_accuracy": balanced_accuracy(y, constant),
        "brier": brier(y, constant),
    }
    naive = {k: out["baselines"][k] for k in BASELINES}
    best = max(naive, key=lambda k: naive[k]["balanced_accuracy"])
    out["best_naive_baseline"] = best

    dates = frame["date"].to_numpy()
    out["vs_always_beat_bal_acc"] = {}
    for name in ["momentum_5d", "reversal_5d"]:
        low, high, point = bootstrap_balanced_accuracy_diff(dates, y, preds[name], preds["always_beat"])
        out["vs_always_beat_bal_acc"][name] = {"point": point, "ci95": [low, high]}
    yearly = frame.assign(y=y, p=preds[best]).groupby(frame["date"].dt.year)
    out["best_baseline_yearly_bal_acc"] = {int(yr): balanced_accuracy(g["y"], g["p"]) for yr, g in yearly}
    if thresholds:
        out["gate_thresholds_for_models"] = {
            "best_baseline_bal_acc": naive[best]["balanced_accuracy"],
            "always_beat_acc": naive["always_beat"]["accuracy"],
            "constant_brier": out["baselines"]["constant_prob"]["brier"],
        }
    return out


def label_diagnostics(frame: pd.DataFrame) -> dict:
    """Per-split label counts (by as_of_date range), purge per boundary, valid tickers per year."""
    per_split = {}
    for name, (start, end) in SPLITS.items():
        lo, hi = pd.Timestamp(start), pd.Timestamp(end)
        in_range = frame["date"].between(lo, hi)
        has_label = frame["status"].isin(["labelled", "tie"])
        purged = in_range & has_label & (frame["split"] != name)
        per_split[name] = {
            "labelled": int((in_range & (frame["split"] == name) & (frame["status"] == "labelled")).sum()),
            "tie": int((in_range & (frame["split"] == name) & (frame["status"] == "tie")).sum()),
            "invalid_window": int((in_range & (frame["status"] == "invalid_window")).sum()),
            "sparse_date": int((in_range & (frame["status"] == "sparse_date")).sum()),
            "purged_at_end": int(purged.sum()),
            "purged_dates": sorted({f"{d:%Y-%m-%d}" for d in frame.loc[purged, "date"]}),
        }
    per_date = frame.groupby("date")["r5"].count()
    by_year = per_date.groupby(per_date.index.year)
    valid_per_year = {
        int(yr): {"min": int(s.min()), "median": float(s.median()), "max": int(s.max())} for yr, s in by_year
    }
    sparse_dates = sorted({f"{d:%Y-%m-%d}" for d in frame.loc[frame["status"] == "sparse_date", "date"]})
    return {"per_split": per_split, "valid_tickers_per_date_by_year": valid_per_year, "sparse_dates": sparse_dates}


def build_eval_frame(prices: pd.DataFrame, min_tickers: int = MIN_TICKERS_PER_DATE) -> pd.DataFrame:
    """Labels, statuses, split and past5_excess for every row of `prices`."""
    frame = label_frame(prices, min_tickers=min_tickers)
    frame["split"] = assign_split(frame)
    past = trailing_excess(prices, min_tickers=min_tickers)
    return frame.merge(past, on=["ticker", "date"], how="left", validate="one_to_one")


def run_baselines(frame: pd.DataFrame, include_test: bool = False) -> dict:
    """Baseline results per split. The test split is evaluated only if include_test."""
    scorable = frame[(frame["status"] == "labelled") & frame["split"].notna() & frame["past5_excess"].notna()]
    train = scorable[scorable["split"] == "train"]
    train_beat_rate = float(train["label"].astype(int).mean())
    majority_class = int(train_beat_rate >= 0.5)
    splits = ["train", "validation"] + (["test"] if include_test else [])
    results = {}
    for s in splits:
        results[s] = evaluate_split(
            scorable[scorable["split"] == s], train_beat_rate, majority_class, thresholds=(s != "test")
        )
        labelled_in_split = int(((frame["split"] == s) & (frame["status"] == "labelled")).sum())
        results[s]["labelled_without_past5_excess"] = labelled_in_split - results[s]["rows"]
    return {"train_beat_rate": train_beat_rate, "majority_class": majority_class, "splits": results}


# ---------------------------------------------------------------- frozen gates
def freeze_gates(baseline_run: dict, dataset_sha256: str, code: dict) -> dict:
    """Gate rules and reference values from the validation baselines."""
    val = baseline_run["splits"]["validation"]
    return {
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_sha256": dataset_sha256,
        "code": code,
        "split": "validation",
        "best_baseline": val["best_naive_baseline"],
        "majority_class": baseline_run["majority_class"],
        "train_beat_rate": baseline_run["train_beat_rate"],
        "n_boot": N_BOOT,
        "seed": SEED,
        "block": BOOTSTRAP_BLOCK_SESSIONS,
        "reference": {"rows": val["rows"], **val["gate_thresholds_for_models"]},
        "rules": [
            "balanced accuracy > best_baseline balanced accuracy on the model's rows",
            "block-bootstrap 95% CI lower bound of (model - best_baseline) balanced accuracy > 0",
            "accuracy >= always_beat accuracy on the model's rows",
            "Brier < constant(train_beat_rate) Brier on the model's rows",
            "every validation year balanced accuracy >= 0.50",
        ],
    }


def load_frozen_gates(path=GATES_FILE, dataset_sha256: str | None = None) -> dict:
    """Load frozen gates; refuse if they were frozen on a different dataset."""
    gates = json.loads(path.read_text())
    if dataset_sha256 is not None and gates["dataset_sha256"] != dataset_sha256:
        raise ValueError(
            f"gates were frozen on dataset {gates['dataset_sha256'][:12]}..., current data is "
            f"{dataset_sha256[:12]}...; results are not comparable"
        )
    return gates


# ------------------------------------------------------------------------- CLI
def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_state() -> dict:
    def run(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True, cwd=CLEAN_FILE.parents[2]).stdout.strip()

    try:
        return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except OSError:
        return {"commit": None, "dirty": None}


def _environment() -> dict:
    versions = {}
    for pkg in ["pandas", "numpy", "pyarrow", "exchange_calendars", "yfinance"]:
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            versions[pkg] = None
    return {"python": platform.python_version(), "packages": versions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--freeze-gates", action="store_true", help="write gates_frozen.json (refuses to overwrite)")
    parser.add_argument("--include-test", action="store_true", help="also evaluate the test split (final run only)")
    args = parser.parse_args()
    if args.freeze_gates and GATES_FILE.exists():
        parser.error(f"{GATES_FILE} already exists; gates are frozen once. Delete it deliberately to re-freeze.")

    prices = pd.read_parquet(CLEAN_FILE, columns=["ticker", "date", "adj_close", "bad_bar"])
    frame = build_eval_frame(prices)
    run = run_baselines(frame, include_test=args.include_test)
    dataset_sha = sha256_file(CLEAN_FILE)
    clean_log = json.loads(CLEAN_LOG_FILE.read_text()) if CLEAN_LOG_FILE.exists() else {}
    code = _git_state()
    header = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "file": str(CLEAN_FILE),
            "sha256": dataset_sha,
            "clean_log_created_at": clean_log.get("created_at"),
            "end_date": clean_log.get("end_date"),
        },
        "code": code,
        "environment": _environment(),
        "target": {
            "horizon_sessions": LABEL_HORIZON,
            "benchmark": MARKET_BENCHMARK,
            "min_tickers_per_date": MIN_TICKERS_PER_DATE,
        },
        "bootstrap": {"n_boot": N_BOOT, "seed": SEED, "cluster": "date", "block_sessions": BOOTSTRAP_BLOCK_SESSIONS},
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    test_result = run["splits"].pop("test", None)
    report = {**header, "labels": label_diagnostics(frame), **run}
    BASELINES_REPORT.write_text(json.dumps(report, indent=2))
    print_report(report)
    print(f"\nReport: {BASELINES_REPORT}")

    if args.freeze_gates:
        GATES_FILE.write_text(json.dumps(freeze_gates(run, dataset_sha, code), indent=2))
        print(f"Gates frozen: {GATES_FILE}")
    if test_result is not None:
        TEST_REPORT.write_text(json.dumps({**header, "split": "test", "result": test_result}, indent=2))
        with open(TEST_ACCESS_LOG, "a") as log:
            log.write(json.dumps({"at": header["created_at"], "dataset_sha256": dataset_sha, "code": code}) + "\n")
        n_access = sum(1 for _ in open(TEST_ACCESS_LOG))
        print(f"Test split evaluated (access #{n_access}): {TEST_REPORT}")


def print_report(report: dict) -> None:
    t, lab = report["target"], report["labels"]
    print(f"Dataset sha256 {report['dataset']['sha256'][:12]}... (clean run {report['dataset']['clean_log_created_at']})")
    print(f"Target: beat the {t['benchmark']} over {t['horizon_sessions']} sessions; min {t['min_tickers_per_date']} tickers/date")
    print(f"Sparse dates dropped: {len(lab['sparse_dates'])} {lab['sparse_dates'][:10]}")
    print("\nLabel counts by as_of_date range:")
    print(f"  {'split':<11}{'labelled':>10}{'tie':>6}{'invalid':>9}{'sparse':>8}{'purged':>8}  purged dates")
    for name, c in lab["per_split"].items():
        dates = f"{c['purged_dates'][0]}..{c['purged_dates'][-1]}" if c["purged_dates"] else "-"
        print(
            f"  {name:<11}{c['labelled']:>10,}{c['tie']:>6}{c['invalid_window']:>9,}{c['sparse_date']:>8,}"
            f"{c['purged_at_end']:>8,}  {dates}"
        )
    print("\nValid tickers per date (min / median) by year:")
    yrs = lab["valid_tickers_per_date_by_year"]
    print("  " + ", ".join(f"{y} {v['min']}/{v['median']:.0f}" for y, v in yrs.items()))
    print(f"\nTrain beat-rate {report['train_beat_rate']:.4f} -> majority class {report['majority_class']}")
    for name, s in report["splits"].items():
        print(
            f"\n[{name}] rows {s['rows']:,} (+{s['labelled_without_past5_excess']:,} labelled without past5_excess), "
            f"dates {s['dates']}, tickers {s['tickers']}, beat-rate {s['beat_rate']:.4f}"
        )
        print(f"  {'baseline':<15}{'accuracy':>10}{'bal. acc':>10}{'brier':>9}")
        for b, m in s["baselines"].items():
            print(f"  {b:<15}{m['accuracy']:>10.4f}{m['balanced_accuracy']:>10.4f}{m['brier']:>9.4f}")
        for b, d in s["vs_always_beat_bal_acc"].items():
            print(
                f"  {b} - always_beat bal. acc: {d['point']:+.4f}, block-bootstrap 95% CI "
                f"[{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}]"
            )
        yearly = ", ".join(f"{y} {v:.3f}" for y, v in s["best_baseline_yearly_bal_acc"].items())
        print(f"  {s['best_naive_baseline']} bal. acc by year: {yearly}")
        if "gate_thresholds_for_models" in s:
            g = s["gate_thresholds_for_models"]
            print(
                f"  a model must beat: bal. acc > {g['best_baseline_bal_acc']:.4f} ({s['best_naive_baseline']}), "
                f"acc >= {g['always_beat_acc']:.4f}, brier < {g['constant_brier']:.4f}"
            )


if __name__ == "__main__":
    main()
