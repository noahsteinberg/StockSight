"""Private research preferences: ownership, validation, reset, CSRF and discovery."""

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, inspect
from test_accounts import account_app as account_app
from test_accounts import accounts_database as accounts_database
from test_accounts import headers
from test_accounts import keys as keys
from test_accounts import token as token
from test_sessions import csrf, start

from app.config import Settings
from app.db import DailyBar, PriceSeries, StockRecord
from app.factory import create_app

ORIGIN_EVIL = "https://evil.test"
ENERGY_AND_TECH = {
    "purpose": "compare",
    "sectors": ["Information Technology", "Energy"],
    "horizon": "months",
    "default_range": "1y",
}


def add_stock(engine, symbol, closes):
    with engine.begin() as connection:
        connection.execute(
            insert(StockRecord).values(
                symbol=symbol, name=symbol, exchange="UNKNOWN", currency="USD"
            )
        )
        connection.execute(
            insert(PriceSeries).values(
                id=f"test-{symbol}",
                symbol=symbol,
                source="test",
                source_url="https://example.test",
                mode="historical_snapshot",
                adjustment="test",
                fixture_sha256="c" * 64,
                imported_at=datetime(2026, 11, 1, tzinfo=UTC),
            )
        )
        for day, close in enumerate(closes, start=1):
            connection.execute(
                insert(DailyBar).values(
                    series_id=f"test-{symbol}",
                    session_date=date(2026, 11, day),
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=1,
                )
            )


@pytest.fixture
def stocks(accounts_database):
    # AAPL comes from the seeded fixture; XOM is Energy and PFE is Health Care.
    _, engine = accounts_database
    add_stock(engine, "XOM", [100.0, 101.0])
    add_stock(engine, "PFE", [25.0, 24.5])


def test_preferences_require_an_account(account_app):
    with TestClient(account_app) as client:
        assert client.get("/api/me/preferences").status_code == 401
        assert client.put("/api/me/preferences", json={}).status_code == 401
        assert client.delete("/api/me/preferences").status_code == 401
        assert client.get("/api/me/discovery").status_code == 401


def test_save_read_reset_and_two_account_isolation(account_app, token):
    alice, bob = headers(token()), headers(token("auth0|bob"))
    with TestClient(account_app) as client:
        empty = client.get("/api/me/preferences", headers=alice)
        assert empty.headers["cache-control"] == "no-store"
        assert empty.json() == {
            "saved": False,
            "schema_version": 1,
            "purpose": None,
            "sectors": [],
            "horizon": None,
            "default_range": None,
            "updated_at": None,
        }
        saved = client.put("/api/me/preferences", headers=alice, json=ENERGY_AND_TECH)
        assert saved.status_code == 200
        body = saved.json()
        assert body["saved"] is True
        # Sectors are stored in taxonomy order, whatever order they were sent in.
        assert body["sectors"] == ["Energy", "Information Technology"]
        assert body["default_range"] == "1y" and body["updated_at"].endswith("Z")
        assert client.get("/api/me/preferences", headers=alice).json() == body
        # Bob sees nothing of Alice's, and his reset cannot remove hers.
        assert client.get("/api/me/preferences", headers=bob).json()["saved"] is False
        assert client.delete("/api/me/preferences", headers=bob).status_code == 204
        assert client.get("/api/me/preferences", headers=alice).json() == body
        # A second save replaces the first; omitted fields become "no preference".
        updated = client.put(
            "/api/me/preferences", headers=alice, json={"purpose": "learn"}
        ).json()
        assert updated["purpose"] == "learn" and updated["sectors"] == []
        assert updated["default_range"] is None
        assert client.delete("/api/me/preferences", headers=alice).status_code == 204
        assert client.delete("/api/me/preferences", headers=alice).status_code == 204
        assert client.get("/api/me/preferences", headers=alice).json()["saved"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"purpose": "invest"},
        {"sectors": ["Tech"]},
        {"sectors": ["Energy", "Energy"]},
        {"horizon": "decades"},
        {"default_range": "5y"},
        {"income": 100000},
        {"user_id": "someone-else"},
        {"sectors": "Energy"},
    ],
)
def test_invalid_or_unexpected_fields_are_rejected(account_app, token, payload):
    alice = headers(token())
    with TestClient(account_app) as client:
        response = client.put("/api/me/preferences", headers=alice, json=payload)
        assert response.status_code == 422
        assert client.get("/api/me/preferences", headers=alice).json()["saved"] is False


def test_cookie_writes_need_csrf_and_exact_origin(account_app, token):
    with TestClient(account_app) as client:
        state = start(client, token())
        invalid_headers = (
            {},
            {"Origin": ORIGIN_EVIL},
            {**csrf(state), "X-CSRF-Token": "invalid"},
        )
        for invalid in invalid_headers:
            rejected = client.put(
                "/api/me/preferences", json=ENERGY_AND_TECH, headers=invalid
            )
            assert rejected.status_code == 403
            assert (
                client.delete("/api/me/preferences", headers=invalid).status_code == 403
            )
        saved = client.put(
            "/api/me/preferences", json=ENERGY_AND_TECH, headers=csrf(state)
        )
        assert saved.status_code == 200
        assert client.get("/api/me/preferences").json()["sectors"] == [
            "Energy",
            "Information Technology",
        ]


def test_discovery_explains_sector_matches_and_never_broadens(
    account_app, token, stocks
):
    alice = headers(token())
    with TestClient(account_app) as client:
        none = client.get("/api/me/discovery", headers=alice).json()
        assert none["preference_sectors"] == [] and none["items"] == []
        assert none["total_matching"] == 0 and none["total_supported"] == 3
        client.put("/api/me/preferences", headers=alice, json=ENERGY_AND_TECH)
        found = client.get("/api/me/discovery", headers=alice)
        assert found.headers["cache-control"] == "no-store"
        body = found.json()
        assert body["preference_sectors"] == ["Energy", "Information Technology"]
        assert [item["symbol"] for item in body["items"]] == ["AAPL", "XOM"]
        assert body["total_matching"] == 2 and body["total_supported"] == 3
        reasons = {item["symbol"]: item["match_reason"] for item in body["items"]}
        assert reasons == {
            "AAPL": "Matches your selected sector: Information Technology",
            "XOM": "Matches your selected sector: Energy",
        }
        xom = body["items"][1]
        assert xom["name"] == "ExxonMobil" and xom["last_close"] == 101.0
        searched = client.get("/api/me/discovery?query=xom", headers=alice).json()
        assert [item["symbol"] for item in searched["items"]] == ["XOM"]
        # Another account's preferences never leak into this list.
        bob = client.get("/api/me/discovery", headers=headers(token("auth0|bob")))
        assert bob.json()["items"] == []


def test_preferences_fail_closed_without_storage(tmp_path):
    fixture = TestClient(create_app(Settings(_env_file=None, database_url=None)))
    assert fixture.get("/api/me/preferences").status_code in {401, 503}
    unmigrated = f"sqlite:///{tmp_path / 'empty.sqlite'}"
    client = TestClient(create_app(Settings(_env_file=None, database_url=unmigrated)))
    assert client.get("/api/ready").status_code == 503


def test_migration_adds_only_the_preferences_table(accounts_database):
    _, engine = accounts_database
    columns = {item["name"] for item in inspect(engine).get_columns("user_preferences")}
    assert columns == {
        "user_id",
        "schema_version",
        "purpose",
        "horizon",
        "default_range",
        "sectors",
        "created_at",
        "updated_at",
    }
