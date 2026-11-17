# Database implementation and operations

Current continuation context: [CURRENT_HANDOFF.md](CURRENT_HANDOFF.md).
PostgreSQL/SQLAlchemy/Alembic persistence, snapshot ingestion, private watchlists
and app sessions are implemented. Live provider refresh and ML are not.

For Supabase hosting, follow [SUPABASE.md](SUPABASE.md). Migration head is now
`0005_backend_only_access`: PostgreSQL RLS and browser-role privilege revocation
keep the existing Auth0/FastAPI ownership boundary intact. This migration does
not replace market data. The previous 0004 head below describes the prior phase.

## Schema and migrations

| Table | Contract |
| --- | --- |
| `stocks` | Symbol key, display name, exchange and currency |
| `price_series` | One canonical series per symbol, source, adjustment label, mode, source hash and import time |
| `daily_bars` | `(series_id, session_date)` key, Numeric(18,6) OHLC, integer volume, OHLC/volume constraints and nullable source_values JSON |
| `user_identities` | Local UUID mapped uniquely to verified Auth0 issuer/subject; no passwords/profile copy |
| `watchlist_entries` | Owner/symbol key, added_at; private, bounded to 100 per owner |
| `auth_sessions` | Hashed opaque session identifier, owner, audience, CSRF state and absolute expiry; no raw Auth0 tokens |

Migrations: `0001` market foundation, `0002` source values, `0003` accounts and
watchlists, `0004_app_sessions` app sessions. Use a checkout containing the current
head with a database already upgraded to it. Alembic owns all schema changes;
normal API startup never creates tables, seeds or imports. Review new migrations
before applying. Downgrades remove data and belong only in disposable tests or
an explicitly authorized recovery operation.

## Existing imported development database

Gavin's local snapshot contains 2,947,701 bars in 494 canonical series. It was
verified after a container restart; later account/session migrations preserved
market counts and hashes. The latest indicator HTTP check preserved market and
watchlist counts. These are dated local findings, not a guarantee of another
checkout's database. See DATASET_HANDOFF.md and INDICATORS.md for evidence.

**Do not run `app.seed` over the snapshot, delete Docker volumes, or reimport as
routine troubleshooting.** The Plotly seed conflicts with the imported canonical
AAPL series. An existing database normally needs only Docker startup, reviewed
migration and readiness checks. Import replacement requires the explicit policy
in [PRICES_IMPORT.md](PRICES_IMPORT.md).

## Local setup

Use [LOCAL_START.md](LOCAL_START.md) for executable commands. Before Docker,
server startup or live tests, run the venv environment check from backend.
A denial is an execution-access problem; do not change credentials or import data
to fix it. Use the supported approval path if available.

For a new setup, copy root `.env.example` to root `.env` for Compose and
`backend/.env.example` to `backend/.env` for FastAPI; set matching local credentials
without committing them. URL-encode password characters in database URLs.
Compose binds PostgreSQL to `127.0.0.1:5433` and retains a named volume. Changing
a Compose password does not change a role in an existing volume.

Run `alembic upgrade head` explicitly, then choose one initial dataset on a blank
database: the small Plotly fixture via `app.seed`, or the separately supplied
Parquet snapshot via the documented importer. Do not run both blindly. No source
Parquet or local database volume travels with Git. Explicit fixture API mode via
`app.demo:create_demo_app --factory` needs no database and ignores saved DB config.

## Read contract and readiness

Missing/empty STOCKSIGHT_DATABASE_URL explicitly selects fixture mode; a nonempty
URL selects database mode and errors never fall back. Search escapes wildcard
characters and caps results at 50. Price display reads newest bounded rows then
returns chronological bars; `all` is Max 2,000 sessions. Indicators use their own
fixed 10,000-session calculation window before trimming; see INDICATORS.md.
Daily dates remain dates, not invented UTC instants. Imported adjustment semantics
are unverified; do not label the team snapshot unadjusted merely because the
Plotly fixture is unadjusted.

`/api/health` proves liveness only. `/api/ready` validates all mapped market and
account/session schema plus usable joined history; it does not require any user
or saved stocks. `app.doctor` gives safe local diagnostic codes without modifying
schema or printing credentials. No readiness response certifies provider freshness
or ML suitability.

## Isolated tests and CI

The default suite uses disposable SQLite adapters. To include PostgreSQL, create
a separate database ending in `_test` and set STOCKSIGHT_TEST_DATABASE_URL;
fixtures migrate and downgrade their tables. Never use the normal development URL.
Use a unique backend/.pytest_cache basetemp. Commands and distinct chart/account
browser database variables are in CURRENT_HANDOFF.md. Chart PostgreSQL tests need
an explicitly migrated/fixture-seeded disposable DB; account tests reset their own
disposable schema. CI defines PostgreSQL-backed backend and browser jobs, including
fixture setup. Hosted success still requires an actual run on the published head.
