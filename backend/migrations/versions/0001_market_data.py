"""Create stocks, canonical daily series, and daily price bars."""

import sqlalchemy as sa
from alembic import op

revision = "0001_market_data"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stocks",
        sa.Column("symbol", sa.String(16), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("exchange", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
    )
    op.create_table(
        "price_series",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column(
            "symbol",
            sa.String(16),
            sa.ForeignKey("stocks.symbol"),
            nullable=False,
            unique=True,
        ),
        sa.Column("source", sa.String(160), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("adjustment", sa.String(200), nullable=False),
        sa.Column("fixture_sha256", sa.String(64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "daily_bars",
        sa.Column(
            "series_id",
            sa.String(80),
            sa.ForeignKey("price_series.id"),
            primary_key=True,
        ),
        sa.Column("session_date", sa.Date(), primary_key=True),
        *[
            sa.Column(field, sa.Numeric(18, 6), nullable=False)
            for field in ("open", "high", "low", "close")
        ],
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("low > 0 AND high >= low", name="ck_bar_bounds"),
        sa.CheckConstraint("open >= low AND open <= high", name="ck_bar_open"),
        sa.CheckConstraint("close >= low AND close <= high", name="ck_bar_close"),
        sa.CheckConstraint("volume >= 0", name="ck_bar_volume"),
    )


def downgrade():
    op.drop_table("daily_bars")
    op.drop_table("price_series")
    op.drop_table("stocks")
