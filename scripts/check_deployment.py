"""Read-only smoke check of the deployed frontend, API, data and auth boundary."""

import argparse
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check(origin):
    parts = urlsplit(origin)
    if parts.scheme != "https" or not parts.hostname or parts.path not in {"", "/"}:
        raise ValueError("Supply an HTTPS origin without a path")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Supply only the deployment origin")
    origin = origin.rstrip("/")

    def get(path, expected=200):
        request = Request(
            origin + path, headers={"User-Agent": "StockSight-deploy-check"}
        )
        try:
            with urlopen(request, timeout=30) as response:
                status, body = response.status, response.read()
        except HTTPError as error:
            status, body = error.code, error.read()
        if status != expected:
            raise RuntimeError(f"{path}: expected {expected}, received {status}")
        return body

    assert b'id="root"' in get("/"), "Frontend HTML is missing the React root"
    assert json.loads(get("/api/health"))["status"] == "ok"
    ready = json.loads(get("/api/ready"))
    assert ready == {"status": "ok", "storage": "database"}, ready
    matches = json.loads(get("/api/stocks?query=AAPL"))
    assert any(stock["symbol"] == "AAPL" for stock in matches)
    prices = json.loads(get("/api/stocks/AAPL/prices?range=3mo"))
    indicators = json.loads(get("/api/stocks/AAPL/indicators?range=3mo"))
    bars = prices["bars"]
    assert bars and len(bars) <= 63
    assert [bar["date"] for bar in bars] == sorted(bar["date"] for bar in bars)
    assert prices["as_of"] == bars[-1]["date"]
    assert [point["date"] for point in indicators["points"]] == [
        bar["date"] for bar in bars
    ]
    assert json.loads(get("/api/auth/session"))["authenticated"] is False
    get("/api/watchlist", expected=401)
    get("/api/stocks/AAPL/prices?range=invalid", expected=422)
    print(
        json.dumps(
            {
                "origin": origin,
                "status": "passed",
                "storage": "database",
                "symbol": "AAPL",
                "as_of": prices["as_of"],
                "sessions": len(bars),
                "source": prices["source"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    check(parser.parse_args().origin)
