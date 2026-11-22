"""Versioned, close-based indicators; calculate before trimming the display window."""

from datetime import date
from math import fsum
from typing import Literal

from pydantic import BaseModel, Field

from app.market import SESSION_LIMITS, History, HistoryRange

CALCULATION_LIMIT = 10000
SMA_PERIOD = 20
RSI_PERIOD = 14


class IndicatorPoint(BaseModel):
    date: date
    sma_20: float | None
    rsi_14: float | None = Field(ge=0, le=100)


class IndicatorHistory(BaseModel):
    symbol: str
    name: str
    source: str
    source_url: str
    mode: Literal["historical_fixture", "historical_snapshot"]
    adjustment: str
    snapshot_id: str
    as_of: date
    range: HistoryRange
    session_limit: int
    has_earlier: bool
    calculation_start: date
    calculation_sessions: int
    calculation_limit: int = CALCULATION_LIMIT
    calculation_has_earlier: bool
    methodology: Literal["close-sma20-wilder-rsi14-v1"] = "close-sma20-wilder-rsi14-v1"
    points: list[IndicatorPoint]


def calculate_indicators(
    history: History, range_value: HistoryRange
) -> IndicatorHistory:
    """Use ordered stored sessions, including gaps; never invent missing bars.

    RSI seeds from the first 14 changes, then uses Wilder's 1/14 smoothing.
    All-flat prices have RSI 50 by our explicit convention (not universal).
    The caller provides the same bounded input window regardless of display range.
    """
    closes = [bar.close for bar in history.bars]
    points = []
    average_gain = average_loss = 0.0
    for index, bar in enumerate(history.bars):
        rsi = None
        if 0 < index <= RSI_PERIOD:
            change = closes[index] - closes[index - 1]
            average_gain += max(change, 0.0) / RSI_PERIOD
            average_loss += max(-change, 0.0) / RSI_PERIOD
        elif index > RSI_PERIOD:
            change = closes[index] - closes[index - 1]
            average_gain = (
                average_gain * (RSI_PERIOD - 1) + max(change, 0.0)
            ) / RSI_PERIOD
            average_loss = (
                average_loss * (RSI_PERIOD - 1) + max(-change, 0.0)
            ) / RSI_PERIOD
        if index >= RSI_PERIOD:
            total = average_gain + average_loss
            rsi = 50.0 if total == 0 else 100.0 * (average_gain / total)
        sma = (
            fsum(closes[index + 1 - SMA_PERIOD : index + 1]) / SMA_PERIOD
            if index >= SMA_PERIOD - 1
            else None
        )
        points.append(IndicatorPoint(date=bar.date, sma_20=sma, rsi_14=rsi))

    limit = SESSION_LIMITS[range_value]
    return IndicatorHistory(
        symbol=history.symbol,
        name=history.name,
        source=history.source,
        source_url=history.source_url,
        mode=history.mode,
        adjustment=history.adjustment,
        snapshot_id=history.snapshot_id,
        as_of=history.as_of,
        range=range_value,
        session_limit=limit,
        has_earlier=history.has_earlier or len(points) > limit,
        calculation_start=history.bars[0].date,
        calculation_sessions=len(points),
        calculation_has_earlier=history.has_earlier,
        points=points[-limit:],
    )
