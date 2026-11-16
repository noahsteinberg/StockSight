"""Historical fixture contract shared by offline and database adapters."""

import csv
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "apple-source.csv"
SOURCE = "Plotly historical Apple dataset"
SOURCE_URL = "https://github.com/plotly/datasets/blob/master/finance-charts-apple.csv"
ADJUSTMENT = "Unadjusted OHLC; historical values are not current quotes"


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
    mode: Literal["historical_fixture", "historical_snapshot"] = "historical_fixture"
    adjustment: str = "Unadjusted OHLC; historical values are not current quotes"
    as_of: date
    range: str
    bars: list[Bar]
    session_limit: int
    has_earlier: bool


@lru_cache(maxsize=1)
def load_bars() -> tuple[Bar, ...]:
    path = FIXTURE_PATH
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
