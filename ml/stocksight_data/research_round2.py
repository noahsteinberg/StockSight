"""Bounded, resumable, train-only follow-up to commit 589d6c5.

From ml/: python -m stocksight_data.research_round2 prepare|audit|run|report
No command in this module scores validation or test, calls judge, or saves a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import time
import traceback
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from . import baselines as b
from . import modeling as m
from .config import CLEAN_FILE, FEATURES_FILE, MIN_TICKERS_PER_DATE, REPO_ROOT, SPLITS
from .features import Feature, build_features, model_features
from .folds import purged_walk_forward
from .labels import assign_split, build_labels, label_frame, trailing_excess
from .trading_calendar import sessions_between

BASE_COMMIT = "589d6c53197e33664f8fa00a801a6117a974192c"
DATA_SHA = "ee0b2ed66c8abb87e0cf36798a32258bc902c0e1687ddee2a485c80b44216e89"
ROOT = CLEAN_FILE.parents[1] / "research_round2"
TRACKED = Path(__file__).resolve().parents[1] / "reports"
CONTEXT = "xs_ret_skew_21d"
EXPERIMENT_FEATURES = {
    CONTEXT: Feature(21, "market", "market", "Trailing-return cross-sectional skew may explain changes in the date-level beat rate."),
}
SMALL_FEATURES = (
    "ex_ret_1d", "ex_ret_5d", "ex_ret_21d", "mom_12_1", "vol_21d", "vol_ratio_21_63",
    "close_loc_1d", "gap_1d", "dist_ma_10", "dist_ma_200", "rsi_14", "volu_ratio_1_21",
)
BASE_NAME = "hgb_raw_wide_bal"
BASE_SPEC = next(s for s in m.candidate_specs() if s.name == BASE_NAME)
PACKAGES = ("numpy", "pandas", "pyarrow", "scikit-learn", "scipy", "exchange_calendars")
PROTECTED = (
    "ml/reports/gates_frozen.json", "ml/reports/model_selection.json",
    "ml/reports/model_validation.json", "ml/reports/validation_access_log.jsonl",
    "data/reports/gates_frozen.json", "data/reports/model_selection.json",
    "data/reports/validation_access_log.jsonl",
)


@dataclass(frozen=True)
class Experiment:
    name: str
    features: tuple[str, ...]
    years: int | None = None


def configurations() -> tuple[Experiment, ...]:
    default = tuple(model_features())
    return (
        Experiment(BASE_NAME, default),
        Experiment("compact_12", SMALL_FEATURES),
        Experiment("trailing_5_years", default, 5),
        Experiment("trailing_10_years", default, 10),
        Experiment("context_skew_21d", (*default, CONTEXT)),
    )


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def source_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def protected_hashes() -> dict:
    return {name: b.sha256_file(REPO_ROOT / name) if (REPO_ROOT / name).exists() else None for name in PROTECTED}


def manifest_value() -> dict:
    if b.sha256_file(CLEAN_FILE) != DATA_SHA:
        raise ValueError("Dataset does not match the frozen snapshot; do not rebuild or re-freeze silently.")
    if not FEATURES_FILE.exists():
        raise FileNotFoundError("Run prepare first to rebuild the existing features.")
    return {
        "base_commit": BASE_COMMIT, "dataset_sha256": DATA_SHA,
        "features_sha256": b.sha256_file(FEATURES_FILE), "source_sha256": source_hash(),
        "environment": {"python": platform.python_version(), **{p: version(p) for p in PACKAGES}},
        "configurations": [asdict(c) for c in configurations()], "base_spec": BASE_SPEC.to_dict(),
        "scoring_folds": [1, 2, 3, 4, 5], "train_end": SPLITS["train"][1],
        "protected_files": protected_hashes(), "bootstrap": {"block_sessions": 10, "draws": 1000, "seed": 0},
    }


def check_manifest() -> dict:
    saved = json.loads((ROOT / "manifest.json").read_text())
    current = json.loads(json.dumps(manifest_value()))
    if saved != current:
        changed = [k for k in current if current[k] != saved.get(k)]
        raise ValueError(f"Research inputs changed ({changed}); preserve this run and explicitly start a new round.")
    return saved


@contextmanager
def run_lock():
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / "run.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another run owns {path}; inspect its PID before removing a stale lock.") from exc
    with os.fdopen(descriptor, "w") as output:
        output.write(str(os.getpid()))
    try:
        yield
    finally:
        path.unlink()


def training_prices() -> pd.DataFrame:
    # Filtering happens at the parquet reader: no validation/test prices reach label construction.
    return pd.read_parquet(CLEAN_FILE, filters=[("date", "<=", pd.Timestamp(SPLITS["train"][1]))])


def market_context(feats: pd.DataFrame, min_tickers: int = MIN_TICKERS_PER_DATE) -> pd.Series:
    """Unbiased sample skew across valid trailing returns on date t, before any label join.

    Invalid per-stock returns are already NaN under the original 21-session clean-window rule.
    A market-level statistic can still be available for a stock with an invalid own window.
    """
    if feats.duplicated(["ticker", "date"]).any():
        raise ValueError("Duplicate stock/date changes the cross-sectional population.")
    if min_tickers < 3:
        raise ValueError("Skew needs at least three observations.")
    group = feats.groupby("date")["ret_21d"]
    values = group.skew().where(group.count() >= min_tickers).replace([np.inf, -np.inf], np.nan)
    return feats["date"].map(values).astype("float32").rename(CONTEXT)


def load_training_frame() -> pd.DataFrame:
    hi = pd.Timestamp(SPLITS["train"][1])
    columns = ["ticker", "date", *model_features()]
    feats = pd.read_parquet(FEATURES_FILE, columns=columns, filters=[("date", "<=", hi)])
    feats[CONTEXT] = market_context(feats)
    prices = pd.read_parquet(CLEAN_FILE, columns=["ticker", "date", "adj_close", "bad_bar"],
                             filters=[("date", "<=", hi)])
    labels = build_labels(prices)
    labels = labels[(assign_split(labels) == "train") & labels.label.notna()]
    labels = labels[["ticker", "date", "target_date", "label", "excess_ret"]]
    past = trailing_excess(prices)
    out = labels.merge(past, on=["ticker", "date"], how="left", validate="one_to_one")
    out = out.merge(feats, on=["ticker", "date"], how="left", validate="one_to_one")
    out["label"] = out["label"].astype("int8")
    return out.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)


def experiment_frame(frame: pd.DataFrame, config: Experiment) -> pd.DataFrame:
    metadata = ["ticker", "date", "target_date", "label", "excess_ret", "past5_excess"]
    return frame[[*metadata, *config.features]]


def window_folds(frame: pd.DataFrame, years: int | None) -> list[dict]:
    folds = purged_walk_forward(frame)
    for fold in folds:
        if years is not None:
            cutoff = fold["fit_end"] - pd.DateOffset(years=years)
            idx = fold["train_index"]
            fold["train_index"] = idx[frame.loc[idx, "date"] > cutoff]
    return folds


def common_eval_index(frame: pd.DataFrame, fold: dict) -> pd.Index:
    rows = frame.loc[fold["eval_index"]]
    return rows.index[rows["past5_excess"].notna() & rows[CONTEXT].notna()]


def append_attempt(value: dict) -> None:
    TRACKED.mkdir(exist_ok=True)
    with (TRACKED / "research_round2_attempts.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps({"at": now(), **value}, allow_nan=False) + "\n")


def require_reproduced_baseline() -> None:
    for fold in range(6):
        path = ROOT / BASE_NAME / f"fold-{fold}.json"
        if not path.exists() or not json.loads(path.read_text()).get("reproduction", {}).get("within_1e_6"):
            raise RuntimeError("Finish and verify all six baseline folds before new configurations.")


def prepare() -> None:
    if b.sha256_file(CLEAN_FILE) != DATA_SHA:
        raise ValueError("Wrong dataset snapshot.")
    if not FEATURES_FILE.exists():
        start = time.perf_counter()
        feats = build_features(pd.read_parquet(CLEAN_FILE))
        FEATURES_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FEATURES_FILE.with_suffix(".parquet.tmp")
        feats.to_parquet(tmp, index=False)
        tmp.replace(FEATURES_FILE)
        print(f"Features rebuilt: {len(feats):,} rows, {time.perf_counter()-start:.1f}s", flush=True)
    candidate = json.loads(json.dumps(manifest_value()))
    path = ROOT / "manifest.json"
    if path.exists():
        check_manifest()
    else:
        write_json(path, candidate)
    print(f"Prepared immutable inputs: {path}", flush=True)


def audit() -> dict:
    check_manifest()
    prices = training_prices()
    labels = label_frame(prices)
    features = pd.read_parquet(FEATURES_FILE, filters=[("date", "<=", pd.Timestamp(SPLITS["train"][1]))])
    trace = []
    for ticker, date in [("AAPL", "2018-12-20"), ("AAPL", "2018-12-24"), ("MSFT", "2008-09-15"), ("JCI", "2007-07-02"), ("EXPE", "2011-12-21")]:
        day = pd.Timestamp(date)
        row = labels[(labels.ticker == ticker) & (labels.date == day)].iloc[0]
        sessions = sessions_between(day, day + pd.Timedelta(days=30))[:6]
        target = sessions[-1]
        panel = prices[prices.date.isin(sessions)]
        good = []
        if target <= pd.Timestamp(SPLITS["train"][1]):
            for _, g in panel.groupby("ticker"):
                g = g.sort_values("date")
                if len(g) == 6 and not g.bad_bar.any() and g.adj_close.notna().all():
                    good.append((g.ticker.iloc[0], float(g.adj_close.iloc[-1] / g.adj_close.iloc[0] - 1)))
        own = dict(good).get(ticker)
        market = float(np.mean([r for _, r in good])) if good else None
        expected = int(own > market) if own is not None and len(good) >= 150 and own != market else None
        actual = None if pd.isna(row.label) else int(row.label)
        assert actual == expected, (ticker, date, actual, expected)
        hist_days = sessions_between(day - pd.Timedelta(days=50), day)[-22:]
        hist = prices[(prices.ticker == ticker) & prices.date.isin(hist_days)].sort_values("date")
        f = features[(features.ticker == ticker) & (features.date == day)].iloc[0]
        valid = len(hist) == 22 and not hist.bad_bar.any() and hist.adj_close.notna().all()
        ret21 = float(hist.adj_close.iloc[-1] / hist.adj_close.iloc[0] - 1) if valid else None
        assert (pd.isna(f.ret_21d) if ret21 is None else np.isclose(f.ret_21d, ret21, rtol=1e-5, atol=1e-7))
        trace.append({"ticker": ticker, "as_of_date": date, "calendar_target": str(target.date()),
                      "status": row.status, "independently_verified_label": expected, "stock_return": own,
                      "benchmark_return": market, "valid_stocks": len(good), "manual_ret_21d": ret21})
    result = {"at": now(), "train_only": True, "traces": trace,
              "checks": ["Five-session labels independently recalculated from all valid stocks.",
                         "21-session returns checked from each stock's own clean history.",
                         "A late-2018 target outside train is invalid; no later price was read.",
                         "Known JCI/EXPE bad-bar windows remain invalid."],
              "limits": ["Current-constituent survivorship bias remains.",
                         "Python 3.12 patch version differs from original 3.12.5; package pins are identical.",
                         "This is a focused audit, not independent certification of all Yahoo prices."]}
    write_json(TRACKED / "research_round2_audit.json", result)
    print("Five independent real-data traces passed.", flush=True)
    return result


def run(only: str | None = None, threads: int = 4) -> None:
    if threads < 1:
        raise ValueError("threads must be positive")
    with run_lock(), threadpool_limits(limits=threads):
        manifest = check_manifest()
        if not (TRACKED / "research_round2_audit.json").exists():
            raise RuntimeError("Run audit before model fitting.")
        frame = load_training_frame()
        expanding = purged_walk_forward(frame)
        references = {f["fold"]: m.fit_base_rate(frame.loc[f["train_index"]], BASE_SPEC) for f in expanding}
        print(f"Training-only frame: {len(frame):,} rows. Threads: {threads}.", flush=True)
        for config in configurations():
            if only and config.name != only:
                continue
            if config.name != BASE_NAME:
                require_reproduced_baseline()
            selected = experiment_frame(frame, config)
            for fold in window_folds(frame, config.years):
                n = fold["fold"]
                stem = ROOT / config.name / f"fold-{n}"
                meta_path = stem.with_suffix(".json")
                prediction_path = stem.with_suffix(".parquet")
                if meta_path.exists() and prediction_path.exists():
                    cached = json.loads(meta_path.read_text())
                    if b.sha256_file(prediction_path) != cached["predictions_sha256"]:
                        raise ValueError(f"Prediction cache changed: {prediction_path}")
                    continue
                attempt = {"config": config.name, "fold": n, "source_sha256": manifest["source_sha256"]}
                append_attempt({**attempt, "status": "started"})
                start = time.perf_counter()
                try:
                    fit = selected.loc[fold["train_index"]]
                    ev_index = common_eval_index(frame, expanding[n])
                    ev = selected.loc[ev_index]
                    assert fit.target_date.max() <= fold["fit_end"] < ev.date.min()
                    model = m.fit_model(BASE_SPEC, fit, columns=config.features)
                    pred = model.predict(ev)
                    if not np.isfinite(pred).all():
                        raise ValueError("Non-finite predictions")
                    result = m.score(ev, pred, references[n])
                    result.update({"fold": n, "fit_end": str(fold["fit_end"].date()), "eval_end": str(fold["eval_end"].date()),
                                   "fit_start": str(fit.date.min().date()), "fit_rows": len(model.fit_index),
                                   "fit_dates": int(fit.date.nunique()), "hgb_n_iter": model.n_iter,
                                   "reference_base_rate": references[n], "model_fit_base_rate": m.fit_base_rate(fit, BASE_SPEC),
                                   "total_eval_rows": len(fold["eval_index"]), "coverage": len(ev) / len(fold["eval_index"]),
                                   "runtime_s": round(time.perf_counter()-start, 2), "config": asdict(config)})
                    if config.name == BASE_NAME:
                        original_ev = selected.loc[fold["eval_index"]]
                        reproduced = m.score(original_ev, model.predict(original_ev), references[n])
                        archived = json.loads((TRACKED / "model_selection.json").read_text())["specs"][BASE_NAME]["folds"][n]
                        result["reproduction"] = {
                            "original_eval_rows": len(original_ev),
                            "metric_differences": {k: reproduced[k] - archived[k] for k in ("bal_acc", "accuracy", "brier")},
                            "iteration_counts_match": model.n_iter == archived["hgb_n_iter"],
                        }
                        result["reproduction"]["within_1e_6"] = all(
                            abs(v) <= 1e-6 for v in result["reproduction"]["metric_differences"].values()
                        )
                        if not result["reproduction"]["within_1e_6"]:
                            write_json(ROOT / "baseline_reproduction_failure.json", result["reproduction"])
                            raise RuntimeError("Baseline did not reproduce within 1e-6; investigate before new configurations.")
                    stem.parent.mkdir(parents=True, exist_ok=True)
                    tmp = prediction_path.with_suffix(".parquet.tmp")
                    ev[["ticker", "date"]].assign(p=pred).to_parquet(tmp, index=False)
                    tmp.replace(prediction_path)
                    result["predictions_sha256"] = b.sha256_file(prediction_path)
                    write_json(meta_path, result)
                    append_attempt({**attempt, "status": "completed", "runtime_s": result["runtime_s"]})
                    print(f"{config.name} fold {n}: bal={result['bal_acc']:.6f}, Brier={result['brier']:.6f}, {result['runtime_s']:.1f}s", flush=True)
                except BaseException as exc:
                    append_attempt({**attempt, "status": "failed", "error": repr(exc), "traceback": traceback.format_exc()})
                    raise
                finally:
                    if protected_hashes() != manifest["protected_files"]:
                        raise RuntimeError("Protected prior reports changed")
        report(frame)


def paired_brier_ci(dates, y, prediction, reference) -> dict:
    loss = (np.asarray(prediction)-np.asarray(y))**2 - (np.asarray(reference)-np.asarray(y))**2
    daily = pd.DataFrame({"date": dates, "loss": loss}).groupby("date").loss.agg(["sum", "count"])
    indices = b.moving_block_indices(len(daily), 10, 1000, np.random.default_rng(0))
    draws = daily["sum"].to_numpy()[indices].sum(axis=1) / daily["count"].to_numpy()[indices].sum(axis=1)
    return {"point": float(loss.mean()), "ci95": np.percentile(draws, [2.5, 97.5]).tolist()}


def report(frame: pd.DataFrame | None = None) -> dict:
    manifest = check_manifest()
    frame = load_training_frame() if frame is None else frame
    results, summaries = {}, {}
    baseline_parts = None
    for config in configurations():
        files = [ROOT / config.name / f"fold-{i}.json" for i in range(6)]
        if not all(p.exists() for p in files):
            continue
        folds = [json.loads(p.read_text()) for p in files]
        parts = []
        for i in range(1, 6):
            path = ROOT / config.name / f"fold-{i}.parquet"
            if b.sha256_file(path) != folds[i]["predictions_sha256"]:
                raise ValueError(f"Changed saved predictions: {path}")
            pred = pd.read_parquet(path).assign(fold=i)
            parts.append(pred)
        saved = pd.concat(parts, ignore_index=True)
        if config.name == BASE_NAME:
            baseline_parts = saved
        elif baseline_parts is None:
            continue
        if not saved[["ticker", "date", "fold"]].equals(baseline_parts[["ticker", "date", "fold"]]):
            raise ValueError("Experiments do not cover identical evaluation observations")
        rows = saved.merge(frame[["ticker", "date", "label", "past5_excess"]], on=["ticker", "date"], validate="one_to_one")
        y, pred = rows.label.to_numpy(dtype=int), rows.p.to_numpy()
        rev = (rows.past5_excess.to_numpy() < 0).astype(float)
        entry = {"folds": folds, "summary": m.common_summary(folds, "hgb"), "runtime_s": sum(f["runtime_s"] for f in folds)}
        summaries[config.name] = entry["summary"]
        for name, reference in [("reversal_5d", rev), (BASE_NAME, baseline_parts.p.to_numpy())]:
            lo, hi, point = b.bootstrap_balanced_accuracy_diff(rows.date, y, pred, reference)
            entry[f"balanced_accuracy_minus_{name}"] = {"point": point, "ci95": [lo, hi]}
            entry[f"brier_minus_{name}"] = paired_brier_ci(rows.date, y, pred, reference)
        entry["baselines_by_fold"] = []
        for f in folds:
            if f["fold"] < 1:
                continue
            chunk = rows[rows.fold == f["fold"]]
            predictions = b.baseline_predictions(chunk.past5_excess, int(f["reference_base_rate"] >= 0.5))
            predictions["constant_prob"] = np.full(len(chunk), f["reference_base_rate"])
            entry["baselines_by_fold"].append({"fold": f["fold"], **{k: {
                "accuracy": b.accuracy(chunk.label, v), "bal_acc": b.balanced_accuracy(chunk.label, v), "brier": b.brier(chunk.label, v)
            } for k, v in predictions.items()}})
        results[config.name] = entry
    finalists = m.choose_finalists(summaries) if summaries else []
    result = {"created_at": now(), "manifest": manifest, "results": results, "finalists_train_only": finalists,
              "new_eligible": [n for n, s in summaries.items() if n != BASE_NAME and m.eligible_for_validation(s)],
              "new_configurations_cap": 4, "historical_configurations_tried": 34,
              "new_configurations_completed": max(0, len(results)-1),
              "all_five_complete": len(results) == 5, "validation_run": False, "test_run": False,
              "warning": "Training-fold selection evidence only. Confidence intervals are exploratory, not a new promotion judgment."}
    write_json(TRACKED / "research_round2.json", result)
    print(f"Saved comparison report. Complete: {len(results)}/5; train-only finalist: {finalists}", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "audit", "run", "report"])
    parser.add_argument("--only", choices=[c.name for c in configurations()])
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "audit":
        audit()
    elif args.command == "run":
        run(args.only, args.threads)
    else:
        report()


if __name__ == "__main__":
    main()
