"""Opaque first-party sessions bootstrapped only by a verified Auth0 access token."""

import hashlib
import hmac
import re
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db import AuthSession, UserIdentity

COOKIE = "stocksight_session"
COOKIE_PATH = "/api"


def digest(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def cookie_value(request):
    value = request.cookies.get(COOKIE, "")
    return value if re.fullmatch(r"[A-Za-z0-9_-]{43}", value) else None


def session_storage_error():
    return HTTPException(
        503,
        detail={
            "code": "SESSION_UNAVAILABLE",
            "message": "Your session is unavailable. Try again.",
        },
    )


def read_session(request):
    value = cookie_value(request)
    if value is None:
        return None
    engine = request.app.state.engine
    if engine is None:
        raise session_storage_error()
    try:
        with engine.connect() as connection:
            row = (
                connection.execute(
                    select(AuthSession, UserIdentity.issuer, UserIdentity.subject)
                    .join(UserIdentity, AuthSession.user_id == UserIdentity.id)
                    .where(AuthSession.token_hash == digest(value))
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        expiry = row["expires_at"]
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        settings = request.app.state.settings
        if (
            expiry <= datetime.now(UTC)
            or not settings.auth0_domain
            or not settings.auth0_audience
            or row["issuer"] != f"https://{settings.auth0_domain}/"
            or row["audience"] != settings.auth0_audience
        ):
            return None
        return dict(row)
    except SQLAlchemyError:
        raise session_storage_error() from None


def require_origin(request):
    if request.headers.get("origin") != request.app.state.settings.app_origin:
        raise HTTPException(
            403,
            detail={
                "code": "ORIGIN_REJECTED",
                "message": "Open StockSight from its configured address.",
            },
        )


def require_session_request(request, session):
    expected_user = request.headers.get("x-session-user")
    if expected_user is not None and expected_user != session["user_id"]:
        raise HTTPException(
            401,
            detail={
                "code": "SESSION_CHANGED",
                "message": "Your account changed. Sign in again.",
            },
        )
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request)
        submitted = request.headers.get("x-csrf-token", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", submitted) or not hmac.compare_digest(
            submitted, session["csrf_token"]
        ):
            raise HTTPException(
                403,
                detail={
                    "code": "CSRF_REJECTED",
                    "message": "Refresh your session before trying again.",
                },
            )
