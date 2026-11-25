"""Hosted connection options and PostgreSQL browser-access isolation."""

import io
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.config import Settings
from app.db import database_engine
from app.seed import seed_fixture


def migration_config(url=None, output_buffer=None):
    config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"),
        output_buffer=output_buffer,
    )
    if url is not None:
        config.attributes["database_url"] = url
    return config


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_dashboard_url_selects_installed_driver(scheme):
    engine = database_engine(
        f"{scheme}://example:secret@db.example.supabase.co/postgres"
    )
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.query["sslmode"] == "require"
        assert "secret" not in str(engine.url)
    finally:
        engine.dispose()


@pytest.mark.parametrize("mode", ["verify-ca", "verify-full"])
def test_stronger_supabase_tls_is_preserved(mode):
    engine = database_engine(
        f"postgresql://u:p@db.example.supabase.co/postgres?sslmode={mode}"
    )
    assert engine.url.query["sslmode"] == mode
    engine.dispose()


def test_transaction_pooler_disables_preparation_before_connect(monkeypatch):
    engine = database_engine(
        "postgresql://u:p@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )
    captured = {}

    def capture(*args, **kwargs):
        captured.update(kwargs)
        raise RuntimeError("No network in this connection-option test")

    monkeypatch.setattr(engine.dialect.dbapi, "connect", capture)
    with pytest.raises(RuntimeError, match="No network"):
        engine.connect()
    assert captured["prepare_threshold"] is None
    assert captured["sslmode"] == "require"
    assert captured["connect_timeout"] == 3
    assert engine.pool.size() == 1
    assert engine.pool._max_overflow == 0
    engine.dispose()


def test_supabase_options_do_not_match_other_hosts():
    engine = database_engine(
        "postgresql://u:p@db.example.supabase.co.example.org:6543/postgres"
    )
    assert "sslmode" not in engine.url.query
    assert engine.pool.size() == 5
    engine.dispose()


def test_blank_migration_url_is_optional():
    settings = Settings(_env_file=None, migration_database_url="")
    assert settings.migration_database_url is None


def test_migrations_choose_separate_connection(monkeypatch):
    monkeypatch.setenv("STOCKSIGHT_DATABASE_URL", "sqlite://")
    monkeypatch.setenv(
        "STOCKSIGHT_MIGRATION_DATABASE_URL", "postgresql+psycopg://u:p@localhost/db"
    )
    output = io.StringIO()
    command.upgrade(migration_config(output_buffer=output), "head", sql=True)
    assert "ENABLE ROW LEVEL SECURITY" in output.getvalue()
    assert "0005_backend_only_access" in output.getvalue()


@pytest.mark.skipif(
    not os.getenv("STOCKSIGHT_TEST_DATABASE_URL"), reason="Disposable PostgreSQL only"
)
def test_browser_roles_cannot_read_or_change_backend_tables():
    url = os.environ["STOCKSIGHT_TEST_DATABASE_URL"]
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Only a disposable database ending in _test may be reset")
    config = migration_config(url)
    engine = database_engine(url)
    roles = []
    try:
        # Emulate Supabase's pre-existing grants before applying migration 0005.
        command.upgrade(config, "0004_app_sessions")
        with engine.begin() as connection:
            for role in ("anon", "authenticated"):
                exists = connection.scalar(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
                )
                if not exists:
                    connection.execute(text(f"CREATE ROLE {role} NOLOGIN"))
                    roles.append(role)
                connection.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
                connection.execute(
                    text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {role}")
                )
        seed_fixture(engine)
        command.upgrade(config, "head")
        with engine.connect() as connection:
            tables = connection.execute(
                text(
                    "SELECT relname, relrowsecurity FROM pg_class "
                    "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'"
                )
            ).all()
            assert {name for name, _ in tables} == {
                "stocks",
                "price_series",
                "daily_bars",
                "user_identities",
                "watchlist_entries",
                "auth_sessions",
                "alembic_version",
                "market_refresh_runs",
                "market_bar_changes",
                "user_preferences",
            }
            assert all(enabled for _, enabled in tables)
            assert connection.scalar(text("SELECT count(*) FROM daily_bars")) == 506
        for role in ("anon", "authenticated"):
            for table, _ in tables:
                for statement in (
                    f'SELECT * FROM public."{table}"',
                    f'DELETE FROM public."{table}"',
                    f'TRUNCATE public."{table}" CASCADE',
                ):
                    with engine.connect() as connection, connection.begin():
                        connection.execute(text(f"SET LOCAL ROLE {role}"))
                        with pytest.raises(DBAPIError):
                            connection.execute(text(statement))
    finally:
        command.downgrade(config, "base")
        with engine.begin() as connection:
            for role in roles:
                connection.execute(text(f"REVOKE ALL ON SCHEMA public FROM {role}"))
                connection.execute(text(f"DROP ROLE {role}"))
        engine.dispose()
