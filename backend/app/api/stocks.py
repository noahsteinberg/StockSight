"""Stock routes preserve the historical contract across explicit storage modes."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from app.market import ADJUSTMENT, SOURCE, SOURCE_URL, History, Stock, load_bars
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


@router.get("/stocks/{symbol}/prices", response_model=History)
def prices(
    request: Request, symbol: str, range: Literal["1mo", "3mo", "1y", "all"] = "3mo"
) -> History:
    symbol = symbol.strip().upper()
    if request.app.state.engine is not None:
        try:
            result = database_history(request.app.state.engine, symbol, range)
        except SQLAlchemyError:
            raise unavailable() from None
        if result is not None:
            return result
    elif symbol == "AAPL":
        bars = load_bars()
        count = {"1mo": 21, "3mo": 63, "1y": 252, "all": 2000}[range]
        return History(
            symbol=symbol,
            name="Apple Inc.",
            source=SOURCE,
            source_url=SOURCE_URL,
            adjustment=ADJUSTMENT,
            as_of=bars[-1].date,
            range=range,
            bars=list(bars[-count:]),
        )
    raise HTTPException(
        404, detail={"code": "UNSUPPORTED_SYMBOL", "message": "Try AAPL."}
    )
