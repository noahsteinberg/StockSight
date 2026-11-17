"""Keep application tables behind FastAPI when hosted on Supabase."""

from alembic import op

revision = "0005_backend_only_access"
down_revision = "0004_app_sessions"
branch_labels = None
depends_on = None

TABLES = (
    "stocks",
    "price_series",
    "daily_bars",
    "user_identities",
    "watchlist_entries",
    "auth_sessions",
    "alembic_version",
)


def upgrade():
    if op.get_context().dialect.name != "postgresql":
        return
    for table in TABLES:
        # No Data API policies: Auth0 ownership stays enforced by FastAPI.
        # The table owner used by the backend retains its normal access.
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON TABLE public."{table}" FROM PUBLIC')
    # Local PostgreSQL need not have Supabase's browser-facing roles.
    tables = ", ".join(f'public."{table}"' for table in TABLES)
    for role in ("anon", "authenticated"):
        op.execute(
            f"""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                REVOKE ALL ON TABLE {tables} FROM {role};
            END IF;
            END; $$"""
        )


def downgrade():
    if op.get_context().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
    # Do not regrant public/browser access when rolling back a security boundary.
