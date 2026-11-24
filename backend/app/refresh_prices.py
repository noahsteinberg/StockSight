"""Preview-first market refresh. Production writes are explicitly opt-in."""

import argparse
import concurrent.futures
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from app.config import Settings
from app.db import PriceSeries, database_engine
from app.market_refresh import (
    apply_refresh,
    plan_refresh,
    read_snapshot,
    record_failure,
    restore_refresh,
)
from app.yahoo_provider import completed_sessions, exchange_today, fetch_yahoo


def run_symbol(engine, symbol, write=False, *, fetch=fetch_yahoo, now=None):
    started = time.perf_counter()
    snapshot = read_snapshot(engine, symbol)
    now = now or datetime.now(UTC)
    start = sorted(snapshot.bars)[-20:][0]
    end = exchange_today(now)
    if end < max(snapshot.bars):
        raise ValueError("Stored history is ahead of requested refresh time")
    completed = completed_sessions(start, end, now)
    try:
        download = fetch(symbol, start, end)
    except ValueError as exc:
        if not write:
            raise
        run_id = record_failure(engine, snapshot, type(exc).__name__, start, end)
        return {
            "symbol": symbol,
            "status": "error",
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "seconds": round(time.perf_counter() - started, 3),
        }
    plan = plan_refresh(snapshot, download, start, end, completed)
    result = (
        apply_refresh(engine, plan) if write and not plan.blockers else plan.report()
    )
    if write and plan.blockers:
        result["run_id"] = record_failure(
            engine, snapshot, "CompatibilityBlocked", start, end, details=result
        )
    result["status"] = result.get(
        "status",
        "blocked" if plan.blockers else "partial" if plan.missing else "preview",
    )
    result["seconds"] = round(time.perf_counter() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selected = parser.add_mutually_exclusive_group(required=True)
    selected.add_argument("--symbols", help="Comma-separated existing symbols")
    selected.add_argument("--all-supported", action="store_true")
    selected.add_argument(
        "--restore-run", help="Restore a refresh only if its revision is still current"
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Explicitly allow writes to configured database",
    )
    parser.add_argument(
        "--report", type=Path, help="New local JSON report path; never overwritten"
    )
    args = parser.parse_args()
    engine = None
    try:
        if args.report and args.report.exists():
            raise ValueError("Report must be a new file")
        if args.report and not args.report.parent.is_dir():
            raise ValueError("Create the report directory before running the refresh")
        if args.restore_run and not args.write:
            raise ValueError("Restoration requires --write")
        settings = Settings()
        if settings.database_url is None:
            raise ValueError(
                "Configure the private database URL; fixture mode cannot refresh"
            )
        engine = database_engine(settings.database_url.get_secret_value())
        if args.restore_run:
            output = restore_refresh(engine, args.restore_run)
            failed = False
        else:
            if args.all_supported:
                with engine.connect() as connection:
                    symbols = list(
                        connection.scalars(
                            select(PriceSeries.symbol)
                            .where(PriceSeries.mode != "historical_fixture")
                            .order_by(PriceSeries.symbol)
                        )
                    )
            else:
                symbols = sorted(
                    set(part.strip().upper() for part in args.symbols.split(","))
                )
            if not symbols or any(
                not re.fullmatch(r"[A-Z][A-Z0-9.^=\-]{0,15}", s) for s in symbols
            ):
                raise ValueError("Supply valid explicit symbols")

            def work(symbol):
                try:
                    return run_symbol(engine, symbol, args.write)
                except (ValueError, SQLAlchemyError) as exc:
                    # Never echo connection URLs, SQL parameters, or provider bodies.
                    return {
                        "symbol": symbol,
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "message": str(exc)
                        if isinstance(exc, ValueError)
                        else "Database operation failed; check private configuration",
                    }

            # The transaction-pooler engine deliberately allows one connection
            # for web requests. Avoid starving CLI workers on that shared pool.
            worker_count = (
                min(3, engine.pool.size()) if isinstance(engine.pool, QueuePool) else 3
            )
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=worker_count
            ) as workers:
                results = list(workers.map(work, symbols))
            failed = any(
                item["status"] in ("blocked", "partial", "error") for item in results
            )
            output = {
                "write_enabled": args.write,
                "results": results,
                "status": "attention_required" if failed else "complete",
            }
        encoded = json.dumps(output, indent=2, default=str)
        # Always preserve run IDs/results in stdout even if the local report
        # destination becomes unavailable after an explicit write.
        print(encoded)
        if args.report:
            try:
                with args.report.open("x", encoding="utf-8") as target:
                    target.write(encoded + "\n")
            except OSError:
                raise SystemExit(
                    "Local report could not be saved; results are in stdout"
                ) from None
        if failed:
            raise SystemExit(1)
    except (ValidationError, SQLAlchemyError):
        raise SystemExit(
            "Refresh unavailable; check private configuration and migration head"
        ) from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
