"""Stock routes preserve the historical contract across explicit storage modes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from app.compare import ComparePage, compare_database, compare_fixture, parse_symbols
from app.explore import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    ExplorePage,
    explore_database,
    explore_fixture,
)
from app.indicators import CALCULATION_LIMIT, IndicatorHistory, calculate_indicators
from app.market import (
    ADJUSTMENT,
    SESSION_LIMITS,
    SOURCE,
    SOURCE_URL,
    History,
    HistoryRange,
    Stock,
    fixture_snapshot_id,
    load_bars,
)
from app.repository import database_history, search_database

router = APIRouter(tags=["stocks"])


def unavailable() -> HTTPException:
    return HTTPException(
        503,
        detail={
            "code": "DATA_UNAVAILABLE",
            "message": "Stock data is temporarily unavailable.",
        },
    )


@router.get("/stocks", response_model=list[Stock])
def search_stocks(
    request: Request, query: Annotated[str, Query(max_length=40)] = ""
) -> list[Stock]:
    query = query.strip().upper()
    if request.app.state.engine is not None:
        try:
            return search_database(request.app.state.engine, query)
        except SQLAlchemyError:
            raise unavailable() from None
    return (
        [Stock(symbol="AAPL", name="Apple Inc.")]
        if not query or query in "AAPL" or query in "APPLE INC."
        else []
    )


@router.get("/explore", response_model=ExplorePage)
def explore(
    request: Request,
    query: Annotated[str, Query(max_length=40)] = "",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> ExplorePage:
    query = query.strip().upper()
    if request.app.state.engine is None:
        return explore_fixture(query, page, page_size)
    try:
        return explore_database(request.app.state.engine, query, page, page_size)
    except SQLAlchemyError:
        raise unavailable() from None


@router.get("/compare", response_model=ComparePage)
def compare(
    request: Request,
    symbols: Annotated[str, Query(max_length=100)],
    range: HistoryRange = "1y",
) -> ComparePage:
    selected = parse_symbols(symbols)
    if request.app.state.engine is None:
        return compare_fixture(selected)
    try:
        return compare_database(request.app.state.engine, selected, range)
    except SQLAlchemyError:
        raise unavailable() from None


@router.get("/stocks/{symbol}/prices", response_model=History)
def prices(request: Request, symbol: str, range: HistoryRange = "3mo") -> History:
    return read_history(request, symbol, range)


@router.get("/stocks/{symbol}/indicators", response_model=IndicatorHistory)
def indicators(
    request: Request, symbol: str, range: HistoryRange = "3mo"
) -> IndicatorHistory:
    history = read_history(request, symbol, "all", session_limit=CALCULATION_LIMIT)
    return calculate_indicators(history, range)


def read_history(
    request: Request,
    symbol: str,
    range: HistoryRange,
    *,
    session_limit: int | None = None,
) -> History:
    symbol = symbol.strip().upper()
    if request.app.state.engine is not None:
        try:
            result = database_history(
                request.app.state.engine, symbol, range, session_limit=session_limit
            )
        except SQLAlchemyError:
            raise unavailable() from None
        if result is not None:
            return result
    elif symbol == "AAPL":
        bars = load_bars()
        count = session_limit if session_limit is not None else SESSION_LIMITS[range]
        return History(
            symbol=symbol,
            name="Apple Inc.",
            source=SOURCE,
            source_url=SOURCE_URL,
            adjustment=ADJUSTMENT,
            snapshot_id=fixture_snapshot_id(),
            as_of=bars[-1].date,
            range=range,
            bars=list(bars[-count:]),
            session_limit=count,
            has_earlier=len(bars) > count,
        )
    raise HTTPException(
        404,
        detail={
            "code": "UNSUPPORTED_SYMBOL",
            "message": "No stored history for this symbol. Search supported stocks.",
        },
    )
