"""Model selection on purged walk-forward folds, and a one-time validation judgment.

Implements ml/docs/prediction-contract.md sections 3.4-3.6 and 5 (ADR-0005, ADR-0006).

Usage (from ml/):
    python -m stocksight_data.modeling select                # all candidate configs on train folds
    python -m stocksight_data.modeling select --only lr_rank_c1e-02_bal
    python -m stocksight_data.modeling judge                 # finalists from the selection report, ONCE

Rules this module enforces:
  * Selection never computes a validation outcome: labels come from prices cut at the
    train end (`build_frame(..., "train")`), and folds come from `folds.purged_walk_forward`.
  * Per-date cross-sectional ranks are computed on every ticker that has features on the
    date, before labels are joined (the label-validity filter looks 5 sessions ahead).
  * Transforms that learn from data (winsorising bounds, means, the missing-indicator
    set) are fitted on the fit rows of each fold only.
  * Adjacent labels share 4 of 5 return days, so models fit on every `stride`-th date
    (optionally one model per offset, averaged: `bags`).
  * `judge` scores at most MAX_FINALISTS candidates with `baselines.gate_model`, appends to
    data/reports/validation_access_log.jsonl, and refuses to re-judge a config without a
    written reason. The test split is refused everywhere in this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from .baselines import (
    _environment,
    _git_state,
    accuracy,
    balanced_accuracy,
    brier,
    gate_model,
    load_frozen_gates,
    sha256_file,
)
from .config import (
    CLEAN_FILE,
    DATA_DIR,
    FEATURES_FILE,
    GATES_FILE,
    MIN_TICKERS_PER_DATE,
    REPORTS_DIR,
    SPLITS,
    TICKERS_FILE,
)
from .feature_report import daily_rank_ic
from .features import model_features
from .folds import purged_walk_forward
from .labels import assign_split, build_labels, check_feature_columns, trailing_excess

SEED = 0
STRIDE = 5
MAX_FINALISTS = 3
HGB_HOLDOUT_DATES = 50  # strided dates (~1 year at stride 5) held out at the end of each fit for early stopping
RANK_PREFIX = "rk_"
FAMILIES = ("lr", "hgb", "rf")
PREPROCESSING = ("rank", "winsor", "raw")
WINSOR_PCT = (1.0, 99.0)

# Market-state features: one value per date (ADR-0006 excludes them by default; opt-in per spec).
MARKET_COLUMNS = [c for c in model_features(include_market=True) if c not in model_features()]

MODELS_DIR = DATA_DIR.parent / "models"
OOF_DIR = MODELS_DIR / "oof"
SELECTION_REPORT = REPORTS_DIR / "model_selection.json"
VALIDATION_REPORT = REPORTS_DIR / "model_validation.json"
VALIDATION_ACCESS_LOG = REPORTS_DIR / "validation_access_log.jsonl"
# Tracked copies (in git): data/ is gitignored, so these let a fresh clone see the selection
# results and, above all, how often validation has been used.
TRACKED_REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"

ESTIMATORS = {"lr": LogisticRegression, "hgb": HistGradientBoostingClassifier, "rf": RandomForestClassifier}
DEFAULTS = {
    "lr": {"max_iter": 2000},
    "hgb": {"early_stopping": True, "n_iter_no_change": 30, "scoring": "loss", "max_iter": 500},
    "rf": {"n_jobs": -1, "max_features": "sqrt"},
}


# ------------------------------------------------------------------- frames
def rank_name(column: str) -> str:
    return RANK_PREFIX + column


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Raw feature names that have a rank column in `frame`, in column order."""
    ranked = {c[len(RANK_PREFIX):] for c in frame.columns if c.startswith(RANK_PREFIX)}
    return [c for c in frame.columns if c in ranked]


def cross_sectional_rank(frame: pd.DataFrame, columns) -> pd.DataFrame:
    """Per-date rank of each column, scaled to (-0.5, 0.5): (rank - 0.5) / n_valid - 0.5.

    Uses only rows of the same date (point-in-time). NaN stays NaN and is excluded from n_valid.
    """
    by_date = frame.groupby("date", sort=False)
    out = {}
    for c in columns:
        r = by_date[c].rank(method="average")
        n = by_date[c].transform("count")
        out[c] = ((r - 0.5) / n - 0.5).astype("float32")
    return pd.DataFrame(out, index=frame.index)


def build_frame(
    prices: pd.DataFrame,
    feats: pd.DataFrame,
    split: str,
    columns,
    min_tickers: int = MIN_TICKERS_PER_DATE,
    market_columns=(),
) -> pd.DataFrame:
    """Labelled rows of `split` with raw features, their per-date ranks and the reversal input.

    Labels and past5_excess are computed from prices cut at the split's end date, so no
    outcome after the split is ever computed. Ranks are computed on every ticker that has
    features on a date, before the label join. `market_columns` (one value per date) are
    kept raw, never ranked. The test split is refused.
    """
    if split not in ("train", "validation"):
        raise ValueError(f"split {split!r} refused: the test split is evaluated once, only via --include-test")
    columns, market_columns = list(columns), list(market_columns)
    check_feature_columns(columns + market_columns)
    lo, hi = (pd.Timestamp(d) for d in SPLITS[split])
    cut = prices[pd.to_datetime(prices["date"]) <= hi]

    labels = build_labels(cut, min_tickers=min_tickers)
    labels = labels[(assign_split(labels) == split) & labels["label"].notna()]
    labels = labels[["ticker", "date", "target_date", "label", "excess_ret"]]
    past = trailing_excess(cut, min_tickers=min_tickers)

    f = feats.loc[:, ["ticker", "date", *columns, *market_columns]].copy()
    f["date"] = pd.to_datetime(f["date"]).astype("datetime64[ns]")
    f = f[f["date"].between(lo, hi)]
    ranks = cross_sectional_rank(f, columns).rename(columns=rank_name)
    f = pd.concat([f[["ticker", "date"]], f[columns + market_columns].astype("float32"), ranks], axis=1)

    out = labels.merge(past, on=["ticker", "date"], how="left", validate="one_to_one")
    out = out.merge(f, on=["ticker", "date"], how="left", validate="one_to_one")
    out["label"] = out["label"].astype("int8")
    return out.sort_values(["date", "ticker"], kind="stable").reset_index(drop=True)


