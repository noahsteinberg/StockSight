"""Complete the local Compose database setup from a normal developer terminal."""

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db import DailyBar, PriceSeries, database_engine
from app.environment_check import docker_status
from app.import_prices import import_snapshot, scan

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
SAMPLE = {"AAPL", "MSFT", "NVDA"}


def local_database_url(settings):
    if settings.database_url is None:
        raise ValueError("Set the local Compose database URL in backend/.env first")
    value = settings.database_url.get_secret_value()
    url = make_url(value)
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.port != 5433
        or url.database != "stocksight"
    ):
        raise ValueError(
            "This command requires the local Compose database on port 5433"
        )
    return value


def subset_report(report):
    counts = report["accepted_by_symbol"]
    if not SAMPLE <= counts.keys():
        raise ValueError("Dataset must contain accepted AAPL, MSFT and NVDA rows")
    return {
        **report,
        "accepted_by_symbol": {symbol: counts[symbol] for symbol in sorted(SAMPLE)},
    }


def verify_counts(engine, report):
    expected = report["accepted_by_symbol"]
    with engine.connect() as connection:
        found = dict(
            connection.execute(
                select(PriceSeries.symbol, func.count(DailyBar.session_date))
                .join(DailyBar, DailyBar.series_id == PriceSeries.id)
                .where(PriceSeries.symbol.in_(expected))
                .group_by(PriceSeries.symbol)
            ).all()
        )
        metadata = connection.execute(
            select(PriceSeries.mode, PriceSeries.fixture_sha256).where(
                PriceSeries.symbol.in_(expected)
            )
        ).all()
    if found != expected or any(
        mode != "historical_snapshot" or digest != report["sha256"]
        for mode, digest in metadata
    ):
        raise ValueError(
            "Stored counts/source hashes do not match the validated snapshot"
        )
    return {"symbols": len(found), "rows": sum(found.values())}


def verify_api(url, report):
    from fastapi.testclient import TestClient

    from app.factory import create_app

    settings = Settings(_env_file=None, database_url=url)
    with TestClient(create_app(settings)) as client:
        ready = client.get("/api/ready")
        if ready.status_code != 200 or ready.json().get("storage") != "database":
            raise ValueError("Database-backed API readiness check failed")
        for symbol in sorted(SAMPLE):
            search = client.get("/api/stocks", params={"query": symbol})
            if search.status_code != 200 or not any(
                item["symbol"] == symbol for item in search.json()
            ):
                raise ValueError(f"API search failed for {symbol}")
            response = client.get(
                f"/api/stocks/{symbol}/prices", params={"range": "all"}
            )
            if response.status_code != 200:
                raise ValueError(f"API history failed for {symbol}")
            history = response.json()
            count = report["accepted_by_symbol"][symbol]
            if (
                history["mode"] != "historical_snapshot"
                or len(history["bars"]) != min(2000, count)
                or history["has_earlier"] != (count > 2000)
                or "Yahoo Finance" not in history["source"]
            ):
                raise ValueError(f"API response contract failed for {symbol}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path.home() / "Downloads/prices_clean.parquet",
    )
    parser.add_argument("--replace-existing-series", action="store_true")
    args = parser.parse_args()
    engine = None
    try:
        if not args.path.is_file():
            raise ValueError("Dataset file is missing; provide its path as an argument")
        url = local_database_url(Settings())
        access = docker_status()
        if access["status"] != "accessible":
            status = access["status"].upper()
            print(f"DOCKER_{status}: {access.get('message', 'Unavailable')}")
            print("Compare with python -m app.environment_check in your terminal.")
            return 1
        if importlib.util.find_spec("pyarrow") is None:
            print("Installing the pinned Parquet reader...", flush=True)
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(BACKEND / "requirements-import.txt"),
                ],
                check=True,
            )
        print("Validating the complete snapshot before database changes...", flush=True)
        report = scan(args.path)
        small = subset_report(report)
        print(
            f"Accepted {report['accepted']} rows; quarantined {report['quarantined']}.",
            flush=True,
        )
        print(
            "Starting the existing Compose database (preserving its volume)...",
            flush=True,
        )
        subprocess.run(
            ["docker", "compose", "up", "-d", "--wait"], cwd=ROOT, check=True
        )
        print("Applying database migrations...", flush=True)
        config = Config(str(BACKEND / "alembic.ini"))
        config.attributes["database_url"] = url
        command.upgrade(config, "head")
        engine = database_engine(url)
        print("Importing and checking AAPL/MSFT/NVDA first...", flush=True)
        import_snapshot(engine, args.path, small, SAMPLE, args.replace_existing_series)
        verify_counts(engine, small)
        verify_api(url, small)
        print("Subset passed. Importing the complete accepted snapshot...", flush=True)
        import_snapshot(
            engine,
            args.path,
            report,
            replace_existing=args.replace_existing_series,
        )
        result = verify_counts(engine, report)
        verify_api(url, report)
        command.check(config)
        output = ROOT / ".local-data"
        output.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        evidence = output / f"backend-completion-{stamp}.json"
        evidence.write_text(
            json.dumps(
                {
                    "status": "database_and_api_verified",
                    "sha256": report["sha256"],
                    **result,
                    "quarantined": report["quarantined"],
                    "verification": "Stored counts/hash and in-process HTTP checks",
                    "browser_verified": False,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"BACKEND VERIFIED: {result['symbols']} symbols, {result['rows']} rows.")
        print(f"Evidence: {evidence}")
        print("Restart the regular app.main:app API, then refresh the frontend.")
        return 0
    except SQLAlchemyError:
        print(
            "Database step failed. Run python -m app.doctor; completion is not claimed."
        )
        return 1
    except (OSError, ValueError, subprocess.CalledProcessError):
        print("Setup failed; see docs/PRICES_IMPORT.md; no completion claimed.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
