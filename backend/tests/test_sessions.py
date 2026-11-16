"""Session expiry, CSRF, identity binding, restart persistence and logout revocation."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select, update
from test_accounts import account_app as account_app
from test_accounts import accounts_database as accounts_database
from test_accounts import headers
from test_accounts import keys as keys
from test_accounts import token as token

from app.config import Settings
from app.db import AuthSession
from app.factory import create_app
from app.sessions import COOKIE, digest

ORIGIN = "http://127.0.0.1:5173"


def start(client, token_value):
    response = client.post(
        "/api/auth/session", headers={**headers(token_value), "Origin": ORIGIN}
    )
    assert response.status_code == 200
    return response.json()


def csrf(state):
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": state["csrf_token"],
        "X-Session-User": state["user"]["id"],
    }


def test_cookie_restores_after_api_restart_and_logout_revokes_replay(
    account_app, token, accounts_database
):
    _, engine = accounts_database
    with TestClient(account_app) as client:
        assert client.get("/api/auth/session").json()["authenticated"] is False
        response = client.post(
            "/api/auth/session", headers={**headers(token()), "Origin": ORIGIN}
        )
        state = response.json()
        assert state["authenticated"] is True
        cookie = client.cookies.get(COOKIE)
        cookie_header = response.headers["set-cookie"]
        assert (
            "HttpOnly" in cookie_header
            and "SameSite=lax" in cookie_header
            and "Path=/api" in cookie_header
        )
        assert response.headers["cache-control"] == "no-store"
        assert cookie not in str(state)
        with engine.connect() as connection:
            row = connection.execute(select(AuthSession)).mappings().one()
            assert row["token_hash"] == digest(cookie)
            assert cookie not in str(dict(row))
        assert (
            client.post(
                "/api/watchlist", json={"symbol": "AAPL"}, headers=csrf(state)
            ).status_code
            == 201
        )
        assert client.get("/api/me").json()["id"] == state["user"]["id"]
        assert client.post("/api/auth/session", headers=csrf(state)).status_code == 401
        assert (
            client.get(
                "/api/me", headers={"Authorization": "Bearer invalid"}
            ).status_code
            == 401
        )
    restarted = create_app(account_app.state.settings)
    with TestClient(restarted) as client:
        client.cookies.set(COOKIE, cookie, path="/api")
        restored = client.get("/api/auth/session").json()
        assert restored == state
        assert len(client.get("/api/watchlist").json()["items"]) == 1
        assert client.post("/api/auth/logout", headers=csrf(state)).status_code == 204
        assert client.get("/api/me").status_code == 401
        client.cookies.set(COOKIE, cookie, path="/api")
        assert client.get("/api/me").status_code == 401
        assert client.get("/api/auth/session").json()["authenticated"] is False
        assert (
            client.post("/api/auth/logout", headers={"Origin": ORIGIN}).status_code
            == 204
        )


def test_cookie_mutations_require_csrf_and_exact_origin(account_app, token):
    with TestClient(account_app) as client:
        assert (
            client.post("/api/auth/session", headers=headers(token())).status_code
            == 403
        )
        assert (
            client.post(
                "/api/auth/session",
                headers={**headers(token()), "Origin": "https://evil.test"},
            ).status_code
            == 403
        )
        state = start(client, token())
        for invalid in (
            {},
            {"Origin": ORIGIN},
            {**csrf(state), "Origin": "https://evil.test"},
            {**csrf(state), "X-CSRF-Token": "invalid"},
        ):
            assert (
                client.post(
                    "/api/watchlist", json={"symbol": "AAPL"}, headers=invalid
                ).status_code
                == 403
            )
            assert (
                client.delete("/api/watchlist/AAPL", headers=invalid).status_code == 403
            )
            assert client.post("/api/auth/logout", headers=invalid).status_code == 403
        assert (
            client.post(
                "/api/watchlist", json={"symbol": "AAPL"}, headers=csrf(state)
            ).status_code
            == 201
        )
        assert (
            client.delete("/api/watchlist/AAPL", headers=csrf(state)).status_code == 204
        )


def test_cookie_two_user_isolation_switching_and_expiry(
    account_app, token, accounts_database
):
    _, engine = accounts_database
    with TestClient(account_app) as client:
        alice = start(client, token())
        alice_cookie = client.cookies.get(COOKIE)
        client.post("/api/watchlist", json={"symbol": "AAPL"}, headers=csrf(alice))
        bob = start(client, token("auth0|bob"))
        assert bob["user"]["id"] != alice["user"]["id"]
        assert client.get("/api/watchlist").json()["items"] == []
        assert (
            client.get(
                "/api/watchlist", headers={"X-Session-User": alice["user"]["id"]}
            ).status_code
            == 401
        )
        assert (
            client.delete("/api/watchlist/AAPL", headers=csrf(alice)).status_code == 401
        )
        assert (
            client.delete("/api/watchlist/AAPL", headers=csrf(bob)).status_code == 204
        )
        client.cookies.clear()
        client.cookies.set(COOKIE, alice_cookie, path="/api")
        assert client.get("/api/watchlist").status_code == 401
        # A fresh Auth0 proof restores Alice's persisted entries.
        alice = start(client, token())
        assert len(client.get("/api/watchlist").json()["items"]) == 1
        with engine.begin() as connection:
            connection.execute(
                update(AuthSession).values(
                    expires_at=datetime.now(UTC) - timedelta(seconds=1)
                )
            )
        assert client.get("/api/watchlist").status_code == 401
        assert client.get("/api/auth/session").json()["authenticated"] is False


def test_five_session_limit_and_secure_deployment_cookie(
    account_app, token, accounts_database
):
    _, engine = accounts_database
    settings = account_app.state.settings
    settings.app_origin = "https://stocksight.example"
    old_cookies = []
    with TestClient(account_app, base_url="https://stocksight.example") as client:
        for _ in range(7):
            client.cookies.clear()
            response = client.post(
                "/api/auth/session",
                headers={**headers(token()), "Origin": settings.app_origin},
            )
            assert response.status_code == 200
            assert "Secure" in response.headers["set-cookie"]
            old_cookies.append(client.cookies.get(COOKIE))
        with engine.connect() as connection:
            assert connection.scalar(select(func.count()).select_from(AuthSession)) == 5
        client.cookies.clear()
        client.cookies.set(COOKIE, old_cookies[0], path="/api")
        assert client.get("/api/me").status_code == 401


def test_session_audience_change_invalidates_cookie(account_app, token):
    with TestClient(account_app) as client:
        start(client, token())
        account_app.state.settings.auth0_audience = "https://different-api"
        assert client.get("/api/auth/session").json()["authenticated"] is False
        assert client.get("/api/watchlist").status_code == 401


@pytest.mark.parametrize(
    "origin",
    [
        "http://public.example",
        "https://public.example/path",
        "*",
        "https://user:password@public.example",
        "https://public.example?query=yes",
    ],
)
def test_session_origin_must_be_exact_and_https_for_deployment(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_origin=origin)