def stride_mask(dates, stride: int = STRIDE, offset: int = 0) -> np.ndarray:
    """True for rows on every `stride`-th distinct date (starting at `offset`), all tickers of a date together."""
    if not 0 <= offset < stride:
        raise ValueError(f"offset must be in [0, {stride}), got {offset}")
    _, codes = np.unique(np.asarray(dates), return_inverse=True)
    return codes % stride == offset


def temporal_holdout(rows: pd.DataFrame, sessions: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split fit rows into (earlier rows, last `sessions` dates) with a label-horizon purge.

    Earlier rows must have target_date before the first holdout date, so no 5-session
    label window is shared with the holdout (used for HGB early stopping).
    """
    days = np.sort(rows["date"].unique())
    first = days[-sessions]
    holdout = rows[rows["date"] >= first]
    earlier = rows[rows["target_date"] < first]
    return earlier, holdout


# ------------------------------------------------------------ preprocessing
class Preprocessor:
    """rank: per-date ranks, NaN -> 0 (the median rank) plus a missing indicator per feature
    that had gaps in the fit rows. winsor: raw values clipped at fit-row 1st/99th
    percentiles and standardised with fit-row mean/std, NaN -> 0 plus indicators.
    raw: raw values with NaN kept (HistGradientBoosting handles missing values natively).
    market_columns (one value per date) are never ranked: with "rank" they get their own
    fit-row winsorise/standardise step (`self.market`); with "winsor"/"raw" they are extra columns."""

    def __init__(self, kind: str, columns, market_columns=()):
        if kind not in PREPROCESSING:
            raise ValueError(f"preprocessing must be one of {PREPROCESSING}, got {kind!r}")
        self.kind = kind
        market_columns = list(market_columns)
        self.market = Preprocessor("winsor", market_columns) if kind == "rank" and market_columns else None
        self.columns = list(columns) + (market_columns if kind != "rank" else [])
        self.indicators: list[str] = []

    def _source(self, frame: pd.DataFrame) -> np.ndarray:
        cols = [rank_name(c) for c in self.columns] if self.kind == "rank" else self.columns
        return frame[cols].to_numpy(dtype="float64")

    def fit(self, frame: pd.DataFrame) -> Preprocessor:
        x = self._source(frame)
        if self.kind != "raw":
            self.indicators = [c for c, gap in zip(self.columns, np.isnan(x).any(axis=0)) if gap]
        if self.kind == "winsor":
            self.lo_, self.hi_ = np.nanpercentile(x, WINSOR_PCT, axis=0)
            clipped = np.clip(x, self.lo_, self.hi_)
            self.mean_ = np.nanmean(clipped, axis=0)
            std = np.nanstd(clipped, axis=0)
            self.std_ = np.where(std > 0, std, 1.0)
        if self.market is not None:
            self.market.fit(frame)
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        x = self._source(frame)
        if self.kind == "raw":
            return x.astype("float32")
        missing = np.isnan(x)
        if self.kind == "winsor":
            x = (np.clip(x, self.lo_, self.hi_) - self.mean_) / self.std_
        x = np.where(missing, 0.0, x)
        flags = missing[:, [self.columns.index(c) for c in self.indicators]].astype("float64")
        parts = [x] + ([self.market.transform(frame)] if self.market is not None else []) + [flags]
        return np.hstack(parts).astype("float32")


# ------------------------------------------------------------------- models
@dataclass(frozen=True)
class ModelSpec:
    name: str
    family: str
    preprocess: str
    params: tuple = ()
    stride: int = STRIDE
    bags: int = 1
    market: bool = False  # add MARKET_COLUMNS (recorded experiment; excluded by default, ADR-0006)

    def __post_init__(self):
        if self.family not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}, got {self.family!r}")
        if self.preprocess not in PREPROCESSING:
            raise ValueError(f"preprocessing must be one of {PREPROCESSING}, got {self.preprocess!r}")
        if not 1 <= self.bags <= self.stride:
            raise ValueError("bags must be between 1 and stride (one model per date offset)")

    def config_id(self) -> str:
        fields = [self.family, self.preprocess, sorted(self.params), self.stride, self.bags]
        if self.market:  # appended only when set, so ids of default specs stay stable
            fields.append("market")
        key = json.dumps(fields, default=str)
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {**asdict(self), "params": dict(self.params), "config_id": self.config_id()}


def make_estimator(spec: ModelSpec, seed: int = SEED):
    params = {**DEFAULTS[spec.family], **dict(spec.params)}
    if spec.family in ("hgb", "rf"):
        params["random_state"] = seed
    return ESTIMATORS[spec.family](**params)


@dataclass
class FittedModel:
    spec: ModelSpec
    members: list = field(default_factory=list)  # (Preprocessor, estimator) per date offset
    fit_index: pd.Index | None = None
    n_iter: list = field(default_factory=list)

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        ps = [est.predict_proba(pre.transform(frame))[:, 1] for pre, est in self.members]
        return np.mean(ps, axis=0)


def fit_base_rate(rows: pd.DataFrame, spec: ModelSpec) -> float:
    """Beat rate of every strided row the spec samples from `rows` (all offsets < bags), including
    HGB's early-stopping holdout, so every family is compared with the same constant."""
    keep = np.zeros(len(rows), dtype=bool)
    for offset in range(spec.bags):
        keep |= stride_mask(rows["date"], spec.stride, offset)
    return float(rows["label"].to_numpy()[keep].mean())


def fit_model(spec: ModelSpec, rows: pd.DataFrame, seed: int = SEED) -> FittedModel:
    """Fit one model per date offset on every spec.stride-th date of `rows` (the fit rows of a fold)."""
    columns = feature_columns(rows)
    market = [c for c in MARKET_COLUMNS if c in rows.columns] if spec.market else []
    if spec.market and not market:
        raise ValueError("spec.market is set but the frame has no market columns")
    model = FittedModel(spec)
    used = []
    for offset in range(spec.bags):
        sub = rows[stride_mask(rows["date"], spec.stride, offset)]
        est = make_estimator(spec, seed + offset)
        if spec.family == "hgb":
            n_hold = min(HGB_HOLDOUT_DATES, max(1, sub["date"].nunique() // 4))
            fit_part, hold = temporal_holdout(sub, n_hold)
            pre = Preprocessor(spec.preprocess, columns, market).fit(fit_part)
            est.fit(pre.transform(fit_part), fit_part["label"].to_numpy(),
                    X_val=pre.transform(hold), y_val=hold["label"].to_numpy())
            model.n_iter.append(int(est.n_iter_))
            used.append(fit_part.index)
        else:
            pre = Preprocessor(spec.preprocess, columns, market).fit(sub)
            est.fit(pre.transform(sub), sub["label"].to_numpy())
            used.append(sub.index)
        model.members.append((pre, est))
    model.fit_index = used[0].append(used[1:]) if len(used) > 1 else used[0]
    return model


# ------------------------------------------------------------------ metrics
def per_date_auc(dates, y, p) -> float:
    """Mean over dates of the within-date AUC; dates with a single class are skipped."""
    d = pd.DataFrame({"date": np.asarray(dates), "y": np.asarray(y, dtype=int), "p": np.asarray(p, dtype=float)})
    d["r"] = d.groupby("date")["p"].rank(method="average")
    g = d.groupby("date")
    n1 = g["y"].sum()
    n0 = g["y"].count() - n1
    pos_rank_sum = (d["r"] * d["y"]).groupby(d["date"]).sum()
    ok = (n1 > 0) & (n0 > 0)
    auc = (pos_rank_sum[ok] - n1[ok] * (n1[ok] + 1) / 2) / (n1[ok] * n0[ok])
    return float(auc.mean())


def per_date_rank_ic(dates, p, excess) -> float:
    """Mean over dates of the Spearman correlation between predictions and excess returns."""
    d = pd.DataFrame({"date": np.asarray(dates), "p": np.asarray(p, dtype=float), "excess_ret": np.asarray(excess)})
    return float(daily_rank_ic(d, "p").mean())


def score(rows: pd.DataFrame, p, base_rate: float) -> dict:
    """Gate metrics plus ranking metrics on `rows` (label, excess_ret, past5_excess, date)."""
    p = np.asarray(p, dtype=float)
    y = rows["label"].to_numpy().astype(int)
    dates = rows["date"].to_numpy()
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    out = {
        "rows": int(len(y)),
        "dates": int(pd.unique(dates).size),
        "accuracy": accuracy(y, p),
        "majority_acc": accuracy(y, np.full(len(y), float(base_rate >= 0.5))),
        "bal_acc": balanced_accuracy(y, p),
        "brier": brier(y, p),
        "constant_brier": brier(y, np.full(len(y), base_rate)),
        "log_loss": float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc))),
        "auc_date": per_date_auc(dates, y, p),
        "ic_date": per_date_rank_ic(dates, p, rows["excess_ret"].to_numpy()),
        "pred_beat_share": float((p >= 0.5).mean()),
        "mean_p": float(p.mean()),
    }
    has = rows["past5_excess"].notna().to_numpy()
    rev = (rows["past5_excess"].to_numpy()[has] < 0).astype(float)
    out["reversal_bal_acc"] = balanced_accuracy(y[has], rev)
    out["bal_acc_minus_reversal"] = balanced_accuracy(y[has], p[has]) - out["reversal_bal_acc"]
    return out


