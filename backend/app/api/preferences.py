"""Optional, private research preferences and the discovery list they explain.

Preferences describe interests only. They filter or default views through explicit
rules; they never feed a model, score a stock or imply financial suitability.
Ownership always comes from the authenticated account, never from the request.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from app.api.accounts import CurrentUser, account_engine, current_user
from app.db import PriceSeries, UserPreference
from app.explore import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    ExploreItem,
    ExploreSort,
    explore_database,
)
from app.stock_metadata import SECTORS, Sector

router = APIRouter(tags=["preferences"])
SCHEMA_VERSION = 1

Purpose = Literal["learn", "compare", "track"]
Horizon = Literal["weeks", "months", "years"]
ChartRange = Literal["1mo", "3mo", "1y", "all"]


def preferences_unavailable():
    return HTTPException(
        503,
        detail={
            "code": "PREFERENCES_UNAVAILABLE",
            "message": "Your preferences are temporarily unavailable. Try again.",
        },
    )


class PreferenceInput(BaseModel):
    """Null or an empty list means "no preference"; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")
    purpose: Purpose | None = None
    sectors: list[Sector] = Field(default_factory=list, max_length=len(SECTORS))
    horizon: Horizon | None = None
    default_range: ChartRange | None = None

    @field_validator("sectors")
    @classmethod
    def distinct_sectors(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Choose each sector at most once.")
        # Stored in taxonomy order, so equal choices always compare equal.
        return [sector for sector in SECTORS if sector in value]


class Preferences(PreferenceInput):
    model_config = ConfigDict(extra="ignore")
    saved: bool
    schema_version: int = SCHEMA_VERSION
    updated_at: datetime | None = None

    @field_validator("updated_at")
    @classmethod
    def utc_timestamp(cls, value):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def read_preferences(connection, user_id: str) -> Preferences:
    row = (
        connection.execute(
            select(UserPreference.__table__).where(UserPreference.user_id == user_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        return Preferences(saved=False)
    return Preferences(
        saved=True,
        schema_version=row["schema_version"],
        purpose=row["purpose"],
        sectors=[sector for sector in row["sectors"] if sector in SECTORS],
        horizon=row["horizon"],
        default_range=row["default_range"],
        updated_at=row["updated_at"],
    )


@router.get("/me/preferences", response_model=Preferences)
def get_preferences(
    request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> Preferences:
    try:
        with account_engine(request).connect() as connection:
            return read_preferences(connection, user.id)
    except SQLAlchemyError:
        raise preferences_unavailable() from None


@router.put("/me/preferences", response_model=Preferences)
def save_preferences(
    payload: PreferenceInput,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
) -> Preferences:
    engine = account_engine(request)
    now = datetime.now(UTC)
    values = {**payload.model_dump(), "schema_version": SCHEMA_VERSION}
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    try:
        with engine.begin() as connection:
            # One upsert keeps concurrent saves for the same account consistent.
            connection.execute(
                insert(UserPreference)
                .values(user_id=user.id, created_at=now, updated_at=now, **values)
                .on_conflict_do_update(
                    index_elements=["user_id"], set_={**values, "updated_at": now}
                )
            )
            return read_preferences(connection, user.id)
    except SQLAlchemyError:
        raise preferences_unavailable() from None


@router.delete("/me/preferences", status_code=204)
def reset_preferences(
    request: Request, user: Annotated[CurrentUser, Depends(current_user)]
) -> Response:
    try:
        with account_engine(request).begin() as connection:
            connection.execute(
                delete(UserPreference).where(UserPreference.user_id == user.id)
            )
        return Response(status_code=204)
    except SQLAlchemyError:
        raise preferences_unavailable() from None


class DiscoveryItem(ExploreItem):
    match_reason: str


class DiscoveryPage(BaseModel):
    query: str
    preference_sectors: list[str]
    page: int
    page_size: int
    total_supported: int
    total_matching: int
    latest_session: date | None
    items: list[DiscoveryItem]


@router.get("/me/discovery", response_model=DiscoveryPage)
def discovery(
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    query: Annotated[str, Query(max_length=40)] = "",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
    sort: ExploreSort = "ticker",
) -> DiscoveryPage:
    """Supported stocks in the account's chosen sectors, with the match reason.

    There is no score or ranking: a stock either matches an explicit rule or not.
    """
    query = query.strip().upper()
    engine = account_engine(request)
    try:
        with engine.connect() as connection:
            preferences = read_preferences(connection, user.id)
            supported = connection.scalar(select(func.count()).select_from(PriceSeries))
        listing = (
            explore_database(
                engine, query, page, page_size, sectors=preferences.sectors, sort=sort
            )
            if preferences.sectors
            else None
        )
    except SQLAlchemyError:
        raise preferences_unavailable() from None
    if listing is None:
        # No chosen sectors means no rule to match; never fall back to everything.
        return DiscoveryPage(
            query=query,
            preference_sectors=[],
            page=page,
            page_size=page_size,
            total_supported=supported or 0,
            total_matching=0,
            latest_session=None,
            items=[],
        )
    return DiscoveryPage(
        query=query,
        preference_sectors=preferences.sectors,
        page=page,
        page_size=page_size,
        total_supported=listing.total_supported,
        total_matching=listing.total_matching,
        latest_session=listing.latest_session,
        items=[
            DiscoveryItem(
                **item.model_dump(),
                match_reason=f"Matches your selected sector: {item.sector}",
            )
            for item in listing.items
        ],
    )
