"""Private, bounded watchlists. Auth0 owns signup, login and password lifecycle."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import Float, cast, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from app.auth import Principal, current_principal
from app.db import DailyBar, PriceSeries, StockRecord, UserIdentity, WatchlistEntry

router = APIRouter(tags=["accounts"])
WATCHLIST_LIMIT = 100


def storage_unavailable():
    return HTTPException(
        503,
        detail={
            "code": "ACCOUNT_STORAGE_UNAVAILABLE",
            "message": "Your watchlist is temporarily unavailable. Try again.",
        },
    )


def account_engine(request):
    engine = request.app.state.engine
    if engine is None:
        raise storage_unavailable()
    return engine


class CurrentUser(BaseModel):
    id: str


class SavedStock(BaseModel):
    symbol: str
    name: str
    added_at: datetime
    daily_change_pct: float | None = None

    @field_validator("added_at")
    @classmethod
    def utc_timestamp(cls, value):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class Watchlist(BaseModel):
    items: list[SavedStock]
    limit: int = WATCHLIST_LIMIT


class AddStock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9.\^=\-]{0,15}$")

    @field_validator("symbol", mode="before")
    @classmethod
    def normalized_symbol(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


def current_user(
    request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> CurrentUser:
    engine = account_engine(request)
    try:
        with engine.begin() as connection:
            identity_query = select(UserIdentity.id).where(
                UserIdentity.issuer == principal.issuer,
                UserIdentity.subject == principal.subject,
            )
            identity = connection.scalar(identity_query)
            if identity is None:
                insert = (
                    pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
                )
                connection.execute(
                    insert(UserIdentity)
                    .values(
                        id=str(uuid4()),
                        issuer=principal.issuer,
                        subject=principal.subject,
                        created_at=datetime.now(UTC),
                    )
                    .on_conflict_do_nothing(index_elements=["issuer", "subject"])
                )
                identity = connection.scalar(identity_query)
        return CurrentUser(id=identity)
    except SQLAlchemyError:
        raise storage_unavailable() from None


def saved_query(user_id):
    # These two index-backed lookups read only the newest stored closes per symbol.
    recent_close = (
        select(DailyBar.close)
        .where(DailyBar.series_id == PriceSeries.id)
        .order_by(DailyBar.session_date.desc())
        .limit(1)
        .correlate(PriceSeries)
    )
    latest = cast(recent_close.scalar_subquery(), Float)
    previous = cast(recent_close.offset(1).scalar_subquery(), Float)
    change = ((latest / func.nullif(previous, 0) - 1) * 100).label("daily_change_pct")
    return (
        select(WatchlistEntry.symbol, StockRecord.name, WatchlistEntry.added_at, change)
        .join(StockRecord, WatchlistEntry.symbol == StockRecord.symbol)
        .outerjoin(PriceSeries, WatchlistEntry.symbol == PriceSeries.symbol)
        .where(WatchlistEntry.user_id == user_id)
    )


@router.get("/me", response_model=CurrentUser)
def me(user: Annotated[CurrentUser, Depends(current_user)]):
    return user


@router.get("/watchlist", response_model=Watchlist)
def list_watchlist(
    request: Request, user: Annotated[CurrentUser, Depends(current_user)]
):
    try:
        with account_engine(request).connect() as connection:
            rows = connection.execute(
                saved_query(user.id)
                .order_by(WatchlistEntry.added_at.desc(), WatchlistEntry.symbol)
                .limit(WATCHLIST_LIMIT)
            ).mappings()
            return Watchlist(items=[SavedStock(**row) for row in rows])
    except SQLAlchemyError:
        raise storage_unavailable() from None


@router.post("/watchlist", response_model=SavedStock, status_code=201)
def add_stock(
    payload: AddStock,
    request: Request,
    response: Response,
    user: Annotated[CurrentUser, Depends(current_user)],
):
    engine = account_engine(request)
    try:
        with engine.begin() as connection:
            # Serialize capacity checks and writes per account on PostgreSQL.
            connection.execute(
                select(UserIdentity.id)
                .where(UserIdentity.id == user.id)
                .with_for_update()
            )
            existing = (
                connection.execute(
                    saved_query(user.id).where(WatchlistEntry.symbol == payload.symbol)
                )
                .mappings()
                .first()
            )
            if existing:
                response.status_code = 200
                return SavedStock(**existing)
            available = connection.scalar(
                select(PriceSeries.symbol).where(PriceSeries.symbol == payload.symbol)
            )
            if available is None:
                raise HTTPException(
                    404,
                    detail={
                        "code": "UNSUPPORTED_SYMBOL",
                        "message": "Choose a supported stock.",
                    },
                )
            count = connection.scalar(
                select(func.count())
                .select_from(WatchlistEntry)
                .where(WatchlistEntry.user_id == user.id)
            )
            if count >= WATCHLIST_LIMIT:
                raise HTTPException(
                    409,
                    detail={
                        "code": "WATCHLIST_FULL",
                        "message": "Remove a stock before saving another. Limit: 100.",
                    },
                )
            connection.execute(
                WatchlistEntry.__table__.insert().values(
                    user_id=user.id, symbol=payload.symbol, added_at=datetime.now(UTC)
                )
            )
            row = (
                connection.execute(
                    saved_query(user.id).where(WatchlistEntry.symbol == payload.symbol)
                )
                .mappings()
                .one()
            )
            return SavedStock(**row)
    except SQLAlchemyError:
        raise storage_unavailable() from None


@router.delete("/watchlist/{symbol}", status_code=204)
def remove_stock(
    symbol: str, request: Request, user: Annotated[CurrentUser, Depends(current_user)]
):
    try:
        symbol = AddStock(symbol=symbol).symbol
    except ValidationError:
        raise HTTPException(
            422, detail={"code": "INVALID_SYMBOL", "message": "Enter a valid ticker."}
        ) from None
    try:
        with account_engine(request).begin() as connection:
            connection.execute(
                delete(WatchlistEntry).where(
                    WatchlistEntry.user_id == user.id, WatchlistEntry.symbol == symbol
                )
            )
        return Response(status_code=204)
    except SQLAlchemyError:
        raise storage_unavailable() from None
