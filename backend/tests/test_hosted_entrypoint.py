"""Hosted startup must fail closed without production configuration."""

import importlib.util
from pathlib import Path

import pytest


def load_entrypoint():
    spec = importlib.util.spec_from_file_location(
        "stocksight_hosted_entrypoint", Path(__file__).parents[1] / "vercel_app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_hosted_startup_requires_database(monkeypatch):
    monkeypatch.setenv("STOCKSIGHT_DATABASE_URL", "")
    with pytest.raises(RuntimeError, match="STOCKSIGHT_DATABASE_URL"):
        load_entrypoint()


def test_hosted_startup_requires_https_origin(monkeypatch):
    monkeypatch.setenv("STOCKSIGHT_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("STOCKSIGHT_APP_ORIGIN", "http://127.0.0.1:5173")
    with pytest.raises(RuntimeError, match="STOCKSIGHT_APP_ORIGIN"):
        load_entrypoint()


def test_hosted_startup_requires_auth_settings(monkeypatch):
    monkeypatch.setenv("STOCKSIGHT_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("STOCKSIGHT_APP_ORIGIN", "https://stocksight.example")
    monkeypatch.setenv("STOCKSIGHT_AUTH0_DOMAIN", "")
    monkeypatch.setenv("STOCKSIGHT_AUTH0_AUDIENCE", "")
    with pytest.raises(RuntimeError, match="Auth0"):
        load_entrypoint()


def test_hosted_app_preserves_api_routes_without_startup_writes(monkeypatch):
    monkeypatch.setenv("STOCKSIGHT_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("STOCKSIGHT_APP_ORIGIN", "https://stocksight.example")
    monkeypatch.setenv("STOCKSIGHT_AUTH0_DOMAIN", "tenant.auth0.com")
    monkeypatch.setenv("STOCKSIGHT_AUTH0_AUDIENCE", "https://stocksight-api")
    app = load_entrypoint()
    try:
        paths = app.openapi()["paths"]
        assert "/api/health" in paths
        assert "/api/stocks/{symbol}/prices" in paths
        assert "/api/watchlist" in paths
        from sqlalchemy import inspect

        assert inspect(app.state.engine).get_table_names() == []
    finally:
        app.state.engine.dispose()
