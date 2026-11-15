"""Explicit atomic import of the bundled historical dataset. Never run on startup."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.db import DailyBar, PriceSeries, StockRecord, database_engine
from app.market import ADJUSTMENT, FIXTURE_PATH, SOURCE, SOURCE_URL, load_bars

SERIES_ID = "plotly-aapl-unadjusted-v1"


def seed_fixture(engine: Engine) -> int:
    bars = load_bars()
    if not bars or len({bar.date for bar in bars}) != len(bars):
        raise ValueError("Fixture must contain unique session dates")
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    with engine.begin() as connection:
        stock = insert(StockRecord).values(
            symbol="AAPL", name="Apple Inc.", exchange="NASDAQ", currency="USD"
        )
        connection.execute(
            stock.on_conflict_do_update(
                index_elements=["symbol"], set_={"name": stock.excluded.name}
            )
        )
        series = insert(PriceSeries).values(
            id=SERIES_ID,
            symbol="AAPL",
            source=SOURCE,
            source_url=SOURCE_URL,
            mode="historical_fixture",
            adjustment=ADJUSTMENT,
            fixture_sha256=hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
            imported_at=datetime.now(UTC),
        )
        connection.execute(
            series.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    key: getattr(series.excluded, key)
                    for key in (
                        "source",
                        "source_url",
                        "mode",
                        "adjustment",
                        "fixture_sha256",
                        "imported_at",
                    )
                },
            )
        )
        rows = [
            dict(
                series_id=SERIES_ID,
                session_date=bar.date,
                open=Decimal(str(bar.open)),
                high=Decimal(str(bar.high)),
                low=Decimal(str(bar.low)),
                close=Decimal(str(bar.close)),
                volume=bar.volume,
            )
            for bar in bars
        ]
        statement = insert(DailyBar).values(rows)
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=["series_id", "session_date"],
                set_={
                    key: getattr(statement.excluded, key)
                    for key in ("open", "high", "low", "close", "volume")
                },
            )
        )
    return len(bars)


def main() -> None:
    settings = Settings()
    if settings.database_url is None:
        raise SystemExit("Set STOCKSIGHT_DATABASE_URL before importing")
    engine = database_engine(settings.database_url.get_secret_value())
    try:
        count = seed_fixture(engine)
        print(f"Imported {count} historical AAPL bars (existing dates updated)")
    except SQLAlchemyError:
        raise SystemExit(
            "Import failed; check database availability and migrations"
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
