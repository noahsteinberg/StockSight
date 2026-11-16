"""Preserve source adjusted close and corporate actions alongside chart bars."""

import sqlalchemy as sa
from alembic import op

revision = "0002_source_values"
down_revision = "0001_market_data"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("daily_bars", sa.Column("source_values", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("daily_bars", "source_values")
