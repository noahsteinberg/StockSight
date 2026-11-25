"""Explore summaries over real migrated storage and the explicit AAPL fixture."""

import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import DailyBar, PriceSeries, StockRecord, database_engine
from app.factory import create_app
from app.market import load_bars
from app.seed import seed_fixture

BACKEND = Path(__file__).resolve().parents[1]
DATABASES = ["sqlite"] + (
    ["postgresql"] if os.getenv("STOCKSIGHT_TEST_DATABASE_URL") else []
)


def add_stock(connection, symbol, name, exchange, closes):
    connection.execute(
        insert(StockRecord).values(
            symbol=symbol, name=name, exchange=exchange, currency="USD"
        )
    )
    if closes is None:
        return
    connection.execute(
        insert(PriceSeries).values(
            id=f"test-{symbol}",
            symbol=symbol,
            source="test",
            source_url="https://example.test",
            mode="historical_snapshot",
            adjustment="test",
            fixture_sha256="b" * 64,
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
                volume=100,
            )
        )


@pytest.fixture(params=DATABASES)
def explore_client(request, tmp_path):
    url = (
        f"sqlite:///{tmp_path / 'explore.sqlite'}"
        if request.param == "sqlite"
        else os.environ["STOCKSIGHT_TEST_DATABASE_URL"]
    )
    if request.param == "postgresql" and not (make_url(url).database or "").endswith(
        "_test"
    ):
        pytest.fail("Only disposable PostgreSQL databases ending in _test may be reset")
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    engine = database_engine(url)
    seed_fixture(engine)
    with engine.begin() as connection:
        # Placeholder metadata as written by the team-snapshot importer.
        add_stock(connection, "ABBV", "ABBV", "UNKNOWN", [100.0, 102.0])
        add_stock(connection, "MSFT", "Microsoft Corporation", "NASDAQ", [50.0])
        add_stock(connection, "BRK-B", "BRK-B", "UNKNOWN", [400.0, 380.0, 390.0])
        # A catalog row without stored history is not a supported stock.
        add_stock(connection, "NOHIST", "No History Inc.", "NYSE", None)
    with TestClient(create_app(Settings(_env_file=None, database_url=url))) as client:
        yield client
    engine.dispose()
    command.downgrade(config, "base")


def test_explore_lists_supported_stocks_alphabetically_with_latest_closes(
    explore_client,
):
    body = explore_client.get("/api/explore").json()
    assert body["total_supported"] == 4
    assert body["total_matching"] == 4
    assert body["page"] == 1
    assert body["page_size"] == 25
    assert [item["symbol"] for item in body["items"]] == [
        "AAPL",
        "ABBV",
        "BRK-B",
        "MSFT",
    ]
    aapl, abbv, brk, msft = body["items"]
    bars = load_bars()
    assert aapl["name"] == "Apple Inc."
    assert aapl["exchange"] == "NASDAQ"
    assert aapl["last_close"] == bars[-1].close
    assert aapl["as_of"] == bars[-1].date.isoformat()
    assert aapl["daily_change_pct"] == pytest.approx(
        (bars[-1].close / bars[-2].close - 1) * 100
    )
    assert len(aapl["series_revision"]) == 64
    # Placeholder names/exchanges are reported as unknown, not as verified facts.
    assert abbv["name"] is None and abbv["exchange"] is None
    assert abbv["last_close"] == 102.0
    assert abbv["as_of"] == "2026-11-02"
    assert abbv["daily_change_pct"] == pytest.approx(2.0)
    assert brk["daily_change_pct"] == pytest.approx((390 / 380 - 1) * 100)
    assert brk["as_of"] == "2026-11-03"
    # One stored session cannot produce a daily change.
    assert msft["last_close"] == 50.0
    assert msft["daily_change_pct"] is None
    assert body["latest_session"] == max(bars[-1].date, date(2026, 11, 3)).isoformat()


def test_explore_pages_are_bounded_and_deterministic(explore_client):
    first = explore_client.get("/api/explore?page_size=2").json()
    second = explore_client.get("/api/explore?page_size=2&page=2").json()
    beyond = explore_client.get("/api/explore?page_size=2&page=3").json()
    assert [item["symbol"] for item in first["items"]] == ["AAPL", "ABBV"]
    assert [item["symbol"] for item in second["items"]] == ["BRK-B", "MSFT"]
    assert beyond["items"] == []
    assert beyond["total_matching"] == 4


def test_explore_query_matches_symbol_or_name_and_ranks_exact_symbol_first(
    explore_client,
):
    by_name = explore_client.get("/api/explore?query=microsoft").json()
    assert [item["symbol"] for item in by_name["items"]] == ["MSFT"]
    assert by_name["total_matching"] == 1
    assert by_name["total_supported"] == 4
    assert by_name["query"] == "MICROSOFT"
    exact = explore_client.get("/api/explore?query=abbv").json()
    assert exact["items"][0]["symbol"] == "ABBV"
    none = explore_client.get("/api/explore?query=%25").json()
    assert none["items"] == [] and none["total_matching"] == 0
    assert explore_client.get("/api/explore?query=NOHIST").json()["items"] == []


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": 1001},
        {"page_size": 0},
        {"page_size": 51},
        {"query": "x" * 41},
        {"page": "two"},
    ],
)
def test_explore_rejects_invalid_parameters(params):
    client = TestClient(create_app(Settings(_env_file=None, database_url=None)))
    assert client.get("/api/explore", params=params).status_code == 422


def test_explore_fixture_mode_serves_only_the_apple_fixture():
    client = TestClient(create_app(Settings(_env_file=None, database_url=None)))
    body = client.get("/api/explore").json()
    bars = load_bars()
    assert body["total_supported"] == 1
    assert [item["symbol"] for item in body["items"]] == ["AAPL"]
    assert body["items"][0]["last_close"] == bars[-1].close
    assert body["latest_session"] == bars[-1].date.isoformat()
    assert client.get("/api/explore?query=apple").json()["total_matching"] == 1
    missing = client.get("/api/explore?query=MSFT").json()
    assert missing["items"] == [] and missing["total_matching"] == 0
    assert client.get("/api/explore?page=2").json()["items"] == []


def test_explore_reports_storage_failure_as_503(tmp_path):
    unmigrated = f"sqlite:///{tmp_path / 'unmigrated.sqlite'}"
    client = TestClient(create_app(Settings(_env_file=None, database_url=unmigrated)))
    response = client.get("/api/explore")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATA_UNAVAILABLE"
