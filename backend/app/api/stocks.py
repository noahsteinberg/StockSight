"""Deterministic historical data adapter; replace behind this boundary in M2."""

import csv
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(tags=["stocks"])


class Stock(BaseModel):
    symbol: str
    name: str


class Bar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class History(BaseModel):
    symbol: str
    name: str
    source: str
    source_url: str
    mode: Literal["historical_fixture"] = "historical_fixture"
    adjustment: str = "Unadjusted OHLC; historical values are not current quotes"
    as_of: date
    range: str
    bars: list[Bar]


@lru_cache(maxsize=1)
def load_bars() -> tuple[Bar, ...]:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "apple-source.csv"
    with path.open(newline="", encoding="utf-8") as source:
        return tuple(
            sorted(
                (
                    Bar(
                        date=row["Date"],
                        open=float(row["AAPL.Open"]),
                        high=float(row["AAPL.High"]),
                        low=float(row["AAPL.Low"]),
                        close=float(row["AAPL.Close"]),
                        volume=int(row["AAPL.Volume"]),
                    )
                    for row in csv.DictReader(source)
                ),
                key=lambda bar: bar.date,
            )
        )


@router.get("/stocks", response_model=list[Stock])
def search_stocks(query: str = Query(default="", max_length=40)) -> list[Stock]:
    query = query.strip().upper()
    return (
        [Stock(symbol="AAPL", name="Apple Inc.")]
        if not query or query in "AAPL" or query in "APPLE INC."
        else []
    )


@router.get("/stocks/{symbol}/prices", response_model=History)
def prices(
    symbol: str,
    range: Literal["1mo", "3mo", "1y", "all"] = "3mo",
) -> History:
    if symbol.strip().upper() != "AAPL":
        raise HTTPException(
            status_code=404,
            detail={"code": "UNSUPPORTED_SYMBOL", "message": "Try AAPL."},
        )
    bars = load_bars()
    # Session counts are explicit: ranges end at the last fixture observation.
    count = {"1mo": 21, "3mo": 63, "1y": 252, "all": len(bars)}[range]
    return History(
        symbol="AAPL",
        name="Apple Inc.",
        source="Plotly historical Apple dataset",
        source_url="https://github.com/plotly/datasets/blob/master/finance-charts-apple.csv",
        as_of=bars[-1].date,
        range=range,
        bars=list(bars[-count:]),
    )
