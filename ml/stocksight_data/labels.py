"""5-session market-relative labels and purged chronological splits.

Implements ml/docs/prediction-contract.md section 3.2 (ADR-0004) and 3.5 (ADR-0005).
For each (ticker, as_of_date t):

    r5[t]         = adj_close[t+5] / adj_close[t] - 1     (t+5 = 5th NYSE session after t)
    market_r5[t]  = equal-weight mean (or median) of r5 across valid tickers on t
    excess_ret[t] = r5[t] - market_r5[t]
    label[t]      = 1 if excess_ret > 0, 0 if < 0, <NA> if exactly 0 (tie)

A window is valid only if the ticker has a row on every session t..t+5, no row in
the window is a bad_bar, and adj_close is present at both ends. Nothing is filled
and no gap is bridged. Dates with fewer than MIN_TICKERS_PER_DATE valid tickers get
no label.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LABEL_HORIZON, MARKET_BENCHMARK, MIN_TICKERS_PER_DATE, SPLITS
from .trading_calendar import sessions_between

LABEL_COLUMNS = ["ticker", "date", "target_date", "ret", "r5", "market_r5", "excess_ret", "label"]
BENCHMARKS = ("mean", "median")

# Columns that must never be model inputs (contract 3.4 rules 6-7).
# Forward-looking: computed from data after t (label_frame mixes these with the
# feature-safe `ret`, so a careless join could pull them into features).
FUTURE_COLUMNS = frozenset(
    {"target_date", "r5", "market_r5", "excess_ret", "label", "status", "n_valid", "split"}
)
# Survivorship / future membership: known only because the stock is in today's index.
MEMBERSHIP_COLUMNS = frozenset(
    {"yf_symbol", "symbol", "name", "sector", "sub_industry", "headquarters", "date_added", "cik", "founded"}
)


def check_feature_columns(columns) -> None:
    """Raise ValueError if any column is forward-looking or a membership attribute."""
    bad = sorted(set(columns) & (FUTURE_COLUMNS | MEMBERSHIP_COLUMNS))
    if bad:
        raise ValueError(f"forbidden feature columns (future or membership information): {bad}")


def _prepare(prices: pd.DataFrame) -> pd.DataFrame:
    """Sorted copy with each row's NYSE session number (-1 if the date is not a session)."""
    df = prices[["ticker", "date", "adj_close", "bad_bar"]].copy()
    df["date"] = pd.to_datetime(df["date"]).astype("datetime64[ns]").dt.normalize()
    df["bad_bar"] = df["bad_bar"].astype(bool)
    df = df.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    sessions = sessions_between(df["date"].min(), df["date"].max() + pd.Timedelta(days=30))
    df["session"] = sessions.get_indexer(pd.DatetimeIndex(df["date"]))
    return df


def _window_return(df: pd.DataFrame, k: int) -> tuple[pd.Series, pd.Series]:
    """Return over k sessions (k > 0: t -> t+k, forward; k < 0: t-|k| -> t, backward).

    Valid only if the ticker has rows on all |k|+1 sessions, none is a bad_bar, and
    both end closes are present. Returns (return, date at the other end).
    """
    g = df.groupby("ticker", sort=False)
    m = abs(k)
    other_session = g["session"].shift(-k)
    other_close = g["adj_close"].shift(-k)
    other_date = g["date"].shift(-k)

    bad = df["bad_bar"].astype(int)
    csum = bad.groupby(df["ticker"], sort=False).cumsum()
    shifted_csum = csum.groupby(df["ticker"], sort=False).shift(-k)
    if k > 0:  # rows t..t+k
        bad_in_window = shifted_csum - csum + bad
        span_ok = (other_session - df["session"]) == m
    else:  # rows t-m..t
        shifted_bad = bad.groupby(df["ticker"], sort=False).shift(-k)
        bad_in_window = csum - shifted_csum + shifted_bad
        span_ok = (df["session"] - other_session) == m

    valid = (
        span_ok  # consecutive sessions: m steps of strictly increasing rows spanning m sessions
        & (df["session"] >= 0)
        & (bad_in_window == 0)
        & df["adj_close"].notna()
        & other_close.notna()
    )
    ret = (other_close / df["adj_close"] - 1) if k > 0 else (df["adj_close"] / other_close - 1)
    return ret.where(valid), other_date.where(valid)


