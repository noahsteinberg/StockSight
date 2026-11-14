"""Exchange-calendar helpers: which sessions exist and which one last closed."""

from __future__ import annotations

from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd

from .config import EXCHANGE, START_DATE

# Wait a bit after the official close before treating the day as final; Yahoo's
# daily bar (especially volume) keeps settling for a few minutes after 16:00 ET.
CLOSE_BUFFER = pd.Timedelta(minutes=30)
# Yahoo keeps revising the latest daily bar (high/low/volume) for hours after the
# close; we observed inconsistent OHLC 2.5h after close. A bar fetched before
# close + SETTLE_DELAY is treated as provisional and re-fetched on the next run.
SETTLE_DELAY = pd.Timedelta(hours=12)


def settled_at(session: pd.Timestamp) -> pd.Timestamp:
    """UTC time after which a session's daily bar is considered final."""
    return get_calendar().session_close(pd.Timestamp(session).normalize()) + SETTLE_DELAY


@lru_cache(maxsize=1)
def get_calendar() -> xcals.ExchangeCalendar:
    # Explicit start: exchange_calendars defaults to ~20 years back.
    return xcals.get_calendar(EXCHANGE, start=START_DATE)


def last_completed_session(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """Most recent session whose close (+buffer) is in the past, as a naive date."""
    cal = get_calendar()
    now = pd.Timestamp.now(tz="UTC") if now is None else now.tz_convert("UTC")
    # Sessions up to today's date (in New York), newest last.
    today_ny = now.tz_convert("America/New_York").normalize().tz_localize(None)
    sessions = cal.sessions_in_range(cal.first_session, min(today_ny, cal.last_session))
    for session in reversed(sessions):
        close = cal.session_close(session)  # tz-aware UTC; handles early closes
        if close + CLOSE_BUFFER <= now:
            return pd.Timestamp(session).tz_localize(None).normalize()
    raise RuntimeError("No completed session found")


def sessions_between(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    """Sessions in [start, end], clamped to the calendar's range (it ends ~1 year ahead)."""
    cal = get_calendar()
    start = max(pd.Timestamp(start), cal.first_session.tz_localize(None))
    end = min(pd.Timestamp(end), cal.last_session.tz_localize(None))
    return cal.sessions_in_range(start, end).tz_localize(None)
