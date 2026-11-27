"""Persistence models and engine construction; schema changes belong in Alembic."""

from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def series_revision(series):
    stamp = series.updated_at or series.imported_at
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return sha256(
        f"{series.id}:{series.fixture_sha256}:{stamp.isoformat()}".encode()
    ).hexdigest()


class StockRecord(Base):
    __tablename__ = "stocks"
    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    exchange: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))


class PriceSeries(Base):
    __tablename__ = "price_series"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), unique=True)
    source: Mapped[str] = mapped_column(String(160))
    source_url: Mapped[str] = mapped_column(String(500))
    mode: Mapped[str] = mapped_column(String(40))
    adjustment: Mapped[str] = mapped_column(String(200))
    fixture_sha256: Mapped[str] = mapped_column(String(64))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketRefreshRun(Base):
    __tablename__ = "market_refresh_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("price_series.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    applied_revision: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON)


class MarketBarChange(Base):
    __tablename__ = "market_bar_changes"
    run_id: Mapped[str] = mapped_column(
        ForeignKey("market_refresh_runs.id"), primary_key=True
    )
    session_date: Mapped[date] = mapped_column(primary_key=True)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)


class DailyBar(Base):
    __tablename__ = "daily_bars"
    __table_args__ = (
        CheckConstraint("low > 0 AND high >= low", name="ck_bar_bounds"),
        CheckConstraint("open >= low AND open <= high", name="ck_bar_open"),
        CheckConstraint("close >= low AND close <= high", name="ck_bar_close"),
        CheckConstraint("volume >= 0", name="ck_bar_volume"),
    )
    series_id: Mapped[str] = mapped_column(
        ForeignKey("price_series.id"), primary_key=True
    )
    session_date: Mapped[date] = mapped_column(primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    volume: Mapped[int] = mapped_column(BigInteger)
    source_values: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class UserIdentity(Base):
    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WatchlistEntry(Base):
    __tablename__ = "watchlist_entries"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_identities.id", ondelete="CASCADE"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserPreference(Base):
    """Optional research interests; never income, holdings or identity data."""

    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_identities.id", ondelete="CASCADE"), primary_key=True
    )
    schema_version: Mapped[int]
    purpose: Mapped[str | None] = mapped_column(String(16))
    horizon: Mapped[str | None] = mapped_column(String(16))
    default_range: Mapped[str | None] = mapped_column(String(8))
    sectors: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_identities.id", ondelete="CASCADE"), index=True
    )
    csrf_token: Mapped[str] = mapped_column(String(64))
    audience: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def database_engine(url: str) -> Engine:
    parsed = make_url(url)
    options = {}
    if parsed.drivername in {"postgres", "postgresql", "postgresql+psycopg"}:
        # Supabase's Connect dialog supplies a driver-neutral PostgreSQL URL.
        parsed = parsed.set(drivername="postgresql+psycopg")
        options["connect_args"] = {"connect_timeout": 3}
        host = (parsed.host or "").lower()
        if host.endswith((".supabase.co", ".pooler.supabase.com")):
            secure_modes = {"require", "verify-ca", "verify-full"}
            if parsed.query.get("sslmode") not in secure_modes:
                parsed = parsed.update_query_dict({"sslmode": "require"})
            if parsed.port == 6543:
                # Supavisor transaction mode cannot retain prepared statements.
                options["connect_args"]["prepare_threshold"] = None
                options.update(pool_size=1, max_overflow=0)
    engine = create_engine(parsed, pool_pre_ping=True, hide_parameters=True, **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine
