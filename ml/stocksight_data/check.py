"""Sanity-check the downloaded price files. Reports problems; never modifies data.

Usage (from ml/):  python -m stocksight_data.check [--show N]
Writes data/sp500/check_report.json and prints a summary.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
import pandas as pd

from .config import (
    CHECK_REPORT_FILE,
    MANIFEST_FILE,
    MIN_HISTORY_ROWS,
    PRICES_DIR,
    START_DATE,
    TICKERS_FILE,
    TINY_PRICE,
)
from .trading_calendar import sessions_between

PRICE_FIELDS = ["open", "high", "low", "close", "adj_close"]
REL_TOL = 1e-4  # ignore OHLC inconsistencies smaller than 0.01% (float rounding)
EXTREME_MOVE = 0.40  # |close-to-close return| above this gets listed
BIG_GAP_SESSIONS = 5  # a run of >= this many missing sessions is a "big gap"
SHORT_HISTORY_SESSIONS = MIN_HISTORY_ROWS

# check name -> (severity, one-line description)
CHECKS = {
    "read_error": ("error", "file could not be read"),
    "empty": ("error", "file has no rows"),
    "missing_values": ("warn", "NaNs in price/volume columns"),
    "duplicate_dates": ("error", "same date appears more than once"),
    "out_of_order": ("error", "dates not strictly increasing"),
    "non_session_dates": ("warn", "rows on dates the NYSE was closed"),
    "missing_sessions": ("info", "NYSE sessions with no row between first and last date"),
    "big_gap": ("warn", f"run of >= {BIG_GAP_SESSIONS} consecutive missing sessions"),
    "non_positive_price": ("error", "price <= 0"),
    "ohlc_inconsistent": ("warn", "high below open/close/low, or low above open/close/high"),
    "adj_above_close": ("warn", "adj_close > close (adjustment factor > 1)"),
    "extreme_move": ("warn", f"|1-day close return| > {EXTREME_MOVE:.0%} (real event or bad split adj.)"),
    "zero_volume": ("info", "rows with volume == 0"),
    "flat_bar_zero_volume": ("warn", "open==high==low==close with zero volume (stale quote)"),
    "tiny_prices": ("info", f"split-adjusted close < ${TINY_PRICE} (rounding noise in returns)"),
    "late_start": ("info", "history starts after the requested start (IPO/spin-off/listing)"),
    "short_history": ("warn", f"fewer than {SHORT_HISTORY_SESSIONS} rows (~3 years)"),
    "ends_early": ("warn", "last row is before the target end date"),
}


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) index pairs of consecutive True runs."""
    runs, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(mask) - 1))
    return runs


