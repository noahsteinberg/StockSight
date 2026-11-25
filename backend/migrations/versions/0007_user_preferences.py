"""Store optional, owner-keyed research preferences (issue #19 phase 4).

Additive: one new backend-only table; no existing table or row changes.
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_user_preferences"
down_revision = "0006_market_refresh"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_preferences",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_identities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=True),
        sa.Column("horizon", sa.String(16), nullable=True),
        sa.Column("default_range", sa.String(8), nullable=True),
        sa.Column("sectors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    if op.get_context().dialect.name == "postgresql":
        # Same boundary as every other table: only FastAPI's owner role reads it.
        op.execute("ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON TABLE public.user_preferences FROM PUBLIC")
        for role in ("anon", "authenticated"):
            op.execute(f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                REVOKE ALL ON TABLE public.user_preferences FROM {role};
            END IF; END; $$""")


def downgrade():
    op.drop_table("user_preferences")
