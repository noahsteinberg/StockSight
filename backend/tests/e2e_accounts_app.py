"""TEST-ONLY signed-token issuer. Never mounted by app.main or app.demo."""

import json
import os
import time
from pathlib import Path
from typing import Literal
from uuid import uuid4

import jwt
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import database_engine
from app.factory import create_app
from app.seed import seed_fixture


def create_e2e_app():
    backend = Path(__file__).resolve().parents[1]
    cache = backend / ".pytest_cache"
    cache.mkdir(exist_ok=True)
    url = os.getenv("STOCKSIGHT_E2E_ACCOUNTS_DATABASE_URL")
    if url:
        parsed = make_url(url)
        if not parsed.drivername.startswith("postgresql") or not (
            parsed.database or ""
        ).endswith("_test"):
            raise ValueError(
                "Account E2E requires a disposable PostgreSQL _test database"
            )
    else:
        url = f"sqlite:///{cache / ('accounts-e2e-' + uuid4().hex + '.sqlite')}"
    config = Config(str(backend / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    engine = database_engine(url)
    try:
        seed_fixture(engine)
    finally:
        engine.dispose()
    domain, audience = "e2e.auth0.test", "https://stocksight-test-api"
    application = create_app(
        Settings(
            _env_file=None,
            database_url=url,
            auth0_domain=domain,
            auth0_audience=audience,
        )
    )
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwks = {"keys": [{**public, "kid": "e2e-key", "use": "sig", "alg": "RS256"}]}
    application.state.token_verifier.jwks.fetch_data = lambda: jwks

    @application.get("/api/test/identity", include_in_schema=False)
    def test_identity(user: Literal["alice", "bob"], expired: bool = False):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": "auth0|" + user,
                "iss": f"https://{domain}/",
                "aud": audience,
                "iat": now - 600 if expired else now,
                "exp": now - 60 if expired else now + 300,
            },
            private,
            algorithm="RS256",
            headers={"kid": "e2e-key"},
        )
        return {"access_token": token}

    return application
