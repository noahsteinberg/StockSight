"""Paginated summaries of supported stocks for the public Explore page.

Each row reads only the newest two stored closes for its series, so a page never
loads full histories, calculates indicators or calls a provider.
"""

from datetime import date

from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import DailyBar, PriceSeries, StockRecord, series_revision
from app.market import fixture_snapshot_id, load_bars

PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 50
FIXTURE_STOCK = ("AAPL", "Apple Inc.", "NASDAQ")


class ExploreItem(BaseModel):
    symbol: str
    # Imported rows can carry name=symbol and exchange=UNKNOWN placeholders;
    # those are returned as null rather than presented as verified metadata.
    name: str | None
    exchange: str | None
    last_close: float | None
    as_of: date | None
    daily_change_pct: float | None
    series_revision: str


class ExplorePage(BaseModel):
    query: str
    page: int
    page_size: int
    total_supported: int
    total_matching: int
    latest_session: date | None
    items: list[ExploreItem]


def verified_name(symbol: str, name: str | None) -> str | None:
    cleaned = (name or "").strip()
    return cleaned if cleaned and cleaned.upper() != symbol.upper() else None


def verified_exchange(exchange: str | None) -> str | None:
    cleaned = (exchange or "").strip()
    return cleaned if cleaned and cleaned.upper() != "UNKNOWN" else None


def daily_change(latest: float | None, previous: float | None) -> float | None:
    if latest is None or previous is None or previous == 0:
        return None
    return (latest / previous - 1) * 100


def _matches(query: str):
    # contains(autoescape=True) treats user %, _ and escape characters literally.
    return StockRecord.symbol.icontains(
        query, autoescape=True
    ) | StockRecord.name.icontains(query, autoescape=True)


def explore_database(
    engine: Engine, query: str, page: int, page_size: int
) -> ExplorePage:
    newest = (
        select(DailyBar)
        .where(DailyBar.series_id == PriceSeries.id)
        .order_by(DailyBar.session_date.desc())
        .limit(1)
        .correlate(PriceSeries)
    )
    latest_close = newest.with_only_columns(DailyBar.close).scalar_subquery()
    previous_close = (
        newest.with_only_columns(DailyBar.close).offset(1).scalar_subquery()
    )
    latest_date = newest.with_only_columns(DailyBar.session_date).scalar_subquery()

    supported = select(StockRecord, PriceSeries).join(
        PriceSeries, PriceSeries.symbol == StockRecord.symbol
    )
    filtered = supported.where(_matches(query)) if query else supported
    ordering = (
        (case((StockRecord.symbol == query, 0), else_=1), StockRecord.symbol)
        if query
        else (StockRecord.symbol,)
    )

    with Session(engine) as session:
        total_supported = session.scalar(
            select(func.count()).select_from(supported.subquery())
        )
        total_matching = (
            session.scalar(select(func.count()).select_from(filtered.subquery()))
            if query
            else total_supported
        )
        latest_session = session.scalar(
            select(func.max(latest_date)).select_from(PriceSeries)
        )
        rows = session.execute(
            filtered.add_columns(latest_close, previous_close, latest_date)
            .order_by(*ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

    items = []
    for stock, series, close, previous, as_of in rows:
        last = float(close) if close is not None else None
        items.append(
            ExploreItem(
                symbol=stock.symbol,
                name=verified_name(stock.symbol, stock.name),
                exchange=verified_exchange(stock.exchange),
                last_close=last,
                as_of=as_of,
                daily_change_pct=daily_change(
                    last, float(previous) if previous is not None else None
                ),
                series_revision=series_revision(series),
            )
        )
    return ExplorePage(
        query=query,
        page=page,
        page_size=page_size,
        total_supported=total_supported or 0,
        total_matching=total_matching or 0,
        latest_session=latest_session,
        items=items,
    )


def explore_fixture(query: str, page: int, page_size: int) -> ExplorePage:
    """The explicit offline demo serves one AAPL series; mirror it honestly."""
    symbol, name, exchange = FIXTURE_STOCK
    bars = load_bars()
    matches = not query or query in symbol or query in name.upper()
    item = ExploreItem(
        symbol=symbol,
        name=name,
        exchange=exchange,
        last_close=bars[-1].close,
        as_of=bars[-1].date,
        daily_change_pct=daily_change(bars[-1].close, bars[-2].close),
        series_revision=fixture_snapshot_id(),
    )
    return ExplorePage(
        query=query,
        page=page,
        page_size=page_size,
        total_supported=1,
        total_matching=1 if matches else 0,
        latest_session=bars[-1].date,
        items=[item] if matches and page == 1 else [],
    )