# ------------------------------------------------------------- walk-forward
def walk_forward(frame: pd.DataFrame, spec: ModelSpec, folds, seed: int = SEED):
    """Out-of-fold predictions (index = eval rows; columns fold, p) and per-fold fit diagnostics."""
    parts, diag = [], []
    for fold in folds:
        rows = frame.loc[fold["train_index"]]
        model = fit_model(spec, rows, seed)
        ev = frame.loc[fold["eval_index"]]
        parts.append(pd.DataFrame({"fold": fold["fold"], "p": model.predict(ev)}, index=ev.index))
        fitted = frame.loc[model.fit_index]
        diag.append(
            {
                "fold": int(fold["fold"]),
                "fit_end": f"{pd.Timestamp(fold['fit_end']):%Y-%m-%d}",
                "eval_end": f"{pd.Timestamp(fold['eval_end']):%Y-%m-%d}",
                "fit_rows": int(len(fitted)),
                "fit_dates": int(fitted["date"].nunique()),
                "fit_beat_rate": fit_base_rate(rows, spec),
                "fit_bal_acc": balanced_accuracy(fitted["label"].to_numpy(), model.predict(fitted)),
                "hgb_n_iter": model.n_iter or None,
            }
        )
    return pd.concat(parts), diag


def fold_scores(frame: pd.DataFrame, oof: pd.DataFrame, diag: list[dict], p_col: str = "p") -> list[dict]:
    out = []
    for d in diag:
        part = oof[(oof["fold"] == d["fold"]) & oof[p_col].notna()]
        if part.empty:
            continue
        out.append({**d, **score(frame.loc[part.index], part[p_col].to_numpy(), base_rate=d["fit_beat_rate"])})
    return out


