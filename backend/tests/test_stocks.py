from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

client = TestClient(create_app(Settings(_env_file=None, database_url=None)))


def test_history_uses_latest_ordered_real_observations():
    full = client.get("/api/stocks/AAPL/prices?range=all").json()
    short = client.get("/api/stocks/aapl/prices?range=1mo").json()
    assert len(full["bars"]) > 252
    assert short["bars"] == full["bars"][-21:]
    assert short["as_of"] == full["bars"][-1]["date"]
    dates = [bar["date"] for bar in full["bars"]]
    assert dates == sorted(set(dates))
    first = full["bars"][0]
    assert first["date"] == "2015-02-17"
    assert first["close"] == 127.830002
    assert first["volume"] == 63152400
    for bar in full["bars"]:
        assert bar["low"] <= min(bar["open"], bar["close"])
        assert bar["high"] >= max(bar["open"], bar["close"])
        assert bar["volume"] >= 0


def test_rejects_unsupported_symbol_and_invalid_range():
    assert client.get("/api/stocks/MSFT/prices").status_code == 404
    assert client.get("/api/stocks/AAPL/prices?range=invalid").status_code == 422


def test_supported_symbol_search():
    assert client.get("/api/stocks?query=apple").json()[0]["symbol"] == "AAPL"
    assert client.get("/api/stocks?query=unknown").json() == []
    assert client.get("/api/stocks", params={"query": "x" * 41}).status_code == 422


def test_history_reports_display_bounds():
    from types import SimpleNamespace

    from app.api.stocks import prices

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=None)))
    full = prices(request, "AAPL", "all").model_dump(mode="json")
    short = prices(request, "aapl", "1mo").model_dump(mode="json")
    assert full["session_limit"] == 2000
    assert full["has_earlier"] is False
    assert short["session_limit"] == 21
    assert short["has_earlier"] is True
