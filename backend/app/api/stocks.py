"""Stock routes preserve the historical contract across explicit storage modes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.compare import ComparePage, compare_database, compare_fixture, parse_symbols
from app.explore import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    ExplorePage,
    ExploreSort,
    SectorList,
    explore_database,
    explore_fixture,
    sectors_database,
    sectors_fixture,
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
from app.patterns import PatternResponse, patterns_database, patterns_fixture
from app.repository import database_history, search_database, supported_symbol
from app.research_ideas import IdeaMethod, ResearchIdeas, research_ideas
from app.signals import SUPPORTED_HORIZONS, SignalResponse, unavailable_signal
from app.stock_metadata import SOURCE as METADATA_SOURCE
from app.stock_metadata import MetadataSource, Sector, profile_for

router = APIRouter(tags=["stocks"])
SEARCH_LIMIT_MAX = 1000


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
    request: Request,
    query: Annotated[str, Query(max_length=40)] = "",
    # The default keeps the original 50-result contract; the ticker dropdown
    # asks for the whole supported catalog once (494 stocks today).
    limit: Annotated[int, Query(ge=1, le=SEARCH_LIMIT_MAX)] = 50,
) -> list[Stock]:
    query = query.strip().upper()
    if request.app.state.engine is not None:
        try:
            return search_database(request.app.state.engine, query, limit)
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
    sector: Sector | None = None,
    sort: ExploreSort = "ticker",
) -> ExplorePage:
    query = query.strip().upper()
    if request.app.state.engine is None:
        return explore_fixture(query, page, page_size, sector)
    try:
        return explore_database(
            request.app.state.engine, query, page, page_size, sector, sort=sort
        )
    except SQLAlchemyError:
        raise unavailable() from None


@router.get("/sectors", response_model=SectorList)
def sectors(request: Request) -> SectorList:
    if request.app.state.engine is None:
        return sectors_fixture()
    try:
        return sectors_database(request.app.state.engine)
    except SQLAlchemyError:
        raise unavailable() from None


@router.get("/research-ideas", response_model=ResearchIdeas)
def ideas(
    request: Request,
    query: Annotated[str, Query(max_length=40)] = "",
    sector: Sector | None = None,
    method: IdeaMethod = "momentum",
) -> ResearchIdeas:
    try:
        return research_ideas(
            request.app.state.engine,
            query.strip().upper(),
            [sector] if sector else [],
            method,
        )
    except SQLAlchemyError:
        raise unavailable() from None


class StockProfileResponse(BaseModel):
    symbol: str
    company_name: str | None
    sector: str | None
    sub_industry: str | None
    source: MetadataSource


def require_supported(request: Request, symbol: str) -> str:
    symbol = symbol.strip().upper()
    if request.app.state.engine is None:
        supported = symbol == "AAPL"
    else:
        try:
            supported = supported_symbol(request.app.state.engine, symbol)
        except SQLAlchemyError:
            raise unavailable() from None
    if not supported:
        raise unsupported()
    return symbol


@router.get("/stocks/{symbol}/profile", response_model=StockProfileResponse)
def stock_profile(request: Request, symbol: str) -> StockProfileResponse:
    symbol = require_supported(request, symbol)
    profile = profile_for(symbol)
    return StockProfileResponse(
        symbol=symbol,
        company_name=profile.company_name if profile else None,
        sector=profile.sector if profile else None,
        sub_industry=profile.sub_industry if profile else None,
        source=METADATA_SOURCE,
    )


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


@router.get("/stocks/{symbol}/signals", response_model=SignalResponse)
def signals(
    request: Request,
    symbol: str,
    horizon_sessions: Annotated[
        int, Query(ge=min(SUPPORTED_HORIZONS), le=max(SUPPORTED_HORIZONS))
    ] = 1,
) -> SignalResponse:
    """Typed research-signal status. No model is approved, so a supported stock
    always gets a 200 "unavailable" response; nothing is generated on request."""
    return unavailable_signal(require_supported(request, symbol), horizon_sessions)


@router.get("/stocks/{symbol}/patterns", response_model=PatternResponse)
def patterns(
    request: Request,
    symbol: str,
    horizon_sessions: Annotated[int, Query(ge=5, le=21)] = 21,
) -> PatternResponse:
    if horizon_sessions not in (5, 21):
        raise HTTPException(
            422,
            detail={
                "code": "INVALID_PATTERN_HORIZON",
                "message": "Choose 5 or 21 stored sessions.",
            },
        )
    symbol = symbol.strip().upper()
    if request.app.state.engine is None:
        if symbol != "AAPL":
            raise unsupported()
        return patterns_fixture(horizon_sessions)
    try:
        result = patterns_database(request.app.state.engine, symbol, horizon_sessions)
    except SQLAlchemyError:
        raise unavailable() from None
    if result is None:
        raise unsupported()
    return result


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
    raise unsupported()


def unsupported() -> HTTPException:
    return HTTPException(
        404,
        detail={
            "code": "UNSUPPORTED_SYMBOL",
            "message": "No stored history for this symbol. Search supported stocks.",
        },
    )
