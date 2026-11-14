"""Download daily bars for every ticker in tickers.csv via yfinance.

Usage (from ml/):
    python -m stocksight_data.download              # resume: skip up-to-date files
    python -m stocksight_data.download --force      # re-download everything
    python -m stocksight_data.download --tickers AAPL MSFT

Notes on what's stored (auto_adjust=False):
  * open/high/low/close are Yahoo's *split-adjusted* prices (Yahoo back-adjusts
    splits but not dividends), not the literal historical prints.
  * adj_close is additionally dividend-adjusted (total-return style).
  * dividends / stock_splits are the corporate-action events on each date.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from . import universe
from .config import (
    DATA_DIR,
    MANIFEST_FILE,
    PRICE_COLUMNS,
    PRICES_DIR,
    START_DATE,
    TICKERS_FILE,
    WIKIPEDIA_URL,
)
from .trading_calendar import last_completed_session, settled_at

PRICE_FIELDS = ["open", "high", "low", "close", "adj_close"]
# Retry schedule: (batch size, seconds to wait before the round).
DEFAULT_ROUNDS = [(50, 0), (10, 10), (1, 30), (1, 90)]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def price_path(ticker: str):
    return PRICES_DIR / f"{ticker}.parquet"


def load_universe() -> pd.DataFrame:
    if not TICKERS_FILE.exists():
        print("tickers.csv not found; fetching the S&P 500 list first.")
        universe.save_universe()
    return pd.read_csv(TICKERS_FILE)


def previous_entries() -> dict:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text()).get("tickers", {})
    return {}


def is_provisional(last_date: pd.Timestamp, fetched_at: str | None) -> bool:
    """True if the last bar was fetched before Yahoo had settled it."""
    if not fetched_at:
        return True
    return pd.Timestamp(fetched_at) < settled_at(last_date)


def is_up_to_date(ticker: str, end: pd.Timestamp, fetched_at: str | None) -> bool:
    path = price_path(ticker)
    if not path.exists():
        return False
    try:
        dates = pd.read_parquet(path, columns=["date"])["date"]
    except Exception:
        return False  # unreadable/corrupt file -> download again
    if len(dates) == 0 or dates.max() < end:
        return False
    # Reaches the target date, but re-fetch if that last bar was still settling.
    return not is_provisional(dates.max(), fetched_at)


def _normalise(sub: pd.DataFrame, ticker: str, end: pd.Timestamp) -> pd.DataFrame:
    sub = sub.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))
    for col in PRICE_COLUMNS[2:]:
        if col not in sub.columns:
            sub[col] = pd.NA
    idx = pd.DatetimeIndex(sub.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    sub.index = idx.normalize()
    # Multi-ticker downloads align on a shared date index, so a ticker that
    # listed in 2015 gets all-NaN rows before then. Those rows are an artifact
    # of batching, not real data, so drop them. Partially-missing rows are kept
    # (the check step reports them).
    sub = sub.dropna(subset=PRICE_FIELDS, how="all")
    # Never keep a bar for a session that hasn't closed yet.
    sub = sub[sub.index <= end]
    out = sub.reset_index(names="date")
    out.columns.name = None
    out["ticker"] = ticker
    out["volume"] = out["volume"].astype("Float64").round().astype("Int64")
    for col in PRICE_FIELDS + ["dividends", "stock_splits"]:
        out[col] = out[col].astype("float64")
    return out[PRICE_COLUMNS]


class _CaptureYFLogs(logging.Handler):
    """Collect yfinance's per-ticker error log lines so they land in the manifest."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())

    def reason_for(self, ticker: str) -> str | None:
        # yfinance formats these as "$TICKER: ..." or "['TICKER']: ...".
        for msg in reversed(self.messages):
            for prefix in (f"${ticker}: ", f"['{ticker}']: "):
                if prefix in msg:
                    return msg.split(prefix, 1)[1].strip().splitlines()[0]
        return None


