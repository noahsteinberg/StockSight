"""Validate a team Parquet snapshot; database writes require --write explicitly."""

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db import DailyBar, PriceSeries, StockRecord, database_engine

COLUMNS = {
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "dividends",
    "stock_splits",
    "bad_bar",
}
PRICES = ("open", "high", "low", "close")
SOURCE = "Yahoo Finance historical snapshot (team supplied)"
SOURCE_URL = "https://finance.yahoo.com/"
ADJUSTMENT = (
    "OHLC as supplied by team; adjustment convention unverified. "
    "Adjusted close and corporate actions retained separately. "
    "USD assumed from team US scope."
)


def input_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parquet_rows(path):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise ValueError("Install requirements-import.txt to read Parquet") from None
    source = pq.ParquetFile(path)
    try:
        schema = source.schema_arrow
        if set(schema.names) != COLUMNS or len(schema.names) != len(COLUMNS):
            raise ValueError("Unexpected Parquet columns; refusing to discard fields")
        if not pa.types.is_timestamp(schema.field("date").type):
            raise ValueError("date must be a timestamp column")
        if schema.field("date").type.tz is not None:
            raise ValueError(
                "Timezone-aware source needs an explicit session-date policy"
            )
        if not (
            pa.types.is_string(schema.field("ticker").type)
            or pa.types.is_large_string(schema.field("ticker").type)
        ):
            raise ValueError("ticker must be a string column")
        if not pa.types.is_boolean(schema.field("bad_bar").type):
            raise ValueError("bad_bar must be a boolean column")
        if not pa.types.is_integer(schema.field("volume").type):
            raise ValueError("volume must be an integer column")
        for name in (*PRICES, "adj_close", "dividends", "stock_splits"):
            if not pa.types.is_floating(schema.field(name).type):
                raise ValueError(f"{name} must be a floating-point column")
        for batch in source.iter_batches(batch_size=8192):
            yield from batch.to_pylist()
    finally:
        source.close()


def validated_row(row):
    symbol, stamp = row["ticker"], row["date"]
    if not isinstance(symbol, str) or not re.fullmatch(
        r"[A-Z][A-Z0-9.\^=\-]{0,15}", symbol
    ):
        raise ValueError("Invalid or unnormalized ticker; validation stopped")
    if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
        raise ValueError("Invalid trading-session timestamp; validation stopped")
    if any((stamp.hour, stamp.minute, stamp.second, stamp.microsecond)):
        raise ValueError("Non-midnight timestamp needs an explicit date policy")
    key = (symbol, stamp.date())
    reasons = []
    if row["bad_bar"] is not False:
        reasons.append("flagged_bar")
    numeric = (*PRICES, "adj_close", "volume", "dividends", "stock_splits")
    if any(row[name] is None for name in numeric):
        reasons.append("missing_value")
        return key, None, reasons
    if any(not math.isfinite(row[name]) for name in numeric):
        reasons.append("nonfinite_value")
        return key, None, reasons
    if any(row[name] <= 0 for name in (*PRICES, "adj_close")):
        reasons.append("nonpositive_price")
    if (
        row["low"] > row["high"]
        or not row["low"] <= row["open"] <= row["high"]
        or not row["low"] <= row["close"] <= row["high"]
    ):
        reasons.append("ohlc_bounds")
    if not isinstance(row["volume"], int) or not 0 <= row["volume"] <= 2**63 - 1:
        reasons.append("invalid_volume")
    if any(abs(row[name]) >= 1e12 for name in PRICES):
        reasons.append("numeric_overflow")
        return key, None, reasons
    rounded = {
        name: Decimal(str(row[name])).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_EVEN
        )
        for name in PRICES
    }
    if any(value >= Decimal("1000000000000") for value in rounded.values()):
        reasons.append("numeric_overflow")
    if (
        rounded["low"] <= 0
        or not rounded["low"] <= rounded["open"] <= rounded["high"]
        or not rounded["low"] <= rounded["close"] <= rounded["high"]
    ):
        reasons.append("rounded_bounds")
    if reasons:
        return key, None, reasons
    return (
        key,
        {
            "session_date": key[1],
            **rounded,
            "volume": row["volume"],
            "source_values": {
                name: row[name]
                for name in ("adj_close", "dividends", "stock_splits", "bad_bar")
            },
        },
        [],
    )


def scan(path, symbols=None, quarantine=None):
    fingerprint = input_hash(path)
    total = accepted = rejected = 0
    reasons = Counter()
    counts = Counter()
    first = last = previous = None
    for row in parquet_rows(path):
        key, bar, failures = validated_row(row)
        if previous is not None and key <= previous:
            raise ValueError(
                "Duplicate or out-of-order ticker/date key; validation stopped"
            )
        previous = key
        if symbols is not None and key[0] not in symbols:
            continue
        total += 1
        first = min(first, key[1]) if first else key[1]
        last = max(last, key[1]) if last else key[1]
        if bar is None:
            rejected += 1
            reasons.update(failures)
            if quarantine is not None:
                quarantine.write(
                    json.dumps(
                        {
                            "symbol": key[0],
                            "date": str(key[1]),
                            "reasons": failures,
                        }
                    )
                    + "\n"
                )
        else:
            accepted += 1
            counts[key[0]] += 1
    if not total:
        raise ValueError("No input rows matched the requested symbols")
    if input_hash(path) != fingerprint:
        raise ValueError("Input changed during validation; no import is approved")
    return {
        "sha256": fingerprint,
        "selected_rows": total,
        "accepted": accepted,
        "quarantined": rejected,
        "reason_counts": dict(sorted(reasons.items())),
        "accepted_by_symbol": dict(sorted(counts.items())),
        "first_date": str(first),
        "last_date": str(last),
        "source": SOURCE,
        "adjustment": ADJUSTMENT,
        "status": "validated_only",
    }


