"""Exercise storage failures without requiring network sockets or real credentials."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from app.api.health import readiness
from app.db import Base, DailyBar, database_engine
from app.demo import create_demo_app
from app.seed import seed_fixture
from app.storage import storage_problem


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{tmp_path / 'diagnostics.sqlite'}")
    yield engine
    engine.dispose()


def test_missing_schema_is_actionable_and_readiness_fails(engine):
    assert storage_problem(engine)["code"] == "SCHEMA_MISSING"
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=engine)))
    with pytest.raises(HTTPException) as failure:
        readiness(request)
    assert failure.value.status_code == 503
    assert failure.value.detail["code"] == "SCHEMA_MISSING"


def test_partial_schema_does_not_pass_readiness(engine):
    DailyBar.__table__.create(engine)
    assert storage_problem(engine)["code"] == "SCHEMA_MISSING"


def test_empty_then_seeded_storage(engine):
    Base.metadata.create_all(engine)
    assert storage_problem(engine)["code"] == "DATA_NOT_IMPORTED"
    seed_fixture(engine)
    assert storage_problem(engine) is None
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=engine)))
    assert readiness(request) == {"status": "ok", "storage": "database"}
    # An incompatible referenced table must not pass merely because bars exist.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE price_series RENAME COLUMN source TO old_source"
        )
    assert storage_problem(engine)["code"] == "STORAGE_UNAVAILABLE"


@pytest.mark.parametrize(
    ("state", "code"),
    [
        ("28P01", "DATABASE_AUTH_FAILED"),
        ("3D000", "DATABASE_MISSING"),
        (None, "STORAGE_UNAVAILABLE"),
    ],
)
def test_database_errors_do_not_reveal_driver_details(state, code):
    class DriverFailure(Exception):
        sqlstate = state

    class BrokenEngine:
        def connect(self):
            raise OperationalError("secret SQL", {}, DriverFailure("secret password"))

    problem = storage_problem(BrokenEngine())
    assert problem["code"] == code
    assert "secret" not in str(problem)


def test_demo_ignores_even_invalid_database_environment(monkeypatch):
    monkeypatch.setenv("STOCKSIGHT_DATABASE_URL", "invalid-database-url-with-secret")
    app = create_demo_app()
    assert app.state.engine is None
    assert app.state.settings.database_url is None
    request = SimpleNamespace(app=app)
    assert readiness(request) == {"status": "ok", "storage": "fixture"}


def test_unavailable_storage_never_becomes_fixture(engine):
    from app.api.stocks import prices

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=engine)))
    with pytest.raises(HTTPException) as failure:
        prices(request, "AAPL", "3mo")
    assert failure.value.status_code == 503
    assert failure.value.detail["code"] == "DATA_UNAVAILABLE"
