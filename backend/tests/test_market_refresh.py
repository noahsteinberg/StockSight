"""Incremental persistence contracts; no real provider or hosted database writes."""

import os
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import (
    DailyBar,
    MarketBarChange,
    MarketRefreshRun,
    PriceSeries,
    StockRecord,
    database_engine,
)
from app.indicators import calculate_indicators
from app.main import create_app
from app.market_refresh import (
    apply_refresh,
    plan_refresh,
    read_snapshot,
    restore_refresh,
)
from app.repository import database_history
from app.yahoo_provider import Download, completed_sessions

NOW = datetime(2026, 11, 24, 12, tzinfo=UTC)
DATES = [date(2026, 11, d) for d in (9, 10, 11, 12)]
EXTRA = [date(2026, 11, d) for d in (13, 16, 17)]
BACKEND = Path(__file__).resolve().parents[1]
DATABASES = ["sqlite"] + (
    ["postgresql"] if os.getenv("STOCKSIGHT_TEST_DATABASE_URL") else []
)


@pytest.fixture(params=DATABASES)
def engine(request, tmp_path):
    url = (
        f"sqlite:///{tmp_path / 'refresh.sqlite'}"
        if request.param == "sqlite"
        else os.environ["STOCKSIGHT_TEST_DATABASE_URL"]
    )
    if request.param == "postgresql" and not (make_url(url).database or "").endswith(
        "_test"
    ):
        pytest.fail("Disposable _test database required")
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    eng = database_engine(url)
    with eng.begin() as conn:
        conn.execute(
            StockRecord.__table__.insert(),
            dict(symbol="AAPL", name="Apple", exchange="NASDAQ", currency="USD"),
        )
        conn.execute(
            PriceSeries.__table__.insert(),
            dict(
                id="team-yahoo-v1-AAPL",
                symbol="AAPL",
                source="team snapshot",
                source_url="https://finance.yahoo.com/",
                mode="historical_snapshot",
                adjustment="unverified",
                fixture_sha256="a" * 64,
                imported_at=datetime(2026, 11, 12, tzinfo=UTC),
            ),
        )
        conn.execute(
            DailyBar.__table__.insert(),
            [
                dict(
                    series_id="team-yahoo-v1-AAPL",
                    session_date=d,
                    open=10,
                    high=12,
                    low=9,
                    close=11,
                    volume=100,
                    source_values=dict(
                        adj_close=10.5, dividends=0.0, stock_splits=0.0, bad_bar=False
                    ),
                )
                for d in DATES
            ],
        )
    yield eng
    eng.dispose()
    command.downgrade(config, "base")


def rows(dates):
    return [
        dict(
            ticker="AAPL",
            date=d.isoformat(),
            open=10.0,
            high=12.0,
            low=9.0,
            close=11.0,
            volume=100,
            adj_close=10.5,
            dividends=0.0,
            stock_splits=0.0,
        )
        for d in dates
    ]


def plan(engine, data=None, completed=None):
    snapshot = read_snapshot(engine, "AAPL")
    data = rows(sorted(snapshot.bars) + EXTRA) if data is None else data
    return plan_refresh(
        snapshot,
        Download(data, "yfinance/test", "b" * 64, NOW),
        min(snapshot.bars),
        max(EXTRA),
        set(DATES + EXTRA) if completed is None else completed,
    )


def test_append_repeat_api_alignment_and_restore(engine):
    before = read_snapshot(engine, "AAPL")
    preview = plan(engine)
    assert preview.report()["inserts"] == [d.isoformat() for d in EXTRA]
    assert read_snapshot(engine, "AAPL") == before  # planning is read-only
    result = apply_refresh(engine, preview)
    assert result["changed_bars"] == 3
    history = database_history(engine, "AAPL", "all")
    assert history.mode == "daily_history"
    assert history.as_of == EXTRA[-1]
    assert history.last_refreshed_at is not None
    assert calculate_indicators(history, "all").snapshot_id == history.snapshot_id
    assert (
        read_snapshot(engine, "AAPL").bars | before.bars
        == read_snapshot(engine, "AAPL").bars
    )
    repeat = plan(engine, rows(DATES + EXTRA))
    assert not repeat.updates
    assert apply_refresh(engine, repeat)["snapshot_id"] == result["snapshot_id"]
    with TestClient(
        create_app(
            Settings(
                _env_file=None,
                database_url=engine.url.render_as_string(hide_password=False),
            )
        )
    ) as client:
        price = client.get("/api/stocks/AAPL/prices?range=all").json()
        indicator = client.get("/api/stocks/AAPL/indicators?range=all").json()
        assert price["as_of"] == "2026-11-17"
        assert price["snapshot_id"] == indicator["snapshot_id"]
        assert price["last_refreshed_at"] == indicator["last_refreshed_at"]
    restore_refresh(engine, result["run_id"])
    assert read_snapshot(engine, "AAPL").bars == before.bars
    assert database_history(engine, "AAPL", "all").mode == "historical_snapshot"


