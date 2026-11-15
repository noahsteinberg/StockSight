"""Adversarial probes kept in the review checkout, not production tests."""

import math

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

client = TestClient(create_app(Settings(_env_file=None, app_name="isolated-review")))


@pytest.mark.parametrize("range_value,count", [("1mo",21),("3mo",63),("1y",252),("all",506)])
def test_all_ranges_retain_latest_date(range_value, count):
    response = client.get(f"/api/stocks/AAPL/prices?range={range_value}")
    assert response.status_code == 200
    result = response.json()
    assert len(result["bars"]) == count
    assert result["as_of"] == result["bars"][-1]["date"] == "2017-02-16"
    assert result["mode"] == "historical_fixture"
    for bar in result["bars"]:
        assert all(math.isfinite(bar[field]) for field in ("open", "high", "low", "close", "volume"))
        assert 0 < bar["low"] <= bar["high"]


@pytest.mark.parametrize("symbol", ["aapl", "AaPl", " AAPL "])
def test_normalization(symbol):
    assert client.get(f"/api/stocks/{symbol}/prices").json()["symbol"] == "AAPL"


@pytest.mark.parametrize("query", ["", "AAPL", "apple", "  apple  ", "Apple Inc."])
def test_search_supported_inputs(query):
    assert client.get("/api/stocks", params={"query":query}).json() == [{"symbol":"AAPL","name":"Apple Inc."}]


@pytest.mark.parametrize("range_value", ["", "0", "ALL", "-1", "1d", "x" * 1000])
def test_bad_range_is_validation_error(range_value):
    assert client.get("/api/stocks/AAPL/prices", params={"range":range_value}).status_code == 422


@pytest.mark.parametrize("symbol", ["MSFT", "unknown", "' OR 1=1 --", "☃"])
def test_bad_symbols_do_not_leak_or_crash(symbol):
    response=client.get(f"/api/stocks/{symbol}/prices")
    assert response.status_code == 404
    assert response.json() == {"detail":{"code":"UNSUPPORTED_SYMBOL","message":"Try AAPL."}}


def test_liveness_and_method_boundaries():
    assert client.get("/api/health").json() == {"status":"ok","service":"isolated-review"}
    assert client.post("/api/stocks/AAPL/prices").status_code == 405
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/openapi.json").status_code == 200


def test_defaults_and_repeatability():
    first=client.get("/api/stocks/AAPL/prices").json()
    assert first == client.get("/api/stocks/AAPL/prices?range=3mo").json()
    assert first == client.get("/api/stocks/AAPL/prices").json()
