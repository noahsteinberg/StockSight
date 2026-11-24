"""Optional Yahoo downloader; never called from public HTTP routes."""

import hashlib
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Download:
    rows: list[dict]
    provider: str
    fingerprint: str
    fetched_at: datetime


def completed_sessions(start, end, now):
    import exchange_calendars as xcals

    calendar = xcals.get_calendar(
        "XNYS", start=start - timedelta(days=7), end=end + timedelta(days=7)
    )
    return {
        stamp.date()
        for stamp in calendar.sessions_in_range(start, end)
        if calendar.session_close(stamp).to_pydatetime() + timedelta(minutes=30) <= now
    }


def exchange_today(now):
    return now.astimezone(ZoneInfo("America/New_York")).date()


def fetch_yahoo(symbol, start, end):
    import yfinance as yf

    # A fresh ticker belongs to one worker. No adjustment or automatic repair.
    error = None
    for attempt in range(3):
        try:
            ticker = yf.Ticker(symbol)
            frame = ticker.history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=False,
                back_adjust=False,
                actions=True,
                repair=False,
                keepna=True,
                timeout=20,
                raise_errors=True,
            )
            if frame.empty:
                raise ValueError("Provider returned no bars")
            metadata = ticker.get_history_metadata()
            if metadata.get("symbol") != symbol or metadata.get("currency") != "USD":
                raise ValueError("Unverified provider symbol/currency")
            if frame.index.tz is None or str(frame.index.tz) not in (
                "America/New_York",
                "US/Eastern",
            ):
                raise ValueError("Unverified exchange timezone")
            rows = []
            for stamp, row in frame.iterrows():
                values = {}
                for column, field in (
                    ("Open", "open"),
                    ("High", "high"),
                    ("Low", "low"),
                    ("Close", "close"),
                    ("Volume", "volume"),
                    ("Adj Close", "adj_close"),
                    ("Dividends", "dividends"),
                    ("Stock Splits", "stock_splits"),
                ):
                    value = row.get(column)
                    values[field] = (
                        None
                        if value is None or not math.isfinite(float(value))
                        else float(value)
                    )
                if values["volume"] is not None and values["volume"].is_integer():
                    values["volume"] = int(values["volume"])
                rows.append(
                    {"ticker": symbol, "date": stamp.date().isoformat(), **values}
                )
            encoded = json.dumps(rows, sort_keys=True, allow_nan=False).encode()
            return Download(
                rows,
                f"yfinance/{yf.__version__}",
                hashlib.sha256(encoded).hexdigest(),
                datetime.now(UTC),
            )
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep((2, 5)[attempt])
    # Keep third-party exception bodies out of logs; they may contain credentials.
    raise ValueError(f"Yahoo request failed ({type(error).__name__})") from None