def test_volume_correction_and_adjustment_vintage(engine):
    data = rows(DATES)
    data[-1]["volume"] = 120
    data[0]["adj_close"] = 10.0
    p = plan(engine, data, completed=set(DATES))
    assert p.adjusted_changes
    result = apply_refresh(engine, p)
    updated = read_snapshot(engine, "AAPL")
    assert updated.bars[DATES[-1]]["volume"] == 120
    assert updated.bars[DATES[0]]["source_values"]["adj_close"] == 10.5
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(MarketBarChange)) == 1
    restore_refresh(engine, result["run_id"])
    assert read_snapshot(engine, "AAPL").bars[DATES[-1]]["volume"] == 100


@pytest.mark.parametrize(
    "mutation",
    ["price", "split", "duplicate", "missing_overlap", "symbol", "unexpected_date"],
)
def test_incompatible_data_blocks_all_writes(engine, mutation):
    data = rows(DATES + EXTRA)
    if mutation == "price":
        data[0]["close"] = 11.5
    if mutation == "split":
        data[-1]["stock_splits"] = 2.0
    if mutation == "duplicate":
        data.insert(1, deepcopy(data[0]))
    if mutation == "missing_overlap":
        data.pop(0)
    if mutation == "symbol":
        data[0]["ticker"] = "MSFT"
    if mutation == "unexpected_date":
        data[0]["date"] = "2000-01-01"
    p = plan(engine, data)
    before = read_snapshot(engine, "AAPL")
    assert p.blockers and not p.updates
    with pytest.raises(ValueError, match="blocked"):
        apply_refresh(engine, p)
    assert read_snapshot(engine, "AAPL") == before


def test_incomplete_session_does_not_advance_past_gap(engine):
    data = rows(DATES + EXTRA)
    data[len(DATES)]["close"] = None
    p = plan(engine, data)
    assert p.missing == [EXTRA[0]]
    assert not p.updates
    assert p.rejected
    assert apply_refresh(engine, p)["status"] == "partial"


def test_unfinished_session_is_excluded(engine):
    p = plan(engine, completed=set(DATES + EXTRA[:-1]))
    assert EXTRA[-1] not in p.updates
    assert p.rejected[-1]["reasons"] == ["session_not_finalized"]


def test_stale_preview_refuses_concurrent_change(engine):
    first, second = plan(engine), plan(engine)
    apply_refresh(engine, first)
    with pytest.raises(ValueError, match="changed since preview"):
        apply_refresh(engine, second)


def test_newer_revision_refuses_restore(engine):
    first = apply_refresh(engine, plan(engine))
    data = rows(DATES + EXTRA)
    data[-1]["volume"] = 101
    apply_refresh(engine, plan(engine, data))
    with pytest.raises(ValueError, match="newer series"):
        restore_refresh(engine, first["run_id"])


def test_retention_restore_and_original_fingerprint(engine):
    # Populate 2500 old records, then keep newest rows without losing recovery data.
    with engine.begin() as conn:
        conn.execute(DailyBar.__table__.delete())
        days = [DATES[-1] - timedelta(days=n) for n in reversed(range(2500))]
        conn.execute(
            DailyBar.__table__.insert(),
            [
                dict(
                    series_id="team-yahoo-v1-AAPL",
                    session_date=d,
                    open=10,
                    high=12,
                    low=9,
                    close=11,
                    volume=100,
                    source_values=dict(
                        adj_close=10.5, dividends=0.0, stock_splits=0.0, bad_bar=False
                    ),
                )
                for d in days
            ],
        )
    before = read_snapshot(engine, "AAPL")
    data = rows(sorted(before.bars)[-20:] + EXTRA)
    p = plan_refresh(
        before,
        Download(data, "test", "c" * 64, NOW),
        sorted(before.bars)[-20],
        EXTRA[-1],
        set(days + EXTRA),
    )
    result = apply_refresh(engine, p)
    after = read_snapshot(engine, "AAPL")
    assert len(after.bars) == 2500 and min(after.bars) == days[3]
    with engine.connect() as conn:
        assert conn.scalar(select(PriceSeries.fixture_sha256)) == "a" * 64
    restore_refresh(engine, result["run_id"])
    assert read_snapshot(engine, "AAPL").bars == before.bars


