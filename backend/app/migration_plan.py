"""Read-only hosted-import inventory and preview. This command never imports data."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db import DailyBar, PriceSeries, StockRecord, database_engine
from app.import_prices import parquet_rows, retained_counts, scan, validated_row

TEAM_SHA256 = "ee0b2ed66c8abb87e0cf36798a32258bc902c0e1687ddee2a485c80b44216e89"
PILOT = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"}


def inventory(engine):
    """Inspect only market tables; PostgreSQL enforces a read-only transaction."""
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = connection.execute(
            select(
                PriceSeries.symbol,
                PriceSeries.id,
                PriceSeries.fixture_sha256,
                func.count(DailyBar.session_date),
                func.min(DailyBar.session_date),
                func.max(DailyBar.session_date),
            )
            .outerjoin(DailyBar, DailyBar.series_id == PriceSeries.id)
            .group_by(PriceSeries.symbol, PriceSeries.id, PriceSeries.fixture_sha256)
            .order_by(PriceSeries.symbol)
        ).all()
        result = {
            "symbols": connection.scalar(select(func.count()).select_from(StockRecord)),
            "bars": connection.scalar(select(func.count()).select_from(DailyBar)),
            "series": {
                row[0]: {
                    "id": row[1],
                    "sha256": row[2],
                    "bars": row[3],
                    "first_date": str(row[4]) if row[4] else None,
                    "last_date": str(row[5]) if row[5] else None,
                }
                for row in rows
            },
            "database_bytes": None,
        }
        if engine.dialect.name == "postgresql":
            result["database_bytes"] = connection.scalar(
                text("SELECT pg_database_size(current_database())")
            )
            result["migration"] = connection.scalar(
                text("SELECT version_num FROM public.alembic_version")
            )
        return result


def preview(
    path, symbols, target=None, *, expected_sha256=TEAM_SHA256, max_bars_per_symbol=None
):
    if not symbols:
        raise ValueError("Choose an explicit symbol subset")
    source = scan(path, symbols)
    incoming = retained_counts(source, max_bars_per_symbol)
    found = set(source["accepted_by_symbol"])
    blockers = []
    if source["sha256"] != expected_sha256:
        blockers.append(
            "Source hash differs from the expected snapshot; review provenance"
        )
    missing = sorted(symbols - found)
    if missing:
        blockers.append("No accepted history for: " + ", ".join(missing))
    existing = target["series"] if target else {}
    actions = []
    for symbol, count in incoming.items():
        old = existing.get(symbol)
        actions.append(
            {
                "symbol": symbol,
                "incoming_bars": count,
                "existing_bars": old["bars"] if old else 0,
                "action": (
                    "uninspected_target"
                    if target is None
                    else "create"
                    if old is None
                    else "replace_canonical_series"
                    if old["id"] != f"team-yahoo-v1-{symbol}"
                    else "replace_complete_snapshot"
                ),
            }
        )
    # Sample row payloads, not the Parquet file size: PostgreSQL has row/index overhead.
    samples = []
    for row in parquet_rows(path):
        if row["ticker"] not in symbols:
            continue
        _, bar, _ = validated_row(row)
        if bar is not None:
            samples.append(len(json.dumps(bar, default=str).encode()))
        if len(samples) == 1000:
            break
    estimate = int(sum(incoming.values()) * (max(samples, default=0) + 256) * 1.25)
    new_symbols = [a["symbol"] for a in actions if a["action"] == "create"]
    replacements = [a["symbol"] for a in actions if a["action"] != "create"]
    commands = []
    if target and not blockers:
        for selected, replace in ((new_symbols, False), (replacements, True)):
            if selected:
                command = [
                    "python",
                    "-m",
                    "app.import_prices",
                    str(path.resolve()),
                    "--symbols",
                    ",".join(selected),
                    "--write",
                ]
                if replace:
                    command.append("--replace-existing-series")
                if max_bars_per_symbol is not None:
                    command.extend(["--max-bars-per-symbol", str(max_bars_per_symbol)])
                commands.append(command)
    return {
        "status": "preview_only_no_database_writes",
        "source": source,
        "target": target,
        "actions": actions,
        "planned_import": {
            "bars": sum(incoming.values()),
            "max_bars_per_symbol": max_bars_per_symbol,
        },
        "blockers": blockers,
        "capacity": {
            "sampled_rows": len(samples),
            "conservative_additional_bytes": estimate,
            "note": (
                "Planning estimate from sampled payloads plus row/index allowance. "
                "Not a quota guarantee. Measure a small pilot, leave headroom, and "
                "check the actual plan before importing the full universe."
            ),
        },
        "separate_explicit_import_commands": commands,
        "note": (
            "New tickers and replacements are separate steps. Review/back up existing "
            "histories before replacing. Recheck file hash and capacity immediately "
            "before an import. The importer replaces whole symbol histories; never "
            "pass a short refresh window as a complete snapshot."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?")
    parser.add_argument("--symbols", default=",".join(sorted(PILOT)))
    parser.add_argument("--inspect-target", action="store_true")
    parser.add_argument("--expected-sha256", default=TEAM_SHA256)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--max-bars-per-symbol", type=int)
    args = parser.parse_args()
    engine = None
    try:
        if not args.path and not args.inspect_target:
            raise ValueError("Supply a Parquet path or --inspect-target")
        if args.report and (
            args.report.exists()
            or (args.path and args.report.resolve() == args.path.resolve())
        ):
            raise ValueError("Report must be a new file distinct from the source")
        target = None
        if args.inspect_target:
            settings = Settings()
            if settings.database_url is None:
                raise ValueError("Configure the private STOCKSIGHT_DATABASE_URL first")
            engine = database_engine(settings.database_url.get_secret_value())
            target = inventory(engine)
        result = (
            preview(
                args.path,
                {s.strip().upper() for s in args.symbols.split(",") if s.strip()},
                target,
                expected_sha256=args.expected_sha256,
                max_bars_per_symbol=args.max_bars_per_symbol,
            )
            if args.path
            else {"status": "inventory_only_no_database_writes", "target": target}
        )
        if args.report:
            with args.report.open("x", encoding="utf-8") as output:
                json.dump(result, output, indent=2)
        print(json.dumps(result, indent=2))
    except ValidationError:
        raise SystemExit("Invalid private configuration; check backend/.env") from None
    except SQLAlchemyError:
        raise SystemExit(
            "Cannot inspect storage. Check the private connection/schema."
        ) from None
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