def write_symbol(engine, symbol, bars, fingerprint, replace_existing=False):
    """Replace one complete symbol snapshot atomically, never mix sources."""
    if not bars:
        raise ValueError(f"No accepted bars for {symbol}")
    series_id = f"team-yahoo-v1-{symbol}"
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    with engine.begin() as connection:
        old = connection.execute(
            select(PriceSeries.id).where(PriceSeries.symbol == symbol)
        ).scalar_one_or_none()
        if old and old != series_id and not replace_existing:
            raise ValueError(
                f"{symbol} has another canonical series; replacement is explicit"
            )
        stock = insert(StockRecord).values(
            symbol=symbol,
            name=symbol,
            exchange="UNKNOWN",
            currency="USD",
        )
        # Preserve known company names; use the ticker when metadata is absent.
        connection.execute(stock.on_conflict_do_nothing(index_elements=["symbol"]))
        if old:
            connection.execute(delete(DailyBar).where(DailyBar.series_id == old))
            connection.execute(delete(PriceSeries).where(PriceSeries.id == old))
        connection.execute(
            insert(PriceSeries).values(
                id=series_id,
                symbol=symbol,
                source=SOURCE,
                source_url=SOURCE_URL,
                mode="historical_snapshot",
                adjustment=ADJUSTMENT,
                fixture_sha256=fingerprint,
                imported_at=datetime.now(UTC),
            )
        )
        # Each statement has bounded parameters; the transaction covers the full symbol.
        for start in range(0, len(bars), 250):
            connection.execute(
                insert(DailyBar),
                [{"series_id": series_id, **bar} for bar in bars[start : start + 250]],
            )
    return len(bars)


def import_snapshot(engine, path, report, symbols=None, replace_existing=False):
    if input_hash(path) != report["sha256"]:
        raise ValueError("Input does not match the validated hash")
    allowed = set(report["accepted_by_symbol"])
    with engine.connect() as connection:
        conflicts = connection.execute(select(PriceSeries.symbol, PriceSeries.id)).all()
    if not replace_existing:
        for symbol, series_id in conflicts:
            if symbol in allowed and series_id != f"team-yahoo-v1-{symbol}":
                raise ValueError(
                    f"{symbol} canonical-series conflict; nothing was imported"
                )
    # Validate before writing. Each complete symbol is one transaction.
    current, bars = None, []
    completed = {}
    for row in parquet_rows(path):
        symbol = row["ticker"]
        if symbols is not None and symbol not in symbols:
            continue
        if current is not None and symbol != current:
            if bars:
                completed[current] = write_symbol(
                    engine,
                    current,
                    bars,
                    report["sha256"],
                    replace_existing,
                )
                print(
                    f"Imported {current}: {completed[current]} rows",
                    file=sys.stderr,
                    flush=True,
                )
            bars = []
        current = symbol
        _, bar, _ = validated_row(row)
        if bar is not None:
            bars.append(bar)
    if current is not None and bars:
        completed[current] = write_symbol(
            engine,
            current,
            bars,
            report["sha256"],
            replace_existing,
        )
        print(
            f"Imported {current}: {completed[current]} rows",
            file=sys.stderr,
            flush=True,
        )
    if (
        input_hash(path) != report["sha256"]
        or completed != report["accepted_by_symbol"]
    ):
        raise ValueError(
            "Import did not complete consistently; rerun the unchanged snapshot"
        )
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--symbols", help="Comma-separated subset; default all file symbols"
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--quarantine", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--replace-existing-series", action="store_true")
    args = parser.parse_args()
    symbols = (
        {part.strip().upper() for part in args.symbols.split(",")}
        if args.symbols
        else None
    )
    engine = None
    try:
        # Never let a report path overwrite the input or the other output.
        outputs = [p.resolve() for p in (args.report, args.quarantine) if p is not None]
        if args.path.resolve() in outputs or len(outputs) != len(set(outputs)):
            raise ValueError("Input/report/quarantine paths must be distinct")
        if any(p.exists() for p in outputs):
            raise ValueError(
                "Report/quarantine output already exists; choose new paths"
            )
        if args.quarantine:
            with args.quarantine.open("x", encoding="utf-8") as quarantine:
                report = scan(args.path, symbols, quarantine)
        else:
            report = scan(args.path, symbols)
        if args.write:
            settings = Settings()
            if settings.database_url is None:
                raise ValueError("Set STOCKSIGHT_DATABASE_URL before explicit import")
            engine = database_engine(settings.database_url.get_secret_value())
            import_snapshot(
                engine, args.path, report, symbols, args.replace_existing_series
            )
            report["status"] = "imported"
        if args.report:
            with args.report.open("x", encoding="utf-8") as target:
                json.dump(report, target, indent=2)
        print(json.dumps(report, indent=2))
    except SQLAlchemyError:
        raise SystemExit(
            "Import failed; check migrations/storage. No global completion claimed."
        ) from None
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