def test_failure_rolls_back_bars_and_audit(engine, monkeypatch):
    p = plan(engine)
    original = read_snapshot(engine, "AAPL")
    from sqlalchemy.orm import Session

    real_flush = Session.flush
    calls = 0

    def fail_flush(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise RuntimeError("Injected persistence failure")
        return real_flush(self, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_flush)
    with pytest.raises(RuntimeError):
        apply_refresh(engine, p)
    monkeypatch.setattr(Session, "flush", real_flush)
    assert read_snapshot(engine, "AAPL") == original
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(MarketRefreshRun)) == 0


def test_calendar_holiday_early_close_and_finalization():
    # Thanksgiving closed; the following Friday closes at 13:00 New York time.
    start, end = date(2026, 11, 26), date(2026, 11, 27)
    before = completed_sessions(start, end, datetime(2026, 11, 27, 18, 15, tzinfo=UTC))
    after = completed_sessions(start, end, datetime(2026, 11, 27, 18, 31, tzinfo=UTC))
    assert date(2026, 11, 26) not in after
    assert end not in before and end in after


def test_real_provider_adapter_retries_without_exposing_errors(monkeypatch):
    import yfinance

    from app.yahoo_provider import fetch_yahoo

    calls = []
    sleeps = []

    class BrokenTicker:
        def history(self, **kwargs):
            calls.append(kwargs)
            raise ConnectionError("private-url-must-not-appear")

    monkeypatch.setattr(yfinance, "Ticker", lambda symbol: BrokenTicker())
    monkeypatch.setattr("app.yahoo_provider.time.sleep", sleeps.append)
    with pytest.raises(
        ValueError, match=r"Yahoo request failed \(ConnectionError\)"
    ) as error:
        fetch_yahoo("AAPL", DATES[0], DATES[-1])
    assert "private-url" not in str(error.value)
    assert len(calls) == 3 and sleeps == [2, 5]
    assert calls[0]["auto_adjust"] is False and calls[0]["repair"] is False
    assert calls[0]["timeout"] == 20


def test_failed_provider_is_read_only_in_preview_and_journaled_in_write_mode(engine):
    from app.refresh_prices import run_symbol

    before = read_snapshot(engine, "AAPL")

    def failure(*args):
        raise ValueError("Provider failed")

    with pytest.raises(ValueError):
        run_symbol(engine, "AAPL", fetch=failure, now=NOW)
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(MarketRefreshRun)) == 0
    result = run_symbol(engine, "AAPL", True, fetch=failure, now=NOW)
    assert result["status"] == "error"
    assert read_snapshot(engine, "AAPL") == before
    with engine.connect() as conn:
        assert conn.scalar(select(MarketRefreshRun.status)) == "error"


def test_two_concurrent_writers_commit_only_one_revision(engine):
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock semantics")
    from concurrent.futures import ThreadPoolExecutor

    previews = [plan(engine), plan(engine)]

    def write(preview):
        try:
            return apply_refresh(engine, preview)["status"]
        except ValueError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(write, previews))
    assert sorted(results) == ["stale", "success"]
    assert len(read_snapshot(engine, "AAPL").bars) == len(DATES + EXTRA)


def test_write_mode_journals_blocked_compatibility_without_changing_bars(engine):
    from app.refresh_prices import run_symbol

    before = read_snapshot(engine, "AAPL")
    data = rows(DATES + EXTRA)
    data[0]["close"] = 11.5
    result = run_symbol(
        engine,
        "AAPL",
        True,
        fetch=lambda *args: Download(data, "test", "c" * 64, NOW),
        now=NOW,
    )
    assert result["status"] == "blocked"
    assert read_snapshot(engine, "AAPL") == before
    with engine.connect() as conn:
        details = conn.scalar(select(MarketRefreshRun.details))
        assert details["error_type"] == "CompatibilityBlocked"
        assert conn.scalar(select(func.count()).select_from(MarketBarChange)) == 0
