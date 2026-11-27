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
        # A share-class ticker absent from the reviewed metadata stays unknown.
        add_stock(connection, "ZZ-B", "ZZ-B", "UNKNOWN", [400.0, 380.0, 390.0])
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
        "MSFT",
        "ZZ-B",
    ]
    aapl, abbv, msft, brk = body["items"]
    bars = load_bars()
    assert aapl["name"] == "Apple Inc."
    assert aapl["exchange"] == "NASDAQ"
    assert aapl["last_close"] == bars[-1].close
    assert aapl["as_of"] == bars[-1].date.isoformat()
    assert aapl["daily_change_pct"] == pytest.approx(
        (bars[-1].close / bars[-2].close - 1) * 100
    )
    assert aapl["sector"] == "Information Technology"
    assert len(aapl["series_revision"]) == 64
    # The reviewed metadata replaces the importer's ticker placeholder name...
    assert abbv["name"] == "AbbVie" and abbv["exchange"] is None
    assert abbv["sector"] == "Health Care"
    assert abbv["sub_industry"] == "Biotechnology"
    # ...and a stock it doesn't cover stays unknown rather than guessed.
    assert brk["name"] is None and brk["exchange"] is None
    assert brk["sector"] is None and brk["sub_industry"] is None
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
    assert [item["symbol"] for item in second["items"]] == ["MSFT", "ZZ-B"]
    assert beyond["items"] == []
    assert beyond["total_matching"] == 4


@pytest.mark.parametrize(
    "sort, reverse", [("change_desc", True), ("change_asc", False)]
)
def test_explore_sorts_all_matches_before_paging(explore_client, sort, reverse):
    default = explore_client.get("/api/explore").json()["items"]
    available = (item for item in default if item["daily_change_pct"] is not None)
    ordered = sorted(
        available, key=lambda item: item["daily_change_pct"], reverse=reverse
    )
    expected = [item["symbol"] for item in ordered] + ["MSFT"]
    actual = []
    for page in (1, 2):
        response = explore_client.get(
            "/api/explore", params={"sort": sort, "page": page, "page_size": 2}
        )
        assert response.status_code == 200
        actual.extend(item["symbol"] for item in response.json()["items"])
    assert actual == expected


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


def test_explore_query_matches_reviewed_company_names(explore_client):
    # The stored ABBV name is a placeholder; the reviewed name still matches.
    body = explore_client.get("/api/explore?query=abbvie").json()
    assert [item["symbol"] for item in body["items"]] == ["ABBV"]
    search = explore_client.get("/api/stocks?query=abbvie").json()
    assert search == [{"symbol": "ABBV", "name": "AbbVie"}]
    history = explore_client.get("/api/stocks/ABBV/prices?range=1mo").json()
    assert history["name"] == "AbbVie"


def test_explore_filters_by_sector_and_combines_with_query(explore_client):
    tech = explore_client.get(
        "/api/explore", params={"sector": "Information Technology"}
    ).json()
    assert tech["sector"] == "Information Technology"
    assert [item["symbol"] for item in tech["items"]] == ["AAPL", "MSFT"]
    assert tech["total_matching"] == 2 and tech["total_supported"] == 4
    both = explore_client.get(
        "/api/explore", params={"sector": "Information Technology", "query": "MS"}
    ).json()
    assert [item["symbol"] for item in both["items"]] == ["MSFT"]
    # A filter is never silently broadened to produce results.
    energy = explore_client.get("/api/explore", params={"sector": "Energy"}).json()
    assert energy["items"] == [] and energy["total_matching"] == 0


def test_sectors_report_counts_unknown_coverage_and_source(explore_client):
    body = explore_client.get("/api/sectors").json()
    assert body["total_supported"] == 4
    assert body["unknown"] == 1
    counts = {sector["name"]: sector["count"] for sector in body["sectors"]}
    assert len(counts) == 11
    assert counts["Information Technology"] == 2
    assert counts["Health Care"] == 1
    assert counts["Energy"] == 0
    assert "oldid=1384572480" in body["source"]["url"]
    assert body["source"]["revision_date"] == "2026-11-08"


def test_profile_returns_reviewed_metadata_or_unknown_fields(explore_client):
    abbv = explore_client.get("/api/stocks/abbv/profile").json()
    assert abbv["symbol"] == "ABBV"
    assert abbv["company_name"] == "AbbVie"
    assert abbv["sector"] == "Health Care"
    assert abbv["source"]["license"] == "CC BY-SA 4.0"
    unknown = explore_client.get("/api/stocks/ZZ-B/profile").json()
    assert unknown["company_name"] is None and unknown["sector"] is None
    for symbol in ["NOHIST", "NOPE"]:
        response = explore_client.get(f"/api/stocks/{symbol}/profile")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "UNSUPPORTED_SYMBOL"


def test_profile_and_sectors_in_fixture_mode():
    client = TestClient(create_app(Settings(_env_file=None, database_url=None)))
    assert client.get("/api/stocks/AAPL/profile").json()["sector"] == (
        "Information Technology"
    )
    assert client.get("/api/stocks/MSFT/profile").status_code == 404
    sectors = client.get("/api/sectors").json()
    assert sectors["total_supported"] == 1 and sectors["unknown"] == 0
    tech = client.get("/api/explore", params={"sector": "Information Technology"})
    assert tech.json()["total_matching"] == 1
    energy = client.get("/api/explore", params={"sector": "Energy"}).json()
    assert energy["items"] == [] and energy["total_matching"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": 1001},
        {"page_size": 0},
        {"page_size": 51},
        {"query": "x" * 41},
        {"page": "two"},
        {"sector": "Tech"},
        {"sector": "unknown"},
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
