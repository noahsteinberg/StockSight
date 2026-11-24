"""Track incremental market refreshes without changing existing histories."""

import sqlalchemy as sa
from alembic import op

revision = "0006_market_refresh"
down_revision = "0005_backend_only_access"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "price_series",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "market_refresh_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "series_id", sa.String(80), sa.ForeignKey("price_series.id"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("applied_revision", sa.String(64), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_market_refresh_runs_series_id", "market_refresh_runs", ["series_id"]
    )
    op.create_table(
        "market_bar_changes",
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("market_refresh_runs.id"),
            primary_key=True,
        ),
        sa.Column("session_date", sa.Date(), primary_key=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
    )
    if op.get_context().dialect.name == "postgresql":
        for table in ("market_refresh_runs", "market_bar_changes"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC")
            for role in ("anon", "authenticated"):
                op.execute(f"""DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                    REVOKE ALL ON TABLE public.{table} FROM {role};
                END IF; END; $$""")


def downgrade():
    op.drop_table("market_bar_changes")
    op.drop_index("ix_market_refresh_runs_series_id", table_name="market_refresh_runs")
    op.drop_table("market_refresh_runs")
    op.drop_column("price_series", "updated_at")