# --------------------------------------------------------------- calibration
def platt_fit(p, y):
    """Logistic recalibration on logit(p); returns a function p -> calibrated p."""
    def logit(q):
        q = np.clip(np.asarray(q, dtype=float), 1e-6, 1 - 1e-6)
        return np.log(q / (1 - q)).reshape(-1, 1)

    lr = LogisticRegression(C=1e6, max_iter=1000).fit(logit(p), np.asarray(y, dtype=int))
    return lambda q: lr.predict_proba(logit(q))[:, 1]


def nested_platt(oof: pd.DataFrame, y) -> pd.Series:
    """Calibrate fold k with a Platt map fitted on folds < k only (fold 0 stays NaN)."""
    y = np.asarray(y)
    folds = oof["fold"].to_numpy()
    out = pd.Series(np.nan, index=oof.index)
    for k in sorted(np.unique(folds)):
        prior = folds < k
        if not prior.any():
            continue
        f = platt_fit(oof["p"].to_numpy()[prior], y[prior])
        cur = folds == k
        out[cur] = f(oof["p"].to_numpy()[cur])
    return out


# ----------------------------------------------------------------- selection
SUMMARY_KEYS = ["bal_acc", "accuracy", "majority_acc", "brier", "constant_brier", "log_loss", "auc_date", "ic_date",
                "bal_acc_minus_reversal"]


def passes_gate_proxies(f: dict) -> bool:
    """Fold-level analogue of the frozen gates (without the bootstrap CI and the yearly rule):
    beats reversal on balanced accuracy, accuracy >= majority, Brier < constant."""
    return f["bal_acc_minus_reversal"] > 0 and f["accuracy"] >= f["majority_acc"] and f["brier"] < f["constant_brier"]


def summarise(fold_metrics: list[dict], family: str) -> dict:
    s = {"family": family, "n_folds": len(fold_metrics)}
    for k in SUMMARY_KEYS:
        s[f"mean_{k}"] = float(np.mean([f[k] for f in fold_metrics]))
    bal = [f["bal_acc"] for f in fold_metrics]
    s["std_bal_acc"] = float(np.std(bal, ddof=1)) if len(bal) > 1 else 0.0
    s["worst_bal_acc"] = float(min(bal))
    s["folds_beating_reversal"] = int(sum(f["bal_acc_minus_reversal"] > 0 for f in fold_metrics))
    s["folds_passing_gate_proxies"] = int(sum(passes_gate_proxies(f) for f in fold_metrics))
    s["brier_beats_constant"] = bool(s["mean_brier"] < s["mean_constant_brier"])
    return s


COMMON_FROM_FOLD = 1  # fold 0 has no earlier fold to fit a calibration map on


def common_summary(fold_metrics: list[dict], family: str) -> dict:
    """Summary on the folds every candidate has (1-5), so calibrated candidates, whose fold 0 is
    missing, are compared with everything else on identical rows. Used for eligibility and ranking."""
    return summarise([f for f in fold_metrics if f["fold"] >= COMMON_FROM_FOLD], family)


def eligible_for_validation(s: dict) -> bool:
    """Mean-over-folds analogue of the three point gates: beats reversal on balanced accuracy,
    accuracy >= majority, Brier < constant. A config failing any of these on train folds is not
    expected to pass on validation, and judging it would only add to the number of trials."""
    return (
        s["brier_beats_constant"]
        and s["mean_bal_acc_minus_reversal"] > 0
        and s["mean_accuracy"] >= s["mean_majority_acc"]
    )


def choose_finalists(summary: dict[str, dict], max_n: int = MAX_FINALISTS) -> list[str]:
    """Among eligible configs, the best per family by (share of folds passing all gate proxies,
    mean fold balanced accuracy); families ordered by the same key; at most max_n. May be empty."""
    def key(name):
        s = summary[name]
        return (s["folds_passing_gate_proxies"] / s["n_folds"], s["mean_bal_acc"])

    best: dict[str, str] = {}
    for name, s in summary.items():
        if not eligible_for_validation(s):
            continue
        fam = s["family"]
        if fam not in best or key(name) > key(best[fam]):
            best[fam] = name
    return sorted(best.values(), key=key, reverse=True)[:max_n]