def download_batch(
    tickers: list[str], end: pd.Timestamp
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Return ({ticker: frame}, {ticker: error}) for one yf.download call."""
    errors: dict[str, str] = {}
    yf_logger = logging.getLogger("yfinance")
    capture = _CaptureYFLogs()
    yf_logger.addHandler(capture)
    yf_logger.propagate = False  # keep the console readable; reasons go to the manifest
    try:
        raw = yf.download(
            tickers,
            start=START_DATE,
            end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),  # end is exclusive
            interval="1d",
            auto_adjust=False,
            actions=True,
            group_by="ticker",
            threads=True,
            progress=False,
            timeout=30,
        )
    except Exception as exc:  # network error, rate limit, ...
        msg = f"{type(exc).__name__}: {exc}"
        return {}, {t: msg for t in tickers}
    finally:
        yf_logger.removeHandler(capture)

    frames: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        return {}, {t: capture.reason_for(t) or "empty response" for t in tickers}
    if not isinstance(raw.columns, pd.MultiIndex):  # single-ticker shape
        raw.columns = pd.MultiIndex.from_product([[tickers[0]], raw.columns])
    available = set(raw.columns.get_level_values(0))
    for t in tickers:
        if t not in available:
            errors[t] = capture.reason_for(t) or "ticker missing from response"
            continue
        df = _normalise(raw[t].copy(), t, end)
        if df.empty:
            errors[t] = capture.reason_for(t) or "no rows returned"
        else:
            frames[t] = df
    return frames, errors


def save_frame(ticker: str, df: pd.DataFrame) -> None:
    path = price_path(ticker)
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)  # atomic: an interrupted run never leaves half a file


def run(tickers: list[str], end: pd.Timestamp, force: bool) -> tuple[dict, dict, list]:
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    prev = previous_entries()
    skipped = [] if force else [
        t for t in tickers if is_up_to_date(t, end, prev.get(t, {}).get("fetched_at"))
    ]
    pending = [t for t in tickers if t not in set(skipped)]
    print(f"{len(tickers)} tickers | {len(skipped)} already up to date | {len(pending)} to download")

    fetched: dict[str, str] = {}
    errors: dict[str, str] = {}
    for round_no, (batch_size, wait) in enumerate(DEFAULT_ROUNDS, start=1):
        if not pending:
            break
        if wait:
            print(f"Round {round_no}: retrying {len(pending)} tickers after {wait}s backoff")
            time.sleep(wait)
        else:
            print(f"Round {round_no}: {len(pending)} tickers in batches of {batch_size}")
        failed_this_round: list[str] = []
        for i in range(0, len(pending), batch_size):
            batch = pending[i : i + batch_size]
            frames, errs = download_batch(batch, end)
            for t, df in frames.items():
                save_frame(t, df)
                fetched[t] = utc_now()
                errors.pop(t, None)
            errors.update(errs)
            failed_this_round.extend(errs)
            done = min(i + batch_size, len(pending))
            print(f"  {done}/{len(pending)} done, {len(failed_this_round)} failed so far", flush=True)
        pending = failed_this_round
    return fetched, {t: errors[t] for t in pending}, skipped


def file_stats(ticker: str) -> dict | None:
    path = price_path(ticker)
    if not path.exists():
        return None
    dates = pd.read_parquet(path, columns=["date"])["date"]
    return {
        "rows": int(len(dates)),
        "first_date": dates.min().strftime("%Y-%m-%d") if len(dates) else None,
        "last_date": dates.max().strftime("%Y-%m-%d") if len(dates) else None,
        "file": str(path.relative_to(DATA_DIR)).replace("\\", "/"),
    }


def write_manifest(universe_df: pd.DataFrame, end: pd.Timestamp, fetched: dict, failed: dict) -> dict:
    previous = previous_entries()

    entries: dict[str, dict] = {}
    for t in universe_df["yf_symbol"]:
        stats = file_stats(t)
        if t in failed:
            entries[t] = {"status": "failed", "error": failed[t]}
            if stats:  # an older file still exists; keep its stats for reference
                entries[t]["stale_file"] = stats
        elif stats:
            fetched_at = fetched.get(t) or previous.get(t, {}).get("fetched_at")
            entries[t] = {
                "status": "ok",
                "fetched_at": fetched_at,
                **stats,
                "last_bar_provisional": is_provisional(pd.Timestamp(stats["last_date"]), fetched_at),
            }
        else:
            entries[t] = {"status": "missing"}

    ok = [e for e in entries.values() if e["status"] == "ok"]
    in_universe = set(universe_df["yf_symbol"])
    orphans = sorted(p.stem for p in PRICES_DIR.glob("*.parquet") if p.stem not in in_universe)
    manifest = {
        "last_run_at": utc_now(),
        "source": "Yahoo Finance via yfinance",
        "yfinance_version": yf.__version__,
        "universe_source": WIKIPEDIA_URL,
        "universe_file_modified_at": datetime.fromtimestamp(
            TICKERS_FILE.stat().st_mtime, timezone.utc
        ).isoformat(timespec="seconds"),
        "request": {
            "start_date": START_DATE,
            "end_date": end.strftime("%Y-%m-%d"),
            "interval": "1d",
            "auto_adjust": False,
            "actions": True,
        },
        "summary": {
            "universe_size": len(entries),
            "ok": len(ok),
            "failed": sum(e["status"] == "failed" for e in entries.values()),
            "missing": sum(e["status"] == "missing" for e in entries.values()),
            "total_rows": sum(e["rows"] for e in ok),
            "earliest_date": min((e["first_date"] for e in ok), default=None),
            "latest_date": max((e["last_date"] for e in ok), default=None),
            "provisional_last_bar": sum(e["last_bar_provisional"] for e in ok),
        },
        "failed": {t: e["error"] for t, e in entries.items() if e["status"] == "failed"},
        "files_not_in_current_universe": orphans,
        "tickers": entries,
    }
    tmp = MANIFEST_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2))
    os.replace(tmp, MANIFEST_FILE)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="re-download even if files are up to date")
    parser.add_argument("--tickers", nargs="+", help="only these Yahoo symbols (must be in tickers.csv)")
    args = parser.parse_args()

    universe_df = load_universe()
    tickers = list(universe_df["yf_symbol"])
    if args.tickers:
        wanted = {t.upper() for t in args.tickers}
        unknown = wanted - set(tickers)
        if unknown:
            parser.error(f"not in tickers.csv: {sorted(unknown)}")
        tickers = [t for t in tickers if t in wanted]

    end = last_completed_session()
    print(f"Target range: {START_DATE} .. {end:%Y-%m-%d} (last completed NYSE session)")
    started = time.time()
    fetched, failed, _ = run(tickers, end, args.force)
    manifest = write_manifest(universe_df, end, fetched, failed)

    s = manifest["summary"]
    print(f"\nFinished in {time.time() - started:.0f}s. Manifest: {MANIFEST_FILE}")
    print(f"OK {s['ok']}/{s['universe_size']} | failed {s['failed']} | missing {s['missing']} | rows {s['total_rows']:,}")
    print(f"Date range across tickers: {s['earliest_date']} .. {s['latest_date']}")
    if s["provisional_last_bar"]:
        print(
            f"Note: {s['provisional_last_bar']} tickers' last bar was fetched <12h after the close and may "
            "still be revised by Yahoo; the next run will re-fetch them."
        )
    for t, err in manifest["failed"].items():
        print(f"  FAILED {t}: {err}")


if __name__ == "__main__":
    main()
