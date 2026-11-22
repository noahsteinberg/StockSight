"""Numerical contracts and API/storage integration for the indicator phase."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert
from sqlalchemy.exc import SQLAlchemyError
from test_database import database as database
from test_database import db_settings

from app.config import Settings
from app.db import DailyBar
from app.indicators import CALCULATION_LIMIT, calculate_indicators
from app.main import create_app
from app.market import Bar, History, load_bars
from app.seed import SERIES_ID, seed_fixture


def history(closes):
    bars = [
        Bar(
            date=date(2020, 1, 1) + timedelta(days=index * 2),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1,
        )
        for index, close in enumerate(closes)
    ]
    return History(
        symbol="TEST",
        name="Numerical fixture",
        source="Test",
        source_url="",
        snapshot_id="numerical-test",
        as_of=bars[-1].date,
        range="all",
        bars=bars,
        session_limit=CALCULATION_LIMIT,
        has_earlier=False,
    )


@pytest.mark.parametrize(
    ("closes", "expected_rsi", "expected_sma"),
    [
        (list(range(1, 26)), 100, 15.5),
        (list(range(25, 0, -1)), 0, 10.5),
        ([10] * 25, 50, 10),
    ],
)
def test_rising_falling_flat_and_warmup(closes, expected_rsi, expected_sma):
    source = history(closes)
    points = calculate_indicators(source, "all").points
    assert [point.date for point in points] == [bar.date for bar in source.bars]
    assert all(point.rsi_14 is None for point in points[:14])
    assert all(point.rsi_14 == expected_rsi for point in points[14:])
    assert all(point.sma_20 is None for point in points[:19])
    assert points[-1].sma_20 == expected_sma


def test_wilder_seed_and_recursive_reference_values():
    # A hand-checkable mixed series: 7 gains of 2 and 7 losses of 1 seed
    # gain=1, loss=0.5 => RSI=200/3. Next +1: gain=1, loss=13/28
    # => RSI=2800/41. Next -2: gain=13/14, loss=225/392 => RSI=36400/589.
    closes = [10]
    for change in [2, -1] * 7 + [1, -2]:
        closes.append(closes[-1] + change)
    points = calculate_indicators(history(closes), "all").points
    assert [point.rsi_14 for point in points[14:]] == pytest.approx(
        [200 / 3, 2800 / 41, 36400 / 589], abs=1e-10
    )


def test_short_history_is_returned_with_nulls_not_an_error():
    points = calculate_indicators(history([12]), "all").points
    assert len(points) == 1
    assert points[0].sma_20 is None and points[0].rsi_14 is None


def test_no_future_price_leakage():
    source = history([10 + index % 7 for index in range(80)])
    prefix = source.model_copy(update={"bars": source.bars[:40]})
    assert (
        calculate_indicators(source, "all").points[:40]
        == calculate_indicators(prefix, "all").points
    )


def assert_api_contract(client):
    response = client.get("/api/stocks/aapl/indicators?range=all")
    assert response.status_code == 200
    full = response.json()
    prices = client.get("/api/stocks/AAPL/prices?range=all").json()
    assert full["symbol"] == "AAPL"
    assert full["methodology"] == "close-sma20-wilder-rsi14-v1"
    assert full["snapshot_id"]
    for key in ("source", "source_url", "adjustment", "mode", "as_of", "snapshot_id"):
        assert full[key] == prices[key]
    assert [point["date"] for point in full["points"]] == [
        bar["date"] for bar in prices["bars"]
    ]
    assert full["points"][19]["sma_20"] == pytest.approx(
        sum(bar["close"] for bar in prices["bars"][:20]) / 20
    )
    for range_value, count in (("1mo", 21), ("3mo", 63), ("1y", 252)):
        short = client.get(f"/api/stocks/AAPL/indicators?range={range_value}").json()
        assert short["snapshot_id"] == full["snapshot_id"]
        assert short["points"] == full["points"][-count:]
        assert short["calculation_start"] == full["calculation_start"]
        assert short["session_limit"] == count
        assert short["has_earlier"] is True
        # Display starts after warmup; do not reset the calculation at its edge.
        assert short["points"][0]["sma_20"] is not None
        assert short["points"][0]["rsi_14"] is not None
    assert client.get("/api/stocks/MSFT/indicators").status_code == 404
    assert client.get("/api/stocks/AAPL/indicators?range=bad").status_code == 422


def test_explicit_fixture_api():
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as client:
        assert_api_contract(client)


def test_database_api_matches_fixture_and_survives_restart(database):
    url, engine = database
    seed_fixture(engine)
    with TestClient(create_app(db_settings(url))) as client:
        assert_api_contract(client)
        stored = client.get("/api/stocks/AAPL/indicators?range=all").json()
    with TestClient(create_app(db_settings(url))) as restarted:
        assert restarted.get("/api/stocks/AAPL/indicators?range=all").json() == stored
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as fixture:
        offline = fixture.get("/api/stocks/AAPL/indicators?range=all").json()
        assert offline | {"snapshot_id": stored["snapshot_id"]} == stored


def test_same_date_correction_changes_the_shared_snapshot(database, monkeypatch):
    url, engine = database
    seed_fixture(engine)
    original = load_bars()
    revised = original[-1].model_copy(update={"close": original[-1].close - 0.01})
    with TestClient(create_app(db_settings(url))) as client:
        old_prices = client.get("/api/stocks/AAPL/prices").json()
        old_indicators = client.get("/api/stocks/AAPL/indicators").json()
        monkeypatch.setattr("app.seed.load_bars", lambda: (*original[:-1], revised))
        seed_fixture(engine)
        prices = client.get("/api/stocks/AAPL/prices").json()
        indicators = client.get("/api/stocks/AAPL/indicators").json()

    assert prices["as_of"] == old_prices["as_of"]
    assert prices["source"] == old_prices["source"]
    assert prices["snapshot_id"] != old_prices["snapshot_id"]
    assert indicators["snapshot_id"] == prices["snapshot_id"]
    assert indicators["points"][-1]["sma_20"] != old_indicators["points"][-1]["sma_20"]


def test_calculation_bound_and_display_bound_are_separate(database):
    url, engine = database
    seed_fixture(engine)
    count = CALCULATION_LIMIT + 3
    with engine.begin() as connection:
        connection.execute(delete(DailyBar))
        connection.execute(
            insert(DailyBar),
            [
                dict(
                    series_id=SERIES_ID,
                    session_date=date(1990, 1, 1) + timedelta(days=index),
                    open=index + 1,
                    high=index + 1,
                    low=index + 1,
                    close=index + 1,
                    volume=1,
                )
                for index in range(count)
            ],
        )
    with TestClient(create_app(db_settings(url))) as client:
        full = client.get("/api/stocks/AAPL/indicators?range=all").json()
        short = client.get("/api/stocks/AAPL/indicators?range=1mo").json()
        assert len(full["points"]) == 2000
        assert full["calculation_sessions"] == CALCULATION_LIMIT
        assert full["calculation_has_earlier"] is True
        assert full["calculation_start"] == "1990-01-04"
        assert full["has_earlier"] is True
        assert short["points"] == full["points"][-21:]
        assert full["points"][0]["sma_20"] is not None
        assert full["points"][-1]["sma_20"] == count - 9.5
        assert full["points"][-1]["rsi_14"] == 100
    with engine.begin() as connection:
        connection.execute(delete(DailyBar))
    with TestClient(create_app(db_settings(url))) as client:
        assert client.get("/api/stocks/AAPL/indicators").status_code == 404


def test_storage_failure_is_sanitized_without_fixture_fallback(monkeypatch):
    def broken(*args, **kwargs):
        raise SQLAlchemyError("private-connection-details")

    monkeypatch.setattr("app.api.stocks.database_history", broken)
    app = create_app(Settings(_env_file=None, database_url="sqlite://"))
    with TestClient(app) as client:
        response = client.get("/api/stocks/AAPL/indicators")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "DATA_UNAVAILABLE"
        assert "private-connection-details" not in response.text