def _relative_to_market(df: pd.DataFrame, r: pd.Series, min_tickers: int, benchmark: str):
    """(market, excess, n_valid) per row, NaN where r is invalid or the date is sparse."""
    if benchmark not in BENCHMARKS:
        raise ValueError(f"benchmark must be one of {BENCHMARKS}, got {benchmark!r}")
    by_date = r.groupby(df["date"])
    n_valid = by_date.transform("count")
    market = by_date.transform(benchmark)
    ok = r.notna() & (n_valid >= min_tickers)
    return market.where(ok), (r - market).where(ok), n_valid


def label_frame(
    prices: pd.DataFrame, min_tickers: int = MIN_TICKERS_PER_DATE, benchmark: str = MARKET_BENCHMARK
) -> pd.DataFrame:
    """Every input row with label columns plus `status` and `n_valid`.

    status: "labelled" (label 0/1), "tie" (excess exactly 0), "invalid_window"
    (no valid t..t+5 window), "sparse_date" (fewer than min_tickers valid tickers on t).
    """
    df = _prepare(prices)
    df["ret"], _ = _window_return(df, -1)
    df["r5"], df["target_date"] = _window_return(df, LABEL_HORIZON)
    df["market_r5"], df["excess_ret"], df["n_valid"] = _relative_to_market(df, df["r5"], min_tickers, benchmark)

    label = np.select([df["excess_ret"] > 0, df["excess_ret"] < 0], [1, 0], default=-1)
    df["label"] = pd.array(label, dtype="Int8")
    df.loc[df["label"] == -1, "label"] = pd.NA

    df["status"] = np.select(
        [df["r5"].isna(), df["excess_ret"].isna(), df["label"].isna()],
        ["invalid_window", "sparse_date", "tie"],
        default="labelled",
    )
    df.loc[df["r5"].isna(), "target_date"] = pd.NaT
    return df


def build_labels(
    prices: pd.DataFrame, min_tickers: int = MIN_TICKERS_PER_DATE, benchmark: str = MARKET_BENCHMARK
) -> pd.DataFrame:
    """Rows with a valid label or a tie, columns LABEL_COLUMNS, sorted by ticker, date."""
    frame = label_frame(prices, min_tickers, benchmark)
    kept = frame[frame["status"].isin(["labelled", "tie"])]
    return kept[LABEL_COLUMNS].reset_index(drop=True)


def trailing_excess(
    prices: pd.DataFrame,
    window: int = LABEL_HORIZON,
    min_tickers: int = MIN_TICKERS_PER_DATE,
    benchmark: str = MARKET_BENCHMARK,
) -> pd.DataFrame:
    """past5_excess: trailing `window`-session return minus the market over the same window.

    Uses only rows dated <= t (same validity rules as the label, applied backward).
    Returns columns ticker, date, past5_excess.
    """
    df = _prepare(prices)
    past, _ = _window_return(df, -window)
    _, excess, _ = _relative_to_market(df, past, min_tickers, benchmark)
    return pd.DataFrame({"ticker": df["ticker"], "date": df["date"], "past5_excess": excess})


def assign_split(frame: pd.DataFrame) -> pd.Series:
    """Split name per row, or None when purged/outside.

    A row belongs to a split only if both its as_of_date (`date`) and its
    `target_date` (t+5) fall inside the split's range.
    """
    split = pd.Series(None, index=frame.index, dtype="object")
    for name, (start, end) in SPLITS.items():
        lo, hi = pd.Timestamp(start), pd.Timestamp(end)
        inside = frame["date"].between(lo, hi) & frame["target_date"].between(lo, hi)
        split[inside] = name
    return split
