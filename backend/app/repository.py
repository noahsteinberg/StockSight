"""Bounded reads of a canonical daily series; no provider calls in HTTP requests."""

from sqlalchemy import case, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import DailyBar, PriceSeries, StockRecord, series_revision
from app.market import SESSION_LIMITS, Bar, History, Stock
from app.stock_metadata import company_name, symbols_named


def search_database(engine: Engine, query: str, limit: int = 50) -> list[Stock]:
    with Session(engine) as session:
        statement = select(StockRecord).where(
            StockRecord.symbol.in_(select(PriceSeries.symbol))
        )
        # contains(autoescape=True) treats user %, _ and escape characters literally.
        if query:
            statement = statement.where(
                StockRecord.symbol.icontains(query, autoescape=True)
                | StockRecord.name.icontains(query, autoescape=True)
                | StockRecord.symbol.in_(symbols_named(query))
            )
        ordering = (
            (case((StockRecord.symbol == query, 0), else_=1), StockRecord.symbol)
            if query
            else (StockRecord.symbol,)
        )
        return [
            Stock(
                symbol=row.symbol, name=company_name(row.symbol, row.name) or row.name
            )
            for row in session.scalars(statement.order_by(*ordering).limit(limit))
        ]


def supported_symbol(engine: Engine, symbol: str) -> bool:
    with Session(engine) as session:
        return (
            session.scalar(select(PriceSeries.id).where(PriceSeries.symbol == symbol))
            is not None
        )


def database_history(
    engine: Engine, symbol: str, range_value: str, *, session_limit: int | None = None
) -> History | None:
    # The optional internal limit supplies a fixed calculation window for indicators.
    limit = session_limit if session_limit is not None else SESSION_LIMITS[range_value]
    with Session(engine) as session:
        # One statement binds the rows to the exact series revision that supplied
        # them, including when a writer commits between two API requests.
        rows = session.execute(
            select(PriceSeries, StockRecord.name, DailyBar)
            .select_from(PriceSeries)
            .join(StockRecord, StockRecord.symbol == PriceSeries.symbol)
            .join(DailyBar, DailyBar.series_id == PriceSeries.id)
            .where(PriceSeries.symbol == symbol)
            .order_by(DailyBar.session_date.desc())
            .limit(limit + 1)
        ).all()
        if not rows:
            return None
        series, name, _ = rows[0]
        revision = series_revision(series)
        has_earlier = len(rows) > limit
        bars = [
            Bar(
                date=row.session_date,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=row.volume,
            )
            for _, _, row in reversed(rows[:limit])
        ]
        return History(
            symbol=symbol,
            name=company_name(symbol, name) or name,
            source=series.source,
            source_url=series.source_url,
            mode=series.mode,
            last_refreshed_at=series.updated_at,
            adjustment=series.adjustment,
            snapshot_id=revision,
            as_of=bars[-1].date,
            range=range_value,
            bars=bars,
            session_limit=limit,
            has_earlier=has_earlier,
        )
