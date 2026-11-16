"""Persist external identities and private watchlists without changing market data."""

import sqlalchemy as sa
from alembic import op

revision = "0003_accounts_watchlists"
down_revision = "0002_source_values"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_identities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_identity"),
    )
    op.create_table(
        "watchlist_entries",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_identities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "symbol", sa.String(16), sa.ForeignKey("stocks.symbol"), primary_key=True
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("watchlist_entries")
    op.drop_table("user_identities")