def candidate_specs() -> list[ModelSpec]:
    """The selection grid. Every config run is recorded; the count goes into the ledger."""
    specs = []
    for cw in (None, "balanced"):
        tag = "bal" if cw else "nowt"
        for c in (1e-4, 1e-3, 1e-2, 1.0):
            specs.append(ModelSpec(f"lr_rank_c{c:.0e}_{tag}", "lr", "rank", (("C", c), ("class_weight", cw))))
        specs.append(ModelSpec(f"lr_winsor_c1e-02_{tag}", "lr", "winsor", (("C", 1e-2), ("class_weight", cw))))
    shapes = {
        "small": (("learning_rate", 0.05), ("max_leaf_nodes", 8), ("max_depth", 3), ("min_samples_leaf", 2000),
                  ("l2_regularization", 1.0)),
        "wide": (("learning_rate", 0.05), ("max_leaf_nodes", 16), ("min_samples_leaf", 5000),
                 ("l2_regularization", 10.0)),
    }
    for pre in ("rank", "raw"):
        for shape, params in shapes.items():
            for cw in (None, "balanced"):
                tag = "bal" if cw else "nowt"
                specs.append(ModelSpec(f"hgb_{pre}_{shape}_{tag}", "hgb", pre, (*params, ("class_weight", cw))))
    rf_common = (("n_estimators", 300), ("max_samples", 0.2))
    specs += [
        ModelSpec("rf_d6_l2000_nowt", "rf", "rank", (*rf_common, ("max_depth", 6), ("min_samples_leaf", 2000))),
        ModelSpec("rf_d6_l2000_bal", "rf", "rank",
                  (*rf_common, ("max_depth", 6), ("min_samples_leaf", 2000), ("class_weight", "balanced_subsample"))),
        ModelSpec("rf_d10_l500_bal", "rf", "rank",
                  (*rf_common, ("max_depth", 10), ("min_samples_leaf", 500), ("class_weight", "balanced_subsample"))),
        # Overlap experiment: every date (stride 1); near-duplicate rows should widen the fit/eval gap.
        ModelSpec("rf_d10_l500_bal_stride1", "rf", "rank",
                  (*rf_common, ("max_depth", 10), ("min_samples_leaf", 500), ("class_weight", "balanced_subsample")),
                  stride=1),
    ]
    # Market-state experiment (added after fold diagnostics showed the Brier gap is dominated by the
    # date-level beat rate, which per-date ranks cannot see). Recorded as its own group in the ledger.
    for cw in (None, "balanced"):
        tag = "bal" if cw else "nowt"
        for c in (1e-3, 1e-2):
            specs.append(ModelSpec(f"lr_rank_c{c:.0e}_{tag}_mkt", "lr", "rank", (("C", c), ("class_weight", cw)),
                                   market=True))
        specs.append(ModelSpec(f"hgb_rank_small_{tag}_mkt", "hgb", "rank", (*shapes["small"], ("class_weight", cw)),
                               market=True))
    return specs


