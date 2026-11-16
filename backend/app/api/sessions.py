"""First-party cookie lifecycle. Auth0 remains the sole login identity provider."""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.accounts import current_user
from app.auth import Principal, bearer_principal
from app.db import AuthSession, UserIdentity
from app.sessions import (
    COOKIE,
    COOKIE_PATH,
    cookie_value,
    digest,
    read_session,
    require_origin,
    require_session_request,
    session_storage_error,
)

router = APIRouter(tags=["sessions"])


class SessionUser(BaseModel):
    id: str
    sub: str


class SessionState(BaseModel):
    authenticated: bool
    user: SessionUser | None = None
    csrf_token: str | None = None
    expires_at: datetime | None = None


def state_for(row):
    expiry = row["expires_at"]
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return SessionState(
        authenticated=True,
        user=SessionUser(id=row["user_id"], sub=row["subject"]),
        csrf_token=row["csrf_token"],
        expires_at=expiry,
    )


@router.get("/auth/session", response_model=SessionState)
def get_session(request: Request):
    row = read_session(request)
    if row is None:
        return SessionState(authenticated=False)
    return state_for(row)


@router.post("/auth/session", response_model=SessionState)
def create_session(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(bearer_principal)],
):
    require_origin(request)
    user = current_user(request, principal)
    engine = request.app.state.engine
    settings = request.app.state.settings
    raw = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    row = dict(
        token_hash=digest(raw),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        audience=settings.auth0_audience,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.session_max_age_seconds),
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                select(UserIdentity.id)
                .where(UserIdentity.id == user.id)
                .with_for_update()
            )
            connection.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
            old = cookie_value(request)
            if old:
                connection.execute(
                    delete(AuthSession).where(AuthSession.token_hash == digest(old))
                )
            # Bound storage to five active app sessions per account.
            old_sessions = list(
                connection.scalars(
                    select(AuthSession.token_hash)
                    .where(AuthSession.user_id == user.id)
                    .order_by(AuthSession.created_at.desc(), AuthSession.token_hash)
                    .offset(4)
                )
            )
            if old_sessions:
                connection.execute(
                    delete(AuthSession).where(AuthSession.token_hash.in_(old_sessions))
                )
            connection.execute(AuthSession.__table__.insert().values(**row))
        response.set_cookie(
            COOKIE,
            raw,
            max_age=settings.session_max_age_seconds,
            expires=row["expires_at"],
            httponly=True,
            secure=settings.app_origin.startswith("https://"),
            samesite="lax",
            path=COOKIE_PATH,
        )
        return state_for({**row, "subject": principal.subject})
    except SQLAlchemyError:
        raise session_storage_error() from None


@router.post("/auth/logout", status_code=204)
def logout_session(request: Request, response: Response):
    require_origin(request)
    row = read_session(request)
    if row is None:
        # Already expired/revoked: clearing the browser cookie is idempotent.
        response.delete_cookie(COOKIE, path=COOKIE_PATH)
        return
    require_session_request(request, row)
    try:
        with request.app.state.engine.begin() as connection:
            connection.execute(
                delete(AuthSession).where(AuthSession.token_hash == row["token_hash"])
            )
    except SQLAlchemyError:
        raise session_storage_error() from None
    response.delete_cookie(COOKIE, path=COOKIE_PATH)
