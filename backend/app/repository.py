"""Bounded reads of a canonical daily series; no provider calls in HTTP requests."""

from sqlalchemy import case, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import DailyBar, PriceSeries, StockRecord
from app.market import Bar, History, Stock


def search_database(engine: Engine, query: str) -> list[Stock]:
    with Session(engine) as session:
        statement = select(StockRecord).where(
            StockRecord.symbol.in_(select(PriceSeries.symbol))
        )
        # contains(autoescape=True) treats user %, _ and escape characters literally.
        if query:
            statement = statement.where(
                StockRecord.symbol.icontains(query, autoescape=True)
                | StockRecord.name.icontains(query, autoescape=True)
            )
        ordering = (
            (case((StockRecord.symbol == query, 0), else_=1), StockRecord.symbol)
            if query
            else (StockRecord.symbol,)
        )
        return [
            Stock(symbol=row.symbol, name=row.name)
            for row in session.scalars(statement.order_by(*ordering).limit(50))
        ]


def database_history(engine: Engine, symbol: str, range_value: str) -> History | None:
    limit = {"1mo": 21, "3mo": 63, "1y": 252, "all": 2000}[range_value]
    with Session(engine) as session:
        series = session.scalar(select(PriceSeries).where(PriceSeries.symbol == symbol))
        if series is None:
            return None
        stock = session.get(StockRecord, symbol)
        rows = list(
            session.scalars(
                select(DailyBar)
                .where(DailyBar.series_id == series.id)
                .order_by(DailyBar.session_date.desc())
                .limit(limit + 1)
            )
        )
        has_earlier = len(rows) > limit
        rows = rows[:limit]
        bars = [
            Bar(
                date=row.session_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=row.volume,
            )
            for row in reversed(rows)
        ]
        if not bars:
            return None
        return History(
            symbol=symbol,
            name=stock.name,
            source=series.source,
            source_url=series.source_url,
            mode=series.mode,
            adjustment=series.adjustment,
            as_of=bars[-1].date,
            range=range_value,
            bars=bars,
            session_limit=limit,
            has_earlier=has_earlier,
        )
