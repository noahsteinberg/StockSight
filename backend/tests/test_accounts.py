"""Real signed tokens and isolated storage exercise private account contracts."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jwt import PyJWKClientConnectionError
from sqlalchemy import insert
from sqlalchemy.engine import make_url

from app.auth import TokenVerifier
from app.config import Settings
from app.db import PriceSeries, StockRecord, database_engine
from app.factory import create_app
from app.seed import seed_fixture

ISSUER = "https://tenant.auth0.test/"
AUDIENCE = "https://stocksight-api"
BACKEND = Path(__file__).resolve().parents[1]
DATABASES = ["sqlite"] + (
    ["postgresql"] if os.getenv("STOCKSIGHT_TEST_DATABASE_URL") else []
)


@pytest.fixture(scope="module")
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    return private, {
        "keys": [{**public, "kid": "test-key", "use": "sig", "alg": "RS256"}]
    }


@pytest.fixture
def token(keys):
    def make(subject="auth0|alice", **changes):
        claims = {
            "sub": subject,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        }
        claims.update(changes)
        return jwt.encode(
            claims, keys[0], algorithm="RS256", headers={"kid": "test-key"}
        )

    return make


@pytest.fixture(params=DATABASES)
def accounts_database(request, tmp_path):
    url = (
        f"sqlite:///{tmp_path / 'accounts.sqlite'}"
        if request.param == "sqlite"
        else os.environ["STOCKSIGHT_TEST_DATABASE_URL"]
    )
    if request.param == "postgresql" and not (make_url(url).database or "").endswith(
        "_test"
    ):
        pytest.fail("Only disposable PostgreSQL databases ending in _test may be reset")
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    engine = database_engine(url)
    seed_fixture(engine)
    yield url, engine
    engine.dispose()
    command.downgrade(config, "base")


@pytest.fixture
def account_app(accounts_database, keys, monkeypatch):
    url, _ = accounts_database
    application = create_app(
        Settings(
            _env_file=None,
            database_url=url,
            auth0_domain="tenant.auth0.test",
            auth0_audience=AUDIENCE,
        )
    )
    monkeypatch.setattr(
        application.state.token_verifier.jwks, "fetch_data", lambda: keys[1]
    )
    return application


def headers(value):
    return {"Authorization": f"Bearer {value}"}


def test_watchlist_persistence_identity_and_two_user_isolation(account_app, token):
    alice, bob = headers(token()), headers(token("auth0|bob"))
    with TestClient(account_app) as client:
        assert client.get("/api/watchlist").status_code == 401
        identity = client.get("/api/me", headers=alice).json()
        first = client.post("/api/watchlist", headers=alice, json={"symbol": " aapl "})
        assert first.status_code == 201
        assert first.json()["symbol"] == "AAPL"
        assert first.json()["added_at"].endswith("Z")
        repeated = client.post("/api/watchlist", headers=alice, json={"symbol": "AAPL"})
        assert repeated.status_code == 200
        assert repeated.json() == first.json()
        response = client.get("/api/watchlist", headers=alice)
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {"items": [first.json()], "limit": 100}
        assert client.get("/api/watchlist", headers=bob).json()["items"] == []
        assert client.delete("/api/watchlist/AAPL", headers=bob).status_code == 204
        assert client.get("/api/watchlist", headers=alice).json()["items"] == [
            first.json()
        ]
        assert (
            client.get("/api/watchlist?user_id=" + identity["id"], headers=bob).json()[
                "items"
            ]
            == []
        )
        assert (
            client.post(
                "/api/watchlist",
                headers=bob,
                json={"symbol": "AAPL", "user_id": identity["id"]},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/watchlist", headers=alice, json={"symbol": "MISSING"}
            ).status_code
            == 404
        )
        assert (
            client.delete("/api/watchlist/invalid!", headers=alice).status_code == 422
        )
    # A newly created API/engine must retain the same identity and saved entries.
    settings = account_app.state.settings
    restarted = create_app(settings)
    restarted.state.token_verifier = account_app.state.token_verifier
    with TestClient(restarted) as client:
        assert client.get("/api/me", headers=alice).json() == identity
        assert len(client.get("/api/watchlist", headers=alice).json()["items"]) == 1
        assert client.delete("/api/watchlist/aapl", headers=alice).status_code == 204
        assert client.delete("/api/watchlist/AAPL", headers=alice).status_code == 204
        assert client.get("/api/watchlist", headers=alice).json()["items"] == []
        assert (
            client.get(
                "/api/watchlist", headers=headers(token(exp=int(time.time()) - 60))
            ).status_code
            == 401
        )


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"iss": "https://other-tenant.auth0.test/"},
        {"aud": "spa-client-id"},
        {"sub": ""},
        {"sub": "x" * 256},
        {"sub": "machine@clients"},
        {"gty": "client-credentials"},
        {"nbf": 4102444800},
        {"iat": 4102444800},
    ],
)
def test_wrong_expired_or_non_user_tokens_are_rejected(
    keys, token, claims, monkeypatch
):
    verifier = TokenVerifier(
        Settings(
            _env_file=None, auth0_domain="tenant.auth0.test", auth0_audience=AUDIENCE
        )
    )
    monkeypatch.setattr(verifier.jwks, "fetch_data", lambda: keys[1])
    with pytest.raises(HTTPException) as error:
        verifier.verify(token(**claims))
    assert error.value.status_code == 401


def test_signature_required_claims_algorithm_and_jwks_failures(
    keys, token, monkeypatch
):
    verifier = TokenVerifier(
        Settings(
            _env_file=None, auth0_domain="tenant.auth0.test", auth0_audience=AUDIENCE
        )
    )
    monkeypatch.setattr(verifier.jwks, "fetch_data", lambda: keys[1])
    missing = jwt.encode(
        {"sub": "auth0|alice", "iss": ISSUER, "aud": AUDIENCE},
        keys[0],
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        {
            "sub": "auth0|alice",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
        },
        wrong_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    for invalid in (
        "garbage",
        missing,
        forged,
        jwt.encode(
            {"sub": "alice"}, "a" * 32, algorithm="HS256", headers={"kid": "test-key"}
        ),
    ):
        with pytest.raises(HTTPException) as error:
            verifier.verify(invalid)
        assert error.value.status_code == 401

    def disconnected():
        raise PyJWKClientConnectionError("secret driver details")

    monkeypatch.setattr(verifier.jwks, "fetch_data", disconnected)
    assert verifier.verify(token()).subject == "auth0|alice"
    # Cached known keys remain usable during an outage; a cold cache must fail.
    verifier = TokenVerifier(
        Settings(
            _env_file=None, auth0_domain="tenant.auth0.test", auth0_audience=AUDIENCE
        )
    )
    monkeypatch.setattr(verifier.jwks, "fetch_data", disconnected)
    with pytest.raises(HTTPException) as error:
        verifier.verify(token())
    assert error.value.status_code == 503
    assert "secret" not in str(error.value.detail)
    monkeypatch.setattr(verifier.jwks, "fetch_data", lambda: {"keys": []})
    with pytest.raises(HTTPException) as error:
        verifier.verify(token())
    assert error.value.status_code == 503


def test_missing_configuration_and_storage_fail_closed(
    token, keys, monkeypatch, tmp_path
):
    with TestClient(
        create_app(
            Settings(
                _env_file=None,
                database_url=None,
                auth0_domain=None,
                auth0_audience=None,
            )
        )
    ) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/me").status_code == 401
        assert (
            client.get("/api/me", headers=headers(token())).json()["detail"]["code"]
            == "AUTH_NOT_CONFIGURED"
        )
        assert client.get("/api/test/identity?user=alice").status_code == 404
    for url in (None, f"sqlite:///{tmp_path / 'unmigrated.sqlite'}"):
        application = create_app(
            Settings(
                _env_file=None,
                database_url=url,
                auth0_domain="tenant.auth0.test",
                auth0_audience=AUDIENCE,
            )
        )
        monkeypatch.setattr(
            application.state.token_verifier.jwks, "fetch_data", lambda: keys[1]
        )
        with TestClient(application) as client:
            response = client.get("/api/watchlist", headers=headers(token()))
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "ACCOUNT_STORAGE_UNAVAILABLE"


def test_watchlist_capacity_and_duplicate_at_capacity(
    account_app, accounts_database, token
):
    _, engine = accounts_database
    with engine.begin() as connection:
        for index in range(101):
            symbol = f"Z{index:03d}"
            connection.execute(
                insert(StockRecord).values(
                    symbol=symbol, name=symbol, exchange="TEST", currency="USD"
                )
            )
            connection.execute(
                insert(PriceSeries).values(
                    id=symbol,
                    symbol=symbol,
                    source="test",
                    source_url="https://example.test",
                    mode="historical_snapshot",
                    adjustment="test",
                    fixture_sha256="a" * 64,
                    imported_at=datetime.now(UTC),
                )
            )
    with TestClient(account_app) as client:
        auth = headers(token())
        for index in range(100):
            assert (
                client.post(
                    "/api/watchlist", headers=auth, json={"symbol": f"Z{index:03d}"}
                ).status_code
                == 201
            )
        assert (
            client.post(
                "/api/watchlist", headers=auth, json={"symbol": "Z099"}
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/watchlist", headers=auth, json={"symbol": "Z100"}
            ).status_code
            == 409
        )
        assert len(client.get("/api/watchlist", headers=auth).json()["items"]) == 100


def test_concurrent_duplicate_adds_are_idempotent_on_postgresql(
    account_app, accounts_database, token
):
    _, engine = accounts_database
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency contract")
    with TestClient(account_app) as client:
        auth = headers(token())

        def add(_):
            return client.post(
                "/api/watchlist", headers=auth, json={"symbol": "AAPL"}
            ).status_code

        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(add, range(12)))
        assert statuses.count(201) == 1
        assert statuses.count(200) == 11
        assert len(client.get("/api/watchlist", headers=auth).json()["items"]) == 1