def check_ticker(path, target_end: pd.Timestamp, first_session: pd.Timestamp) -> tuple[dict, dict]:
    issues: dict[str, object] = {}
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        return {"read_error": str(exc)}, {}
    if df.empty:
        return {"empty": True}, {}

    dates = pd.DatetimeIndex(df["date"])
    stats = {
        "rows": len(df),
        "first_date": f"{dates.min():%Y-%m-%d}",
        "last_date": f"{dates.max():%Y-%m-%d}",
    }

    # --- missing values
    na = df[PRICE_FIELDS + ["volume"]].isna().sum()
    na = {k: int(v) for k, v in na.items() if v}
    if na:
        issues["missing_values"] = na

    # --- date ordering / duplicates
    dup = dates[dates.duplicated()].unique()
    if len(dup):
        issues["duplicate_dates"] = {"count": int(len(dup)), "examples": [f"{d:%Y-%m-%d}" for d in dup[:5]]}
    if not dates.is_monotonic_increasing:
        bad = int((np.diff(dates.values).astype("int64") <= 0).sum())
        issues["out_of_order"] = {"count": bad}

    # --- calendar alignment
    udates = dates.unique().sort_values()
    sessions = sessions_between(udates.min(), udates.max())
    off = udates.difference(sessions)
    if len(off):
        issues["non_session_dates"] = {"count": int(len(off)), "examples": [f"{d:%Y-%m-%d}" for d in off[:5]]}
    missing_mask = ~sessions.isin(udates)
    if missing_mask.any():
        runs = _runs(missing_mask)
        longest = max(runs, key=lambda r: r[1] - r[0])
        issues["missing_sessions"] = {
            "count": int(missing_mask.sum()),
            "longest_run": int(longest[1] - longest[0] + 1),
            "longest_run_dates": [f"{sessions[longest[0]]:%Y-%m-%d}", f"{sessions[longest[1]]:%Y-%m-%d}"],
        }
        big = [r for r in runs if r[1] - r[0] + 1 >= BIG_GAP_SESSIONS]
        if big:
            issues["big_gap"] = [
                {"from": f"{sessions[a]:%Y-%m-%d}", "to": f"{sessions[b]:%Y-%m-%d}", "sessions": int(b - a + 1)}
                for a, b in big
            ]

    # --- price sanity (on rows that have all OHLC)
    p = df.dropna(subset=["open", "high", "low", "close"])
    nonpos = int((df[PRICE_FIELDS] <= 0).any(axis=1).sum())
    if nonpos:
        issues["non_positive_price"] = {"count": nonpos}
    hi_bad = p["high"] < p[["open", "close", "low"]].max(axis=1) * (1 - REL_TOL)
    lo_bad = p["low"] > p[["open", "close", "high"]].min(axis=1) * (1 + REL_TOL)
    bad = p[hi_bad | lo_bad]
    if len(bad):
        issues["ohlc_inconsistent"] = {"count": int(len(bad)), "examples": [f"{d:%Y-%m-%d}" for d in bad["date"][:5]]}
    adj_hi = df[df["adj_close"] > df["close"] * (1 + REL_TOL)]
    if len(adj_hi):
        issues["adj_above_close"] = {"count": int(len(adj_hi)), "examples": [f"{d:%Y-%m-%d}" for d in adj_hi["date"][:5]]}

    c = df.set_index("date")["close"]
    ret = c / c.shift(1) - 1
    ext = ret[ret.abs() > EXTREME_MOVE]
    if len(ext):
        issues["extreme_move"] = [{"date": f"{d:%Y-%m-%d}", "return": round(float(r), 4)} for d, r in ext.items()]

    zero_vol = df["volume"].fillna(-1) == 0
    if zero_vol.any():
        issues["zero_volume"] = {"count": int(zero_vol.sum())}
        flat = zero_vol & (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
        if flat.any():
            issues["flat_bar_zero_volume"] = {"count": int(flat.sum()), "examples": [f"{d:%Y-%m-%d}" for d in df.loc[flat, "date"][:5]]}

    tiny = df[df["close"] < TINY_PRICE]
    if len(tiny):
        issues["tiny_prices"] = {"count": int(len(tiny)), "min_close": round(float(df["close"].min()), 6)}

    # --- coverage
    if dates.min() > first_session:
        issues["late_start"] = stats["first_date"]
    if len(df) < SHORT_HISTORY_SESSIONS:
        issues["short_history"] = len(df)
    if dates.max() < target_end:
        issues["ends_early"] = stats["last_date"]
    return issues, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", type=int, default=8, help="example tickers to print per check")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_FILE.read_text()) if MANIFEST_FILE.exists() else {}
    target_end = pd.Timestamp(manifest.get("request", {}).get("end_date") or pd.Timestamp.today().normalize())
    universe = pd.read_csv(TICKERS_FILE)
    first_session = sessions_between(pd.Timestamp(START_DATE), pd.Timestamp(START_DATE) + pd.Timedelta(days=10))[0]

    per_ticker: dict[str, dict] = {}
    by_check: dict[str, list[str]] = defaultdict(list)
    not_downloaded = []
    for t in universe["yf_symbol"]:
        path = PRICES_DIR / f"{t}.parquet"
        if not path.exists():
            not_downloaded.append(t)
            continue
        issues, stats = check_ticker(path, target_end, first_session)
        per_ticker[t] = {**stats, "issues": issues}
        for name in issues:
            by_check[name].append(t)

    summary = {
        name: {"severity": sev, "description": desc, "tickers": len(by_check.get(name, []))}
        for name, (sev, desc) in CHECKS.items()
    }
    report = {
        "checked_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "target_end_date": f"{target_end:%Y-%m-%d}",
        "universe_size": len(universe),
        "files_checked": len(per_ticker),
        "not_downloaded": not_downloaded,
        "thresholds": {
            "extreme_move": EXTREME_MOVE,
            "big_gap_sessions": BIG_GAP_SESSIONS,
            "short_history_sessions": SHORT_HISTORY_SESSIONS,
            "tiny_price": TINY_PRICE,
            "ohlc_rel_tol": REL_TOL,
        },
        "summary": summary,
        "tickers_by_check": {k: sorted(v) for k, v in by_check.items()},
        "per_ticker": per_ticker,
    }
    CHECK_REPORT_FILE.write_text(json.dumps(report, indent=2))

    rows = [s["rows"] for s in per_ticker.values() if "rows" in s]
    print(f"Checked {len(per_ticker)}/{len(universe)} tickers, target end {target_end:%Y-%m-%d}")
    if rows:
        print(f"Rows per ticker: min {min(rows)}, median {int(np.median(rows))}, max {max(rows)}; total {sum(rows):,}")
    if not_downloaded:
        print(f"Not downloaded: {', '.join(not_downloaded)}")
    provisional = sorted(t for t, e in manifest.get("tickers", {}).items() if e.get("last_bar_provisional"))
    report["provisional_last_bar"] = provisional
    CHECK_REPORT_FILE.write_text(json.dumps(report, indent=2))
    if provisional:
        print(
            f"Provisional last bar ({target_end:%Y-%m-%d}) for {len(provisional)} tickers: fetched <12h after "
            "close, Yahoo may still revise it. Rerun download later to refresh."
        )
    print(f"\n{'check':<22}{'sev':<7}{'tickers':>8}  examples")
    for name, s in summary.items():
        hits = sorted(by_check.get(name, []))
        if not hits:
            continue
        ex = ", ".join(hits[: args.show]) + (" ..." if len(hits) > args.show else "")
        print(f"{name:<22}{s['severity']:<7}{s['tickers']:>8}  {ex}")
    clean = [t for t, v in per_ticker.items() if not v["issues"]]
    print(f"\nNo issues at all: {len(clean)} tickers.  Full details: {CHECK_REPORT_FILE}")


if __name__ == "__main__":
    main()
