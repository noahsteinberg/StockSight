"""Historical retrieval is descriptive, bounded and independent of outcomes."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from math import sin
from statistics import mean, stdev

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, insert, select
from test_explore import explore_client as explore_client

from app.config import Settings
from app.db import DailyBar, PriceSeries, StockRecord
from app.factory import create_app
from app.patterns import (
    PatternBar,
    Setup,
    calculate_patterns,
    choose_matches,
    percentile,
    recorded_event,
    setup_at,
)


def history(count=700):
    # Synthetic numerical test data, never served as market history.
    return [
        PatternBar(
            date(2000, 1, 1) + timedelta(days=i),
            100 + i * 0.02 + 8 * sin(i / 13) + 2 * sin(i / 3),
        )
        for i in range(count)
    ]


def calculate(bars, horizon=21):
    return calculate_patterns(
        bars,
        horizon,
        symbol="TEST",
        name="Synthetic test only",
        source="numerical test",
        source_url="https://example.test",
        adjustment="test",
        snapshot_id="test-revision",
        has_earlier=False,
    )


def test_setup_uses_only_known_trailing_prices_and_sample_variability():
    bars = history()
    index = 100
    state = setup_at(bars, index)
    closes = [b.close for b in bars]
    changes = [
        100 * (closes[i] / closes[i - 1] - 1) for i in range(index - 19, index + 1)
    ]
    assert state.change_20_pct == pytest.approx(
        100 * (closes[index] / closes[index - 20] - 1)
    )
    assert state.daily_variability_pct == pytest.approx(stdev(changes))
    assert state.vs_average_50_pct == pytest.approx(
        100 * (closes[index] / mean(closes[index - 49 : index + 1]) - 1)
    )
    mutated = [
        replace(b, close=b.close * 99) if i > index else b for i, b in enumerate(bars)
    ]
    assert setup_at(mutated, index) == state


@pytest.mark.parametrize("horizon", [5, 21])
def test_examples_are_fully_observed_non_overlapping_actual_paths(horizon):
    bars = history()
    response = calculate(bars, horizon)
    assert response.status == "available" and response.matched_count == 12
    index_by_date = {b.date: i for i, b in enumerate(bars)}
    windows = []
    for match in response.matches:
        start = index_by_date[match.date]
        assert match.end_date == bars[start + horizon].date <= response.as_of
        window = set(range(start, start + horizon + 1))
        assert all(not window.intersection(other) for other in windows)
        windows.append(window)
        assert match.path == pytest.approx(
            [
                100 * (bars[i].close / bars[start].close - 1)
                for i in range(start, start + horizon + 1)
            ]
        )
        assert match.change_pct == match.path[-1]
        assert match.setup == setup_at(bars, start)
    outcomes = sorted(m.change_pct for m in response.matches)
    assert response.summary.median_change_pct == pytest.approx(mean(outcomes[5:7]))
    assert response.summary.lower_quartile_pct == pytest.approx(
        outcomes[2] * 0.25 + outcomes[3] * 0.75
    )
    assert response.summary.upper_quartile_pct == pytest.approx(
        outcomes[8] * 0.75 + outcomes[9] * 0.25
    )
    assert (
        sum((response.summary.rose, response.summary.fell, response.summary.unchanged))
        == 12
    )
    assert all(
        p.lower_quartile <= p.median <= p.upper_quartile for p in response.points
    )
    assert response.points[0].median == 0


def test_distance_selection_has_no_outcome_input_and_deterministic_ties():
    candidates = [
        (
            i * 30,
            Setup(change_20_pct=float(i), daily_variability_pct=1, vs_average_50_pct=0),
        )
        for i in range(20)
    ]
    current = Setup(change_20_pct=9.5, daily_variability_pct=1, vs_average_50_pct=0)
    selected = choose_matches(candidates, current, 21)
    assert [index for index, _ in selected[:4]] == [270, 300, 240, 330]
    assert selected == choose_matches(list(reversed(candidates)), current, 21)
    assert percentile([0, 0, 4, 8], 0.5) == 2


def test_recorded_events_exclude_both_setup_and_outcome_windows():
    bars = history()
    bars[300] = replace(bars[300], event=True)
    result = calculate(bars)
    assert result.status == "available" and result.excluded_event_windows == 71
    positions = {b.date: i for i, b in enumerate(bars)}
    assert all(
        not (positions[m.date] - 49 <= 300 <= positions[m.date] + 21)
        for m in result.matches
    )
    bars[-2] = replace(bars[-2], event=True)
    assert calculate(bars).status == "unavailable"


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, False),
        ({"stock_splits": 0}, False),
        ({"stock_splits": 1}, False),
        ({"stock_splits": 4}, True),
        ({"stock_splits": 1.01}, True),
        ({"stock_splits": "bad"}, True),
    ],
)
def test_events_are_not_guessed_into_adjustments(value, expected):
    assert recorded_event(value) is expected


def test_flat_short_and_invalid_histories_do_not_invent_matches():
    assert calculate(history(60)).reason == "insufficient_history"
    flat = [replace(b, close=100) for b in history()]
    assert calculate(flat).reason == "insufficient_matches"
    for bad in (0, -1, float("nan"), float("inf")):
        bars = history()
        bars[100] = replace(bars[100], close=bad)
        assert calculate(bars).reason == "invalid_history"
    assert calculate(list(reversed(history()))).reason == "invalid_history"


@pytest.mark.parametrize("horizon", [5, 21])
def test_fixture_http_contract_matches_chart_revision(horizon):
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as client:
        result = client.get(f"/api/stocks/aapl/patterns?horizon_sessions={horizon}")
        assert result.status_code == 200
        body = result.json()
        prices = client.get("/api/stocks/AAPL/prices").json()
        assert body["snapshot_id"] == prices["snapshot_id"]
        assert body["as_of"] == prices["as_of"]
        assert body["horizon_sessions"] == horizon
        assert body["calculation_sessions"] == 506
        assert body["status"] == "available"


def test_http_errors_and_short_supported_history(explore_client):
    for value in (0, 6, 22, "x", "5.5"):
        assert (
            explore_client.get(
                f"/api/stocks/AAPL/patterns?horizon_sessions={value}"
            ).status_code
            == 422
        )
    assert (
        explore_client.get("/api/stocks/AAPL/patterns").json()["horizon_sessions"] == 21
    )
    for symbol in ("NOPE", "NOHIST"):
        assert explore_client.get(f"/api/stocks/{symbol}/patterns").status_code == 404
    short = explore_client.get("/api/stocks/MSFT/patterns").json()
    assert short["status"] == "unavailable"
    assert short["reason"] == "insufficient_history" and short["matches"] == []


def test_database_reads_are_bounded_atomic_and_do_not_write(explore_client):
    engine = explore_client.app.state.engine
    bars = history(2510)
    with engine.begin() as connection:
        connection.execute(
            insert(StockRecord).values(
                symbol="LONG", name="Synthetic test", exchange="TEST", currency="USD"
            )
        )
        connection.execute(
            insert(PriceSeries).values(
                id="long-test",
                symbol="LONG",
                source="test",
                source_url="https://example.test",
                adjustment="test",
                mode="historical_snapshot",
                fixture_sha256="a" * 64,
                imported_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        connection.execute(
            insert(DailyBar),
            [
                dict(
                    series_id="long-test",
                    session_date=b.date,
                    open=b.close,
                    high=b.close,
                    low=b.close,
                    close=b.close,
                    volume=0,
                )
                for b in bars
            ],
        )
        count_before = connection.scalar(select(func.count()).select_from(DailyBar))
    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = explore_client.get("/api/stocks/LONG/patterns")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available" and body["has_earlier"] is True
    assert body["calculation_sessions"] == 2500
    assert body["calculation_start"] == bars[10].date.isoformat()
    assert len(statements) == 1 and statements[0].lstrip().upper().startswith("SELECT")
    chart = explore_client.get("/api/stocks/LONG/prices").json()
    assert body["snapshot_id"] == chart["snapshot_id"]
    assert body["as_of"] == chart["as_of"]
    with engine.connect() as connection:
        assert (
            connection.scalar(select(func.count()).select_from(DailyBar))
            == count_before
        )


def test_database_failure_is_sanitized_without_fixture_fallback(tmp_path):
    client = TestClient(
        create_app(
            Settings(
                _env_file=None,
                database_url=f"sqlite:///{tmp_path / 'unmigrated.sqlite'}",
            )
        )
    )
    response = client.get("/api/stocks/AAPL/patterns")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATA_UNAVAILABLE"
