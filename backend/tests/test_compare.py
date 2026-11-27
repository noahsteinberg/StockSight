"""Common-date comparison over migrated storage, using small hand-built histories."""

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


def day(number):
    return date(2026, 11, number)


def add_stock(connection, symbol, bars, name=None):
    connection.execute(
        insert(StockRecord).values(
            symbol=symbol, name=name or symbol, exchange="UNKNOWN", currency="USD"
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
    for session_date, close, split in bars:
        connection.execute(
            insert(DailyBar).values(
                series_id=f"test-{symbol}",
                session_date=session_date,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=100,
                source_values={"stock_splits": split, "dividends": 0.0},
            )
        )


@pytest.fixture(params=DATABASES)
def client(request, tmp_path):
    url = (
        f"sqlite:///{tmp_path / 'compare.sqlite'}"
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
        add_stock(connection, "AAA", [(day(n), 10.0 * n, 0) for n in range(1, 6)])
        # BBB has no stored session on day 3.
        add_stock(
            connection, "BBB", [(day(n), 100.0 + n, 0) for n in (1, 2, 4, 5)], "Bee Co"
        )
        # CCC is stale: its newest stored session is day 4.
        add_stock(connection, "CCC", [(day(n), 50.0, 0) for n in range(1, 5)])
        # DDD's close halves on a 2-for-1 split day: stored prices are unadjusted.
        add_stock(
            connection,
            "DDD",
            [(day(1), 100.0, 0), (day(2), 100.0, 0), (day(3), 50.0, 2.0)]
            + [(day(n), 50.0, 0) for n in (4, 5)],
        )
        # EEE records a split, but its closes are continuous (already adjusted).
        add_stock(
            connection,
            "EEE",
            [(day(1), 20.0, 0), (day(2), 20.0, 0), (day(3), 21.0, 2.0)]
            + [(day(n), 22.0, 0) for n in (4, 5)],
        )
        add_stock(connection, "ONE", [(day(5), 9.0, 0)])
        # TWIN copies every AAPL fixture date, so range trimming can be checked.
        add_stock(connection, "TWIN", [(bar.date, 5.0, 0) for bar in load_bars()])
    with TestClient(
        create_app(Settings(_env_file=None, database_url=url))
    ) as test_client:
        yield test_client
    engine.dispose()
    command.downgrade(config, "base")


def get(client, symbols, range_value="1mo"):
    return client.get("/api/compare", params={"symbols": symbols, "range": range_value})


def test_common_dates_exclude_missing_sessions_and_index_to_100(client):
    body = get(client, "aaa, bbb").json()
    assert body["dates"] == [day(n).isoformat() for n in (1, 2, 4, 5)]
    assert body["common_sessions"] == 4
    assert body["start"] == day(1).isoformat() and body["end"] == day(5).isoformat()
    assert body["aligned_to_shared_cutoff"] is False
    aaa, bbb = body["stocks"]
    assert [aaa["symbol"], bbb["symbol"]] == ["AAA", "BBB"]
    assert aaa["indexed"] == pytest.approx([100, 200, 400, 500])
    assert aaa["period_change_pct"] == pytest.approx(400)
    assert bbb["indexed"][0] == pytest.approx(100)
    assert bbb["period_change_pct"] == pytest.approx((105 / 101 - 1) * 100)
    assert bbb["name"] == "Bee Co" and aaa["name"] is None
    assert aaa["metric_status"] == "ok" and aaa["split_events"] == []
    assert len(aaa["series_revision"]) == 64


def test_stale_stock_sets_a_shared_cutoff_without_hiding_newer_closes(client):
    body = get(client, "AAA,CCC").json()
    assert body["aligned_to_shared_cutoff"] is True
    assert body["end"] == day(4).isoformat()
    aaa, ccc = body["stocks"]
    assert aaa["as_of"] == day(5).isoformat() and aaa["last_close"] == 50.0
    assert aaa["end_close"] == 40.0
    assert aaa["period_change_pct"] == pytest.approx(300)
    assert ccc["as_of"] == day(4).isoformat()
    assert ccc["period_change_pct"] == pytest.approx(0)


def test_unadjusted_split_withholds_change_but_adjusted_split_does_not(client):
    body = get(client, "DDD,EEE").json()
    ddd, eee = body["stocks"]
    assert ddd["metric_status"] == "split_unadjusted"
    assert ddd["period_change_pct"] is None
    assert ddd["split_events"] == [
        {"date": day(3).isoformat(), "ratio": 2.0, "price_adjusted": False}
    ]
    assert len(ddd["indexed"]) == 5
    assert eee["metric_status"] == "ok"
    assert eee["split_events"][0]["price_adjusted"] is True
    assert eee["period_change_pct"] == pytest.approx(10)


def test_window_is_trimmed_to_the_requested_range(client):
    bars = load_bars()
    for range_value, sessions in (("1mo", 21), ("3mo", 63)):
        body = get(client, "AAPL,TWIN", range_value).json()
        assert body["requested_sessions"] == sessions
        assert body["common_sessions"] == sessions
        assert body["dates"] == [bar.date.isoformat() for bar in bars[-sessions:]]
        assert body["stocks"][0]["indexed"][-1] == pytest.approx(
            bars[-1].close / bars[-sessions].close * 100
        )


def test_too_little_overlap_is_reported_not_invented(client):
    body = get(client, "AAA,ONE").json()
    assert body["common_sessions"] == 0
    assert body["dates"] == [] and body["start"] is None
    assert {stock["metric_status"] for stock in body["stocks"]} == {
        "insufficient_overlap"
    }
    assert all(stock["period_change_pct"] is None for stock in body["stocks"])
    assert body["stocks"][1]["last_close"] == 9.0


@pytest.mark.parametrize(
    "symbols", ["AAA", "AAA,aaa", "AAA,BBB,CCC,DDD,EEE", "AAA,B$D", ",,"]
)
def test_invalid_selections_return_422(client, symbols):
    response = get(client, symbols)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_COMPARISON"


def test_unknown_symbols_are_named_and_bad_range_is_rejected(client):
    response = get(client, "AAA,NOPE,ZZZZ")
    assert response.status_code == 404
    assert response.json()["detail"]["symbols"] == ["NOPE", "ZZZZ"]
    assert get(client, "AAA,BBB", "5y").status_code == 422


def test_fixture_mode_cannot_compare_and_says_why():
    fixture = TestClient(create_app(Settings(_env_file=None, database_url=None)))
    response = fixture.get("/api/compare", params={"symbols": "AAPL,MSFT"})
    assert response.status_code == 404
    assert response.json()["detail"]["symbols"] == ["MSFT"]


def test_storage_failure_is_503(tmp_path):
    unmigrated = f"sqlite:///{tmp_path / 'unmigrated.sqlite'}"
    broken = TestClient(create_app(Settings(_env_file=None, database_url=unmigrated)))
    response = broken.get("/api/compare", params={"symbols": "AAPL,MSFT"})
    assert response.status_code == 503
