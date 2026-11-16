"""Check orchestration safeguards without touching Docker or a live database."""

import subprocess
from datetime import date

import pytest
from sqlalchemy import update

from app import complete_backend as setup
from app.config import Settings
from app.db import Base, PriceSeries, database_engine
from app.import_prices import write_symbol


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///market.sqlite",
        "postgresql+psycopg://u:p@remote.example:5433/stocksight",
        "postgresql+psycopg://u:p@127.0.0.1:5432/stocksight",
        "postgresql+psycopg://u:p@127.0.0.1:5433/other",
    ],
)
def test_setup_refuses_unrelated_databases(url):
    settings = Settings(_env_file=None, database_url=url)
    with pytest.raises(ValueError, match="local Compose"):
        setup.local_database_url(settings)


def test_subset_preserves_fingerprint_and_does_not_mutate_report():
    counts = {"AAPL": 4, "MSFT": 5, "NVDA": 6, "ZZZ": 7}
    report = {"sha256": "a" * 64, "accepted_by_symbol": counts}
    small = setup.subset_report(report)
    assert small["sha256"] == report["sha256"]
    assert small["accepted_by_symbol"] == {"AAPL": 4, "MSFT": 5, "NVDA": 6}
    assert report["accepted_by_symbol"] == counts
    with pytest.raises(ValueError, match="Dataset must contain"):
        setup.subset_report({"accepted_by_symbol": {"AAPL": 4}})


def test_count_verification_rejects_wrong_counts_and_hashes(tmp_path):
    engine = database_engine(f"sqlite:///{tmp_path / 'setup.sqlite'}")
    try:
        Base.metadata.create_all(engine)
        for symbol in setup.SAMPLE:
            write_symbol(
                engine,
                symbol,
                [
                    {
                        "session_date": date(2020, 1, 1),
                        "open": 10,
                        "high": 11,
                        "low": 9,
                        "close": 10,
                        "volume": 1,
                    }
                ],
                "a" * 64,
            )
        report = {
            "sha256": "a" * 64,
            "accepted_by_symbol": {symbol: 1 for symbol in setup.SAMPLE},
        }
        assert setup.verify_counts(engine, report) == {"symbols": 3, "rows": 3}
        with pytest.raises(ValueError, match="do not match"):
            setup.verify_counts(
                engine,
                {
                    **report,
                    "accepted_by_symbol": {"AAPL": 2, "MSFT": 1, "NVDA": 1},
                },
            )
        with engine.begin() as connection:
            connection.execute(update(PriceSeries).values(fixture_sha256="b" * 64))
        with pytest.raises(ValueError, match="do not match"):
            setup.verify_counts(engine, report)
    finally:
        engine.dispose()


def test_failed_docker_step_does_not_continue_or_claim_completion(
    tmp_path, monkeypatch, capsys
):
    source = tmp_path / "test.parquet"
    source.touch()
    monkeypatch.setattr("sys.argv", ["complete_backend", str(source)])
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@127.0.0.1:5433/stocksight",
    )
    monkeypatch.setattr(setup, "Settings", lambda: settings)
    monkeypatch.setattr(setup.importlib.util, "find_spec", lambda _: object())
    monkeypatch.setattr(
        setup,
        "scan",
        lambda _: {
            "accepted_by_symbol": {symbol: 1 for symbol in setup.SAMPLE},
            "accepted": 3,
            "quarantined": 0,
        },
    )

    def failed_docker(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    def unexpected_migration(*args, **kwargs):
        pytest.fail("Migrations must not run after Docker startup fails")

    monkeypatch.setattr(setup.subprocess, "run", failed_docker)
    monkeypatch.setattr(setup.command, "upgrade", unexpected_migration)
    assert setup.main() == 1
    output = capsys.readouterr().out
    assert "no completion claimed" in output
    assert "BACKEND VERIFIED" not in output