# ------------------------------------------------------- validation guard
def _log_entries(log_path) -> list[dict]:
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def record_validation_access(
    log_path, specs, reason: str | None, extra: dict | None = None, members: list[list[str]] | None = None
) -> int:
    """Append a "started" validation-access entry before any validation work is done.

    Refuses, unless a written `reason` is given:
      * a candidate, or any member model inside it, that was already judged;
      * a cumulative total of distinct judged candidates above MAX_FINALISTS.
    More than MAX_FINALISTS in one call is always refused. `members` lists the underlying
    config ids per candidate (default: the candidate itself). Aborted runs still count.
    Returns the number of validation accesses so far, including this one.
    """
    if len(specs) > MAX_FINALISTS:
        raise ValueError(f"at most {MAX_FINALISTS} finalists may be judged on validation, got {len(specs)}")
    members = members or [[s.config_id()] for s in specs]
    accesses = [e for e in _log_entries(log_path) if e.get("status", "started") == "started"]
    judged = {cid for e in accesses for cid in e["config_ids"] + e.get("member_ids", [])}
    ids = [s.config_id() for s in specs]
    member_ids = sorted({cid for ms in members for cid in ms})
    repeats = sorted((set(ids) | set(member_ids)) & judged)
    if repeats and not reason:
        raise PermissionError(f"configs already judged on validation: {repeats}; pass a written reason to re-judge")
    total = {cid for e in accesses for cid in e["config_ids"]} | set(ids)
    if len(total) > MAX_FINALISTS and not reason:
        raise PermissionError(f"cumulative validation trials would reach {len(total)} > {MAX_FINALISTS}; "
                              "pass a written reason")
    entry = {
        "status": "started",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_finalists": len(specs),
        "names": [s.name for s in specs],
        "config_ids": ids,
        "member_ids": member_ids,
        "reason": reason,
        "seed": SEED,
        **(extra or {}),
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return len(accesses) + 1


def mark_validation_completed(log_path, access: int) -> None:
    with open(log_path, "a") as f:
        f.write(json.dumps({"status": "completed", "access": access,
                            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")


def check_judge_names(names: list[str], summary: dict[str, dict], reason: str | None) -> list[str]:
    """Only candidates that the finalist rule picks (recomputed now) may be judged without a reason."""
    finalists = choose_finalists(summary)
    extra = [n for n in names if n not in finalists]
    if extra and not reason:
        raise PermissionError(f"not finalists under the selection rule: {extra} (finalists: {finalists}); "
                              "pass a written reason")
    return names


# ------------------------------------------------------------------------ CLI
def _provenance() -> dict:
    env = _environment()
    for pkg in ("scikit-learn", "scipy"):
        try:
            env["packages"][pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            env["packages"][pkg] = None
    meta_file = FEATURES_FILE.with_name("features.meta.json")
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    return {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_sha256": sha256_file(CLEAN_FILE),
        "features_sha256": meta.get("features_sha256"),
        "code": _git_state(),
        "environment": env,
        "seed": SEED,
    }


def load_frame(split: str) -> pd.DataFrame:
    hi = pd.Timestamp(SPLITS[split][1])
    lo = pd.Timestamp(SPLITS[split][0])
    columns = model_features()
    prices = pd.read_parquet(CLEAN_FILE, columns=["ticker", "date", "adj_close", "bad_bar"])
    feats = pd.read_parquet(
        FEATURES_FILE, columns=["ticker", "date", *columns, *MARKET_COLUMNS],
        filters=[("date", ">=", lo), ("date", "<=", hi)],
    )
    return build_frame(prices, feats, split, columns, market_columns=MARKET_COLUMNS)


def _read_report() -> dict:
    return json.loads(SELECTION_REPORT.read_text()) if SELECTION_REPORT.exists() else {"specs": {}}


def _spec_from_dict(d: dict) -> ModelSpec:
    return ModelSpec(d["name"], d["family"], d["preprocess"], tuple(d["params"].items()), d["stride"], d["bags"],
                     d.get("market", False))


def _oof_path(name: str):
    return OOF_DIR / f"{name}.parquet"


def run_select(only: list[str] | None, rerun: bool) -> dict:
    t0 = time.time()
    frame = load_frame("train")
    folds = purged_walk_forward(frame)
    print(f"train frame: {len(frame):,} rows, {frame['date'].nunique()} dates, {len(feature_columns(frame))} features"
          f" ({time.time() - t0:.0f}s)")
    report = _read_report()
    report["provenance"] = _provenance()
    report["folds"] = [{"fold": f["fold"], "fit_end": f"{f['fit_end']:%Y-%m-%d}", "eval_end": f"{f['eval_end']:%Y-%m-%d}",
                        "fit_rows": len(f["train_index"]), "eval_rows": len(f["eval_index"])} for f in folds]
    specs = [s for s in candidate_specs() if only is None or s.name in only]
    OOF_DIR.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        if spec.name in report["specs"] and not rerun:
            print(f"skip {spec.name} (already in report)")
            continue
        t = time.time()
        oof, diag = walk_forward(frame, spec, folds)
        fold_metrics = fold_scores(frame, oof, diag)
        oof.assign(date=frame.loc[oof.index, "date"], ticker=frame.loc[oof.index, "ticker"]).to_parquet(
            _oof_path(spec.name)
        )
        report["specs"][spec.name] = {
            "spec": spec.to_dict(),
            "folds": fold_metrics,
            "summary": common_summary(fold_metrics, spec.family),
            "summary_all_folds": summarise(fold_metrics, spec.family),
            "runtime_s": round(time.time() - t, 1),
        }
        s = report["specs"][spec.name]["summary_all_folds"]
        gap = np.mean([f["fit_bal_acc"] - f["bal_acc"] for f in fold_metrics])
        print(f"{spec.name:<28} bal {s['mean_bal_acc']:.4f} (worst {s['worst_bal_acc']:.4f}) "
              f"-rev {s['mean_bal_acc_minus_reversal']:+.4f} [{s['folds_beating_reversal']}/6] "
              f"brier {s['mean_brier']:.5f} vs {s['mean_constant_brier']:.5f} auc {s['mean_auc_date']:.4f} "
              f"ic {s['mean_ic_date']:+.4f} fit-gap {gap:+.4f} ({report['specs'][spec.name]['runtime_s']:.0f}s)",
              flush=True)
        _write_report(report)
    return _finish(frame, report)


DIAG_KEYS = ("fold", "fit_end", "eval_end", "fit_rows", "fit_dates", "fit_beat_rate", "fit_bal_acc", "hgb_n_iter")


def _finish(frame: pd.DataFrame, report: dict) -> dict:
    report["candidates"] = evaluate_candidates(frame, report)
    # Candidates are re-derived from the current best specs; ones evaluated earlier still count as trials.
    ever = set(report.get("candidates_ever", [])) | set(report["candidates"])
    report["candidates_ever"] = sorted(ever)
    report["n_configs_tried"] = len(report["specs"]) + len(ever)
    summary = {**{n: v["summary"] for n, v in report["specs"].items()},
               **{n: v["summary"] for n, v in report["candidates"].items()}}
    report["finalists"] = choose_finalists(summary)
    _write_report(report)
    return report


def run_rescore() -> dict:
    """Recompute fold metrics and summaries from the stored out-of-fold predictions (no refitting)."""
    frame = load_frame("train")
    folds = {f["fold"]: f for f in purged_walk_forward(frame)}
    report = _read_report()
    for name, entry in report["specs"].items():
        spec = _spec_from_dict(entry["spec"])
        oof = _load_oof(frame, name)
        diag = [{k: f[k] for k in DIAG_KEYS} for f in entry["folds"]]
        for d in diag:
            d["fit_beat_rate"] = fit_base_rate(frame.loc[folds[d["fold"]]["train_index"]], spec)
        entry["folds"] = fold_scores(frame, oof, diag)
        entry["summary"] = common_summary(entry["folds"], spec.family)
        entry["summary_all_folds"] = summarise(entry["folds"], spec.family)
    return _finish(frame, report)


def missing_oof(names) -> list[str]:
    """Spec names whose out-of-fold prediction file is absent (data/ is not in git)."""
    return [n for n in names if not _oof_path(n).exists()]


def check_access_log_in_sync(local, tracked) -> None:
    """Refuse when the tracked copy (ml/reports, in git) records validation accesses that the
    local log (data/reports, gitignored) lacks, e.g. on a fresh clone. Otherwise the guard would
    believe validation was never used."""
    if not tracked.exists():
        return
    def started(path):
        return [e for e in _log_entries(path) if e.get("status", "started") == "started"]
    if len(started(local)) < len(started(tracked)):
        raise RuntimeError(
            f"{tracked} records {len(started(tracked))} validation access(es) but {local} has "
            f"{len(started(local))}: copy the tracked file to {local} before judging (see ml/HANDOFF.md)"
        )


def sync_tracked(paths, dest=None) -> None:
    """Copy reports that must survive a fresh clone into ml/reports (tracked in git)."""
    dest = TRACKED_REPORTS_DIR if dest is None else dest
    dest.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            shutil.copyfile(path, dest / path.name)


def _load_oof(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    if not _oof_path(name).exists():
        raise FileNotFoundError(
            f"{_oof_path(name)} is missing (data/ is not in git). Copy data/models/oof/ from the author, "
            f"or rerun `python -m stocksight_data.modeling select --only {name} --rerun`"
        )
    o = pd.read_parquet(_oof_path(name))
    if not (o["date"].equals(frame.loc[o.index, "date"]) and o["ticker"].equals(frame.loc[o.index, "ticker"])):
        raise ValueError(f"OOF predictions for {name} do not align with the train frame; rerun select")
    return o


def evaluate_candidates(frame: pd.DataFrame, report: dict) -> dict:
    """Calibrated variants of the best spec per family and an LR+HGB average.

    Fold 0 has no earlier folds to fit a calibration map on, so every summary used for
    eligibility and ranking (specs and candidates alike) covers folds 1-5 (`common_summary`).
    """
    summary = {n: v["summary"] for n, v in report["specs"].items()}
    best = {}
    for name, s in summary.items():
        if s["family"] not in best or s["mean_bal_acc"] > summary[best[s["family"]]]["mean_bal_acc"]:
            best[s["family"]] = name
    out = {}

    def load(name):
        return _load_oof(frame, name)

    diags = {n: [{k: f[k] for k in DIAG_KEYS} for f in report["specs"][n]["folds"]] for n in best.values()}
    for fam, name in best.items():
        oof = load(name)
        y = frame.loc[oof.index, "label"].to_numpy()
        cal = oof.assign(p=nested_platt(oof, y))
        metrics = fold_scores(frame, cal, diags[name])
        out[f"{name}+platt"] = {"members": [name], "calibrate": True, "folds": metrics,
                                "summary": common_summary(metrics, fam)}
    if "lr" in best and "hgb" in best:
        a, b = load(best["lr"]), load(best["hgb"])
        avg = a.assign(p=(a["p"] + b.loc[a.index, "p"]) / 2)
        metrics = fold_scores(frame, avg, diags[best["lr"]])
        out[f"{best['lr']}+{best['hgb']}"] = {"members": [best["lr"], best["hgb"]], "calibrate": False,
                                              "folds": metrics, "summary": common_summary(metrics, "ensemble"),
                                              "summary_all_folds": summarise(metrics, "ensemble")}
    for n, c in out.items():
        s = c["summary"]
        print(f"{n:<52} bal {s['mean_bal_acc']:.4f} brier {s['mean_brier']:.5f} vs {s['mean_constant_brier']:.5f}"
              f" auc {s['mean_auc_date']:.4f} (folds {[f['fold'] for f in c['folds']]})")
    return out


def _write_report(report: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SELECTION_REPORT.write_text(json.dumps(report, indent=2, default=str))


def slices(val: pd.DataFrame, p: np.ndarray) -> dict:
    """Balanced accuracy and AUC by year, volatility tercile (per date) and current GICS sector.

    Sector comes from today's tickers.csv: an evaluation slice only, never a model input.
    """
    d = val[["date", "ticker", "label", "excess_ret"]].assign(p=p)
    d["year"] = d["date"].dt.year
    if rank_name("vol_63d") in val:
        d["vol_tercile"] = pd.cut(val[rank_name("vol_63d")], [-0.5, -1 / 6, 1 / 6, 0.5],
                                  labels=["low", "mid", "high"], include_lowest=True).astype(str)
    if TICKERS_FILE.exists():
        sectors = pd.read_csv(TICKERS_FILE).set_index("yf_symbol")["sector"]
        d["sector"] = d["ticker"].map(sectors).fillna("unknown")
    out = {}
    for key in ("year", "vol_tercile", "sector"):
        if key not in d:
            continue
        out[key] = {
            str(k): {"rows": int(len(g)), "beat_rate": float(g["label"].mean()),
                     "bal_acc": balanced_accuracy(g["label"].to_numpy(), g["p"].to_numpy()),
                     "auc_date": per_date_auc(g["date"], g["label"], g["p"])}
            for k, g in d.groupby(key)
        }
    return out


def run_judge(names: list[str] | None, reason: str | None) -> dict:
    report = _read_report()
    candidates = {**{n: {"members": [n], "calibrate": False} for n in report["specs"]}, **report.get("candidates", {})}
    summary = {**{n: v["summary"] for n, v in report["specs"].items()},
               **{n: v["summary"] for n, v in report.get("candidates", {}).items()}}
    names = names or choose_finalists(summary)  # recomputed, never the stored list
    if not names:
        raise SystemExit("no candidate is eligible under the selection rule; nothing to judge")
    unknown = [n for n in names if n not in candidates]
    if unknown:
        raise SystemExit(f"not in the selection report (only selected configs may be judged): {unknown}")
    check_judge_names(names, summary, reason)
    gates = load_frozen_gates(GATES_FILE, sha256_file(CLEAN_FILE))
    # Check everything judge needs BEFORE logging the access, so a missing file cannot consume it.
    check_access_log_in_sync(VALIDATION_ACCESS_LOG, TRACKED_REPORTS_DIR / VALIDATION_ACCESS_LOG.name)
    absent = missing_oof({m for n in names for m in candidates[n]["members"]})
    if absent:
        raise SystemExit(f"out-of-fold predictions missing for {sorted(absent)}: copy data/models/oof/ "
                         "or rerun `select --only <names> --rerun` first")

    # Each judged candidate is logged under one pseudo-spec whose id covers members and calibration.
    def candidate_spec(n):
        members = [_spec_from_dict(report["specs"][m]["spec"]) for m in candidates[n]["members"]]
        if len(members) == 1 and not candidates[n]["calibrate"]:
            return members[0]
        ids = "+".join(s.config_id() for s in members) + ("+platt" if candidates[n]["calibrate"] else "")
        return ModelSpec(n, members[0].family, members[0].preprocess, (("candidate", ids),))

    member_ids = [[_spec_from_dict(report["specs"][m]["spec"]).config_id() for m in candidates[n]["members"]]
                  for n in names]
    n_access = record_validation_access(
        VALIDATION_ACCESS_LOG, [candidate_spec(n) for n in names], reason, members=member_ids,
        extra={"dataset_sha256": gates["dataset_sha256"], "n_configs_tried": report.get("n_configs_tried")},
    )
    print(f"validation access #{n_access}: judging {names}")

    train = load_frame("train")
    val = load_frame("validation")
    base_rate = float(train["label"].mean())
    fitted: dict[str, np.ndarray] = {}
    results = {}
    for n in names:
        c = candidates[n]
        ps = []
        for member in c["members"]:
            if member not in fitted:
                spec = _spec_from_dict(report["specs"][member]["spec"])
                t = time.time()
                fitted[member] = fit_model(spec, train).predict(val)
                print(f"  fitted {member} on all train rows ({time.time() - t:.0f}s)")
            ps.append(fitted[member])
        p = np.mean(ps, axis=0)
        # Label-free diagnostic: does the refit model's score distribution match the OOF scores
        # the calibration map (and the fold metrics) were computed on?
        oofs = [_load_oof(train, m)["p"] for m in c["members"]]
        oof_p = np.mean([o.to_numpy() for o in oofs], axis=0)
        spread = {"oof_mean": float(oof_p.mean()), "oof_sd": float(oof_p.std()),
                  "final_mean": float(p.mean()), "final_sd": float(p.std())}
        if c["calibrate"]:
            if len(c["members"]) > 1:
                raise ValueError("calibrated ensembles are not supported")
            p = platt_fit(oof_p, train.loc[oofs[0].index, "label"].to_numpy())(p)
        results[n] = {
            "raw_score_spread": spread,
            "gate": gate_model(val, p, gates),
            "secondary": score(val, p, base_rate=base_rate),
            "slices": slices(val, p),
        }
        g = results[n]["gate"]
        d = g[f"model_minus_{gates['best_baseline']}_bal_acc"]
        print(f"{n}: bal {g['model']['balanced_accuracy']:.4f} acc {g['model']['accuracy']:.4f} "
              f"brier {g['model']['brier']:.5f} | vs {gates['best_baseline']} {d['point']:+.4f} "
              f"CI [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}] | years "
              f"{ {y: round(v, 4) for y, v in g['yearly_bal_acc'].items()} } | passed={g['gates']['passed']}")
    out = {"provenance": _provenance(), "validation_access": n_access, "n_finalists": len(names),
           "n_configs_tried": report.get("n_configs_tried"), "frozen_gates": gates, "results": results}
    previous = json.loads(VALIDATION_REPORT.read_text()) if VALIDATION_REPORT.exists() else {"runs": []}
    previous["runs"].append(out)
    VALIDATION_REPORT.write_text(json.dumps(previous, indent=2, default=str))
    mark_validation_completed(VALIDATION_ACCESS_LOG, n_access)
    sync_tracked([VALIDATION_ACCESS_LOG, VALIDATION_REPORT, SELECTION_REPORT])
    print(f"tracked copies updated in {TRACKED_REPORTS_DIR}: commit them")
    print(f"report: {VALIDATION_REPORT}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sel = sub.add_parser("select", help="walk-forward selection inside train")
    sel.add_argument("--only", nargs="+", help="run only these config names")
    sel.add_argument("--rerun", action="store_true", help="re-run configs already in the report")
    sub.add_parser("rescore", help="recompute fold metrics from stored out-of-fold predictions")
    jd = sub.add_parser("judge", help=f"judge at most {MAX_FINALISTS} finalists once on validation")
    jd.add_argument("--names", nargs="+", help="candidates to judge (default: the report's finalists)")
    jd.add_argument("--reason", help="required to re-judge a config that was already judged")
    args = parser.parse_args()
    if args.cmd == "select":
        run_select(args.only, args.rerun)
    elif args.cmd == "rescore":
        run_rescore()
    else:
        run_judge(args.names, args.reason)


if __name__ == "__main__":
    main()
