"""Combine the raw per-ticker files into one cleaned long table. Raw files are not modified.

Usage (from ml/):  python -m stocksight_data.clean [--end-date 2026-11-12]

Rules, applied per ticker in this order (each one's removals are counted):
  1. drop rows after --end-date (the latest raw bar may be unsettled)
  2. stale pre-listing history: if more than half of the first 252 rows have zero
     volume, the stale block ends at the first run of 252 consecutive rows with no
     zero-volume rows and the ticker starts there (constants in config.py). Later
     zero-volume rows never trigger a trim. A ticker not in STALE_REVIEWED_TICKERS
     that triggers this rule fails the run before anything is written.
  3. drop leading rows with adj_close < TINY_PRICE (only from the start, never mid-history)
  4. EXCLUSIONS (config.py): set that bar's prices to NaN and bad_bar=True
  4b. remaining zero/missing-volume rows: flat bars (O==H==L==C) get prices NaN and
     bad_bar=True; bars whose prices vary keep their prices and get volume NaN
  5. drop tickers with fewer than MIN_HISTORY_ROWS rows left

bad_bar rows are kept so date gaps stay visible. Downstream code must treat any
return/feature that touches one as invalid (see the bad_bar note in config.py).

Writes data/clean/prices_clean.parquet (sorted by ticker, date; raw columns + bad_bar)
and data/clean/clean_log.json.
Sanity checks are enforced: if any fails, the log is written with status "failed",
the Parquet file is not, and the command exits with an AssertionError.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .config import (
    CLEAN_DIR,
    CLEAN_FILE,
    CLEAN_LOG_FILE,
    DEFAULT_CLEAN_END_DATE,
    EXCLUSIONS,
    MIN_HISTORY_ROWS,
    PRICE_COLUMNS,
    PRICES_DIR,
    STALE_DETECT_ROWS,
    STALE_CLEAN_RUN_ROWS,
    STALE_REVIEWED_TICKERS,
    STALE_ZERO_SHARE,
    TICKERS_FILE,
    TINY_PRICE,
)

PRICE_FIELDS = ["open", "high", "low", "close", "adj_close"]
OUTPUT_COLUMNS = PRICE_COLUMNS + ["bad_bar"]


def _leading_trim(keep_from: pd.Series) -> int:
    """Number of leading rows before the first True (all rows if none is True)."""
    values = keep_from.to_numpy()
    return int(values.argmax()) if values.any() else len(values)


def clean_ticker(
    df: pd.DataFrame, end: pd.Timestamp, exclusions: dict[pd.Timestamp, str]
) -> tuple[pd.DataFrame, dict]:
    """Apply rules 1-4b to one ticker. Returns (cleaned frame, per-rule counts)."""
    counts: dict[str, object] = {}
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    df["bad_bar"] = False

    # 1. cutoff
    after = df["date"] > end
    counts["end_date"] = int(after.sum())
    df = df[~after].reset_index(drop=True)

    # 2. stale pre-listing history, judged only on the early block
    zero = ~(df["volume"].fillna(0) > 0)
    early_share = float(zero.iloc[:STALE_DETECT_ROWS].mean()) if len(df) else 0.0
    n = 0
    if early_share > STALE_ZERO_SHARE:
        # clean_run[i] is True when rows i .. i+STALE_CLEAN_RUN_ROWS-1 all exist and
        # none has zero volume. The stale block ends at the first such row; if no
        # such run exists, the whole history is stale (rule 5 then drops the ticker).
        zeros_ahead = zero[::-1].rolling(STALE_CLEAN_RUN_ROWS).sum()[::-1]
        clean_run = zeros_ahead.eq(0)
        n = int(clean_run.to_numpy().argmax()) if clean_run.any() else len(df)
        counts["stale_detail"] = {
            "early_zero_share": round(early_share, 3),
            "new_start": f"{df['date'].iloc[n]:%Y-%m-%d}" if n < len(df) else None,
            "zero_volume_rows_left": int(zero.iloc[n:].sum()),
        }
    counts["stale_history"] = n
    df = df.iloc[n:].reset_index(drop=True)

    # 3. leading tiny split-adjusted prices (NaN counts as "not tiny" so we never
    #    trim past a row we can't judge)
    n = _leading_trim(~(df["adj_close"] < TINY_PRICE))
    counts["leading_tiny_price"] = n
    df = df.iloc[n:].reset_index(drop=True)

    counts["tiny_price_rows_left"] = int((df["adj_close"] < TINY_PRICE).sum())

    # 4. known-bad bars -> NaN prices, row kept
    applied, missing = [], []
    for date, _reason in exclusions.items():
        hit = df["date"] == date
        if hit.any():
            df.loc[hit, PRICE_FIELDS] = np.nan
            df.loc[hit, "bad_bar"] = True
            applied.append(f"{date:%Y-%m-%d}")
        else:
            missing.append(f"{date:%Y-%m-%d}")
    counts["excluded_bars"] = applied
    counts["exclusions_not_found"] = missing

    # 4b. remaining zero/missing-volume rows (excluded bars already handled)
    zero = ~(df["volume"].fillna(0) > 0) & ~df["bad_bar"]
    flat = (df["open"] == df["high"]) & (df["high"] == df["low"]) & (df["low"] == df["close"])
    flat_zero = zero & flat
    varying_zero = zero & ~flat
    df.loc[flat_zero, PRICE_FIELDS] = np.nan
    df.loc[flat_zero, "bad_bar"] = True
    df.loc[varying_zero, "volume"] = pd.NA
    counts["flat_no_trade_bars"] = int(flat_zero.sum())
    counts["zero_volume_set_nan"] = int(varying_zero.sum())
    return df, counts


def validate(df: pd.DataFrame, end: pd.Timestamp) -> dict[str, dict]:
    """Return {check_name: details} for every failed check (empty dict = all passed)."""
    failures: dict[str, dict] = {}

    def fail(name: str, rows: pd.DataFrame) -> None:
        failures[name] = {
            "rows": int(len(rows)),
            "tickers": rows["ticker"].value_counts().to_dict(),
            "examples": [f"{t} {d:%Y-%m-%d}" for t, d in zip(rows["ticker"][:5], rows["date"][:5])],
        }

    dup = df.duplicated(["ticker", "date"], keep=False)
    if dup.any():
        fail("duplicate_ticker_date", df[dup])

    prev_same = df["ticker"].eq(df["ticker"].shift())
    not_increasing = prev_same & ~(df["date"] > df["date"].shift())
    if not_increasing.any():
        fail("dates_not_strictly_increasing", df[not_increasing])

    if (df["date"] > end).any():
        fail("date_after_cutoff", df[df["date"] > end])

    # Every row with real prices has volume > 0 or volume NaN.
    real_prices = ~df["bad_bar"]
    bad_vol = real_prices & df["volume"].notna() & ~(df["volume"].fillna(0) > 0)
    if bad_vol.any():
        fail("non_positive_volume", df[bad_vol])

    # Contract for the next step: prices are NaN exactly on bad_bar rows.
    any_nan = df[PRICE_FIELDS].isna().any(axis=1)
    all_nan = df[PRICE_FIELDS].isna().all(axis=1)
    mismatch = (df["bad_bar"] & ~all_nan) | (~df["bad_bar"] & any_nan)
    if mismatch.any():
        fail("bad_bar_vs_nan_prices_mismatch", df[mismatch])

    sizes = df.groupby("ticker").size()
    short = sizes[sizes < MIN_HISTORY_ROWS]
    if len(short):
        failures["ticker_below_min_rows"] = {"tickers": short.to_dict()}
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--end-date", default=DEFAULT_CLEAN_END_DATE, help="last date to keep (inclusive)")
    args = parser.parse_args()
    end = pd.Timestamp(args.end_date).normalize()

    exclusions: dict[str, dict[pd.Timestamp, str]] = {}
    for ticker, date, reason in EXCLUSIONS:
        exclusions.setdefault(ticker, {})[pd.Timestamp(date)] = reason

    tickers = list(pd.read_csv(TICKERS_FILE)["yf_symbol"])
    missing_files = [t for t in tickers if not (PRICES_DIR / f"{t}.parquet").exists()]

    rows_before = 0
    count_keys = [
        "end_date",
        "stale_history",
        "leading_tiny_price",
        "tiny_price_rows_left",
        "flat_no_trade_bars",
        "zero_volume_set_nan",
    ]
    per_rule: dict[str, dict[str, int]] = {k: {} for k in count_keys}
    stale_detail: dict[str, dict] = {}
    excluded_applied: dict[str, list[str]] = {}
    excluded_not_found: dict[str, list[str]] = {}
    frames: dict[str, pd.DataFrame] = {}
    for t in tickers:
        if t in missing_files:
            continue
        raw = pd.read_parquet(PRICES_DIR / f"{t}.parquet")
        rows_before += len(raw)
        cleaned, counts = clean_ticker(raw, end, exclusions.get(t, {}))
        for key in count_keys:
            if counts[key]:
                per_rule[key][t] = counts[key]
        if "stale_detail" in counts:
            stale_detail[t] = {"rows_removed": counts["stale_history"], **counts["stale_detail"]}
        if counts["excluded_bars"]:
            excluded_applied[t] = counts["excluded_bars"]
        if counts["exclusions_not_found"]:
            excluded_not_found[t] = counts["exclusions_not_found"]
        frames[t] = cleaned

    # 5. minimum history (counted on rows kept, bad_bar rows included)
    dropped_short = {t: len(f) for t, f in frames.items() if len(f) < MIN_HISTORY_ROWS}
    kept = [f for t, f in frames.items() if t not in dropped_short and len(f)]
    out = pd.concat(kept, ignore_index=True)[OUTPUT_COLUMNS]
    out["bad_bar"] = out["bad_bar"].astype(bool)
    out = out.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    failures = validate(out, end)
    unreviewed = sorted(set(stale_detail) - STALE_REVIEWED_TICKERS)
    if unreviewed:
        # A new ticker triggered the stale-history trim: stop so a human can review it.
        failures["unreviewed_stale_trim"] = {"tickers": {t: stale_detail[t] for t in unreviewed}}

    def rule_entry(counts: dict[str, int], key: str = "rows_removed", **extra) -> dict:
        ordered = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
        return {key: sum(counts.values()), "tickers_affected": len(counts), "by_ticker": ordered, **extra}

    log = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "failed" if failures else "ok",
        "end_date": f"{end:%Y-%m-%d}",
        "thresholds": {
            "tiny_price": TINY_PRICE,
            "min_history_rows": MIN_HISTORY_ROWS,
            "stale_detect_rows": STALE_DETECT_ROWS,
            "stale_zero_share": STALE_ZERO_SHARE,
            "stale_clean_run_rows": STALE_CLEAN_RUN_ROWS,
            "stale_reviewed_tickers": sorted(STALE_REVIEWED_TICKERS),
        },
        "before": {"tickers": len(frames), "rows": rows_before},
        "after": {
            "tickers": int(out["ticker"].nunique()),
            "rows": int(len(out)),
            "bad_bar_rows": int(out["bad_bar"].sum()),
            "rows_with_volume_nan": int(out["volume"].isna().sum()),
        },
        "missing_raw_files": missing_files,
        "rules": {
            "1_end_date": rule_entry(per_rule["end_date"]),
            "2_stale_history": rule_entry(per_rule["stale_history"], trimmed=stale_detail),
            "3_leading_tiny_price": rule_entry(
                per_rule["leading_tiny_price"],
                tiny_rows_left_mid_history=rule_entry(per_rule["tiny_price_rows_left"], key="rows"),
            ),
            "4_exclusions": {
                "bars_nulled": sum(len(v) for v in excluded_applied.values()),
                "applied": excluded_applied,
                "not_found": excluded_not_found,
                "reasons": {f"{t} {d}": r for t, d, r in EXCLUSIONS},
            },
            # Counted before rule 5, so tickers later dropped for short history are included.
            "4b_zero_volume_bars": {
                "flat_bars_set_to_nan": rule_entry(per_rule["flat_no_trade_bars"], key="rows"),
                "varying_price_volume_set_to_nan": rule_entry(per_rule["zero_volume_set_nan"], key="rows"),
            },
            "5_min_history": {
                "tickers_dropped": len(dropped_short),
                "rows_removed": sum(dropped_short.values()),
                "dropped": dropped_short,
            },
        },
        "check_failures": failures,
        "output_file": str(CLEAN_FILE) if not failures else None,
    }

    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_LOG_FILE.write_text(json.dumps(log, indent=2))
    print_summary(log)
    if failures:
        raise AssertionError(
            f"Sanity checks failed: {', '.join(failures)}. Nothing written to {CLEAN_FILE.name}; "
            f"details in {CLEAN_LOG_FILE}"
        )

    tmp = CLEAN_FILE.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    os.replace(tmp, CLEAN_FILE)
    print(f"\nWrote {CLEAN_FILE} ({len(out):,} rows, {out['ticker'].nunique()} tickers)")


def _top(by_ticker: dict, n: int = 8) -> str:
    return ", ".join(f"{t} {v}" for t, v in list(by_ticker.items())[:n])


def print_summary(log: dict) -> None:
    b, a, r = log["before"], log["after"], log["rules"]
    print(f"Cutoff {log['end_date']} | status: {log['status']}")
    print(f"Before: {b['tickers']} tickers, {b['rows']:,} rows")
    print(
        f"After:  {a['tickers']} tickers, {a['rows']:,} rows  (removed {b['rows'] - a['rows']:,}); "
        f"bad_bar rows {a['bad_bar_rows']:,}, volume NaN rows {a['rows_with_volume_nan']:,}"
    )
    for name in ("1_end_date", "2_stale_history", "3_leading_tiny_price"):
        e = r[name]
        print(f"  rule {name}: -{e['rows_removed']:,} rows in {e['tickers_affected']} tickers  [{_top(e['by_ticker'])}]")
        if name == "2_stale_history":
            for t, d in e["trimmed"].items():
                print(
                    f"    {t}: early zero share {d['early_zero_share']:.0%}, new start {d['new_start']}, "
                    f"zero-volume rows still after it {d['zero_volume_rows_left']}"
                )
    left = r["3_leading_tiny_price"]["tiny_rows_left_mid_history"]
    print(f"    tiny-price rows left mid-history: {left['rows']} [{_top(left['by_ticker'])}]")
    ex = r["4_exclusions"]
    print(f"  rule 4_exclusions: {ex['bars_nulled']} bars set to NaN {ex['applied']}; not found: {ex['not_found'] or 'none'}")
    fz = r["4b_zero_volume_bars"]["flat_bars_set_to_nan"]
    vz = r["4b_zero_volume_bars"]["varying_price_volume_set_to_nan"]
    print(f"  rule 4b flat no-trade bars -> NaN prices: {fz['rows']:,} rows in {fz['tickers_affected']} tickers [{_top(fz['by_ticker'])}]")
    print(f"  rule 4b varying prices, zero volume -> volume NaN: {vz['rows']:,} rows in {vz['tickers_affected']} tickers [{_top(vz['by_ticker'])}]")
    m = r["5_min_history"]
    print(f"  rule 5_min_history: dropped {m['tickers_dropped']} tickers (-{m['rows_removed']:,} rows) {m['dropped']}")
    for name, f in log["check_failures"].items():
        tick = f.get("tickers", {})
        print(f"  CHECK FAILED {name}: {f.get('rows', '')} rows; {dict(list(tick.items())[:10])}")


if __name__ == "__main__":
    main()
