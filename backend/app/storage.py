"""Read-only storage diagnostics. Never expose driver errors or connection URLs."""

from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db import (
    AuthSession,
    DailyBar,
    MarketBarChange,
    MarketRefreshRun,
    PriceSeries,
    StockRecord,
    UserIdentity,
    WatchlistEntry,
)

MODELS = (
    StockRecord,
    PriceSeries,
    DailyBar,
    UserIdentity,
    WatchlistEntry,
    AuthSession,
    MarketRefreshRun,
    MarketBarChange,
)


def storage_problem(engine: Engine | None) -> dict[str, str] | None:
    if engine is None:
        return None
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            if any(not inspector.has_table(model.__tablename__) for model in MODELS):
                return {
                    "code": "SCHEMA_MISSING",
                    "message": "Database tables are missing. Run alembic upgrade head.",
                }
            # Query all mapped columns, not just one table, to detect schema drift.
            for model in MODELS:
                connection.execute(select(model).limit(1))
            available = connection.execute(
                select(DailyBar.session_date)
                .join(PriceSeries, DailyBar.series_id == PriceSeries.id)
                .join(StockRecord, PriceSeries.symbol == StockRecord.symbol)
                .limit(1)
            ).first()
            if available is None:
                return {
                    "code": "DATA_NOT_IMPORTED",
                    "message": "No stored prices. Run the explicit fixture importer.",
                }
    except SQLAlchemyError as error:
        state = getattr(getattr(error, "orig", None), "sqlstate", None)
        if state in {"28P01", "28000"}:
            return {
                "code": "DATABASE_AUTH_FAILED",
                "message": "Database login failed. Check local credentials.",
            }
        if state == "3D000":
            return {
                "code": "DATABASE_MISSING",
                "message": "The configured database does not exist.",
            }
        return {
            "code": "STORAGE_UNAVAILABLE",
            "message": "Cannot read price storage. Check PostgreSQL and migrations.",
        }
    return None
