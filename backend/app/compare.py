"""Common-date comparison of 2-4 supported stocks (issue #19, Phase 2).

Numerical rules (documented in docs/API.md, pending Parth's review):
- The window ends at the latest session every selected stock has stored
  (shared cutoff), so a stale stock is never mixed with newer data.
- Only dates present for every stock are used; missing dates are excluded,
  never forward-filled. The window is the last N common dates for the range.
- Each line is indexed to 100 at the first common date:
  close / first_common_close * 100. Period change is the last indexed value
  minus 100. Closes exclude dividends, so this is price change, not total return.
- A stock split inside the window is checked against the stored closes. If the
  close moves by roughly the split factor that day, the history is treated as
  unadjusted there and the period change is withheld.
"""

import re
from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import DailyBar, PriceSeries, StockRecord, series_revision
from app.explore import verified_name
from app.market import SESSION_LIMITS

MIN_SYMBOLS = 2
MAX_SYMBOLS = 4
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.^=-]{0,15}$")
# Extra stored sessions read per stock so the common window can still reach the
# requested length when the selected histories have different missing dates.
OVERLAP_MARGIN = 40
# A split is "unadjusted" when the close moves within 25% of the split factor.
SPLIT_TOLERANCE = 0.25


class SplitEvent(BaseModel):
    date: date
    ratio: float
    price_adjusted: bool


class CompareStock(BaseModel):
    symbol: str
    name: str | None
    as_of: date
    last_close: float
    series_revision: str
    start_close: float | None
    end_close: float | None
    period_change_pct: float | None
    metric_status: Literal["ok", "insufficient_overlap", "split_unadjusted"]
    split_events: list[SplitEvent]
    indexed: list[float]


class ComparePage(BaseModel):
    range: str
    requested_sessions: int
    common_sessions: int
    start: date | None
    end: date | None
    aligned_to_shared_cutoff: bool
    dates: list[date]
    stocks: list[CompareStock]


def parse_symbols(raw: str) -> list[str]:
    symbols: list[str] = []
    for part in raw.split(","):
        symbol = part.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    invalid = [symbol for symbol in symbols if not SYMBOL_PATTERN.match(symbol)]
    if invalid or not MIN_SYMBOLS <= len(symbols) <= MAX_SYMBOLS:
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_COMPARISON",
                "message": "Choose 2 to 4 different supported ticker symbols.",
                "invalid": invalid,
            },
        )
    return symbols


def split_events(bars, start: date, end: date) -> list[SplitEvent]:
    """Splits dated after the window start and on/before its end."""
    events = []
    for previous, bar in zip(bars, bars[1:], strict=False):
        ratio = float((bar.source_values or {}).get("stock_splits") or 0)
        if ratio <= 0 or ratio == 1 or not start < bar.session_date <= end:
            continue
        move = float(bar.close) / float(previous.close) if previous.close else 1
        unadjusted = abs(move * ratio - 1) < SPLIT_TOLERANCE
        events.append(
            SplitEvent(
                date=bar.session_date, ratio=ratio, price_adjusted=not unadjusted
            )
        )
    return events


def compare_database(
    engine: Engine, symbols: list[str], range_value: str
) -> ComparePage:
    requested = SESSION_LIMITS[range_value]
    with Session(engine) as session:
        rows = session.execute(
            select(StockRecord, PriceSeries)
            .join(PriceSeries, PriceSeries.symbol == StockRecord.symbol)
            .where(StockRecord.symbol.in_(symbols))
        ).all()
        found = {stock.symbol: (stock, series) for stock, series in rows}
        unknown = [symbol for symbol in symbols if symbol not in found]
        if unknown:
            raise HTTPException(
                404,
                detail={
                    "code": "UNSUPPORTED_SYMBOL",
                    "message": "Some symbols have no stored history.",
                    "symbols": unknown,
                },
            )
        latest: dict[str, date] = {
            symbol: day
            for symbol, day in session.execute(
                select(PriceSeries.symbol, func.max(DailyBar.session_date))
                .join(DailyBar, DailyBar.series_id == PriceSeries.id)
                .where(PriceSeries.symbol.in_(symbols))
                .group_by(PriceSeries.symbol)
            ).all()
        }
        cutoff = min(latest.values())
        histories = {}
        for symbol in symbols:
            series = found[symbol][1]
            newest_first = session.scalars(
                select(DailyBar)
                .where(DailyBar.series_id == series.id, DailyBar.session_date <= cutoff)
                .order_by(DailyBar.session_date.desc())
                .limit(requested + OVERLAP_MARGIN)
            ).all()
            histories[symbol] = list(reversed(newest_first))
        newest = {
            symbol: session.scalars(
                select(DailyBar.close)
                .where(DailyBar.series_id == found[symbol][1].id)
                .order_by(DailyBar.session_date.desc())
                .limit(1)
            ).one()
            for symbol in symbols
        }

    common = set.intersection(
        *({bar.session_date for bar in bars} for bars in histories.values())
    )
    dates = sorted(common)[-requested:]
    enough = len(dates) >= 2
    start, end = (dates[0], dates[-1]) if dates else (None, None)

    stocks = []
    for symbol in symbols:
        stock, series = found[symbol]
        by_date = {bar.session_date: float(bar.close) for bar in histories[symbol]}
        events = (
            split_events(histories[symbol], start, end)
            if start is not None and end is not None and enough
            else []
        )
        if not enough:
            status, indexed, change = "insufficient_overlap", [], None
            first = last = None
        else:
            first, last = by_date[start], by_date[end]
            indexed = [by_date[day] / first * 100 for day in dates]
            unadjusted = any(not event.price_adjusted for event in events)
            status = "split_unadjusted" if unadjusted else "ok"
            change = None if unadjusted else indexed[-1] - 100
        stocks.append(
            CompareStock(
                symbol=symbol,
                name=verified_name(symbol, stock.name),
                as_of=latest[symbol],
                last_close=float(newest[symbol]),
                series_revision=series_revision(series),
                start_close=first,
                end_close=last,
                period_change_pct=change,
                metric_status=status,
                split_events=events,
                indexed=indexed,
            )
        )
    return ComparePage(
        range=range_value,
        requested_sessions=requested,
        common_sessions=len(dates) if enough else 0,
        start=start if enough else None,
        end=end if enough else None,
        aligned_to_shared_cutoff=len(set(latest.values())) > 1,
        dates=dates if enough else [],
        stocks=stocks,
    )


def compare_fixture(symbols: list[str]) -> ComparePage:
    """The explicit demo stores only AAPL, so any comparison has unknown symbols."""
    unknown = [symbol for symbol in symbols if symbol != "AAPL"]
    raise HTTPException(
        404,
        detail={
            "code": "UNSUPPORTED_SYMBOL",
            "message": "Some symbols have no stored history.",
            "symbols": unknown,
        },
    )
