"""Migration/import/restart tests on temp SQLite and opt-in disposable PostgreSQL."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import DailyBar, database_engine
from app.main import create_app
from app.market import load_bars
from app.seed import SERIES_ID, seed_fixture

BACKEND = Path(__file__).resolve().parents[1]
DATABASES = ["sqlite"] + (
    ["postgresql"] if os.getenv("STOCKSIGHT_TEST_DATABASE_URL") else []
)


def migration_config(url):
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = url
    return config


@pytest.fixture(params=DATABASES)
def database(request, tmp_path):
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path / 'market.sqlite'}"
    else:
        url = os.environ["STOCKSIGHT_TEST_DATABASE_URL"]
        if not (make_url(url).database or "").endswith("_test"):
            pytest.fail("Only a disposable database ending in _test may be reset")
    config = migration_config(url)
    command.upgrade(config, "head")
    engine = database_engine(url)
    yield url, engine
    engine.dispose()
    command.downgrade(config, "base")


def db_settings(url):
    return Settings(_env_file=None, database_url=url)


def test_idempotent_import_correction_and_restart(database):
    url, engine = database
    assert seed_fixture(engine) == 506
    assert seed_fixture(engine) == 506
    with engine.begin() as connection:
        assert connection.scalar(select(func.count()).select_from(DailyBar)) == 506
        connection.execute(
            update(DailyBar)
            .where(
                DailyBar.series_id == SERIES_ID,
                DailyBar.session_date == load_bars()[0].date,
            )
            .values(volume=1)
        )
    seed_fixture(engine)
    with TestClient(create_app(db_settings(url))) as client:
        assert client.get("/api/ready").json() == {
            "status": "ok",
            "storage": "database",
        }
        first = client.get("/api/stocks/AAPL/prices?range=all").json()
        assert len(first["bars"]) == 506
        assert first["bars"][0]["volume"] == 63152400
        assert client.get("/api/stocks?query=apple").json()[0]["symbol"] == "AAPL"
        assert client.get("/api/stocks?query=%").json() == []
        assert client.get("/api/stocks?query=_").json() == []
        assert client.get("/api/stocks/MSFT/prices").status_code == 404
        assert client.get("/api/stocks/AAPL/prices?range=bad").status_code == 422
        for range_value, count in (("1mo", 21), ("3mo", 63), ("1y", 252)):
            response = client.get(f"/api/stocks/aapl/prices?range={range_value}").json()
            assert response["bars"] == first["bars"][-count:]
    # A new app/engine must read persisted records, not seed on startup.
    with TestClient(create_app(db_settings(url))) as restarted:
        assert restarted.get("/api/stocks/AAPL/prices?range=all").json() == first
    with TestClient(create_app(Settings(_env_file=None, database_url=None))) as fixture:
        assert fixture.get("/api/stocks/AAPL/prices?range=all").json() == first
    command.check(migration_config(url))


def test_invalid_import_rolls_back_whole_batch(database, monkeypatch):
    _, engine = database
    seed_fixture(engine)
    original = load_bars()
    bad = original[-1].model_copy(update={"volume": -1})
    corrected = original[0].model_copy(update={"volume": 1})
    monkeypatch.setattr("app.seed.load_bars", lambda: (corrected, *original[1:-1], bad))
    with pytest.raises(IntegrityError):
        seed_fixture(engine)
    with engine.connect() as connection:
        volume = connection.scalar(
            select(DailyBar.volume).where(
                DailyBar.session_date == original[0].date,
                DailyBar.series_id == SERIES_ID,
            )
        )
        assert volume == original[0].volume


def test_unmigrated_database_fails_safely_without_fixture_fallback(tmp_path):
    url = f"sqlite:///{tmp_path / 'empty.sqlite'}"
    with TestClient(create_app(db_settings(url))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 503
        response = client.get("/api/stocks/AAPL/prices")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "DATA_UNAVAILABLE"
        assert client.get("/api/stocks").status_code == 503


def test_migration_can_upgrade_again_after_downgrade(tmp_path):
    config = migration_config(f"sqlite:///{tmp_path / 'migration.sqlite'}")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)


def test_foreign_keys_reject_orphan_bars(database):
    from sqlalchemy import insert

    _, engine = database
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            insert(DailyBar).values(
                series_id="missing",
                session_date=load_bars()[0].date,
                open=10,
                high=11,
                low=9,
                close=10,
                volume=1,
            )
        )


def test_disconnected_database_never_falls_back_or_leaks_credentials():
    url = "postgresql+psycopg://review:do-not-expose@127.0.0.1:1/stocksight"
    with TestClient(create_app(db_settings(url))) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/ready").status_code == 503
        response = client.get("/api/stocks/AAPL/prices")
        assert response.status_code == 503
        assert "do-not-expose" not in response.text
        assert "127.0.0.1" not in response.text


def test_history_cap_and_source_metadata(database):
    from datetime import date, timedelta

    from sqlalchemy import insert

    from app.db import PriceSeries
    from app.repository import database_history

    url, engine = database
    seed_fixture(engine)
    # Synthetic sessions belong only to this disposable test database.
    with engine.begin() as connection:
        connection.execute(DailyBar.__table__.delete())
        connection.execute(
            update(PriceSeries)
            .where(PriceSeries.id == SERIES_ID)
            .values(source="Integration test source", adjustment="Test convention")
        )
        connection.execute(
            insert(DailyBar),
            [
                dict(
                    series_id=SERIES_ID,
                    session_date=date(2000, 1, 1) + timedelta(days=index),
                    open=10,
                    high=11,
                    low=9,
                    close=10,
                    volume=index,
                )
                for index in range(2001)
            ],
        )
    result = database_history(engine, "AAPL", "all").model_dump(mode="json")
    assert len(result["bars"]) == 2000
    assert result["session_limit"] == 2000
    assert result["has_earlier"] is True
    assert result["bars"][0]["volume"] == 1
    assert result["bars"][-1]["volume"] == 2000
    assert result["source"] == "Integration test source"
    assert result["adjustment"] == "Test convention"
    with engine.begin() as connection:
        connection.execute(DailyBar.__table__.delete().where(DailyBar.volume == 0))
    exact = database_history(engine, "AAPL", "all").model_dump(mode="json")
    assert len(exact["bars"]) == 2000
    assert exact["has_earlier"] is False


def test_search_history_adapter_contract_parity(database):
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.stocks import prices, search_stocks

    _, engine = database
    assert seed_fixture(engine) == seed_fixture(engine) == 506
    persisted = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(engine=engine))
    )
    fixture = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=None)))
    for query in ("apple", " aapl ", "unknown", "%", "_"):
        assert search_stocks(persisted, query) == search_stocks(fixture, query)
    for range_value in ("1mo", "3mo", "1y", "all"):
        stored = prices(persisted, " aapl ", range_value)
        assert stored == prices(fixture, "AAPL", range_value)
        assert len(stored.bars) <= stored.session_limit
    with pytest.raises(HTTPException) as unsupported:
        prices(persisted, "MSFT", "all")
    assert unsupported.value.status_code == 404
    assert unsupported.value.detail["code"] == "UNSUPPORTED_SYMBOL"
