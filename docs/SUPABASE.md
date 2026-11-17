# Supabase setup for StockSight

Prepared November 16, 2026 for Parth's database task. This guide uses the existing
FastAPI/SQLAlchemy/Alembic architecture. Supabase hosts PostgreSQL; Auth0 continues
to authenticate users and FastAPI continues to enforce private watchlist access.
There is no Supabase browser SDK or new frontend secret.

## 1. Create the project

In the [Supabase dashboard](https://supabase.com/dashboard), choose New project
in the intended team organization, name it StockSight, and select a region near
the eventual backend. Use a Free organization for the initial classroom setup;
review any cost shown before selecting paid resources. Save the database password
privately in a password manager. Do not put credentials in chat or GitHub.

If an integration creates the project, record its actual dashboard URL and verify
that provisioning has finished. Creating a project alone does not migrate tables,
load prices, or connect the running application.

## 2. Configure server-side connections

Copy `backend/.env.example` to ignored `backend/.env`. Open the project's Connect
dialog and copy its real host, username and connection URL; do not invent the
pooler host from the region. Percent-encode reserved characters in the password.

| Use | Supabase connection | Setting |
| --- | --- | --- |
| Local development / persistent API | Direct if IPv6 works, otherwise Session pooler on 5432 | `STOCKSIGHT_DATABASE_URL` |
| Vercel serverless API | Transaction pooler on 6543 | `STOCKSIGHT_DATABASE_URL` in Vercel server secrets |
| Alembic schema changes | Direct, or Session pooler when direct IPv6 is unavailable | `STOCKSIGHT_MIGRATION_DATABASE_URL` |

Both `postgresql://` from the dashboard and explicit `postgresql+psycopg://` work.
The engine selects the installed psycopg driver, requires TLS on Supabase hosts,
and preserves stronger `verify-ca`/`verify-full` settings. For Supabase port 6543
it disables automatic prepared statements and caps the process pool at one
connection with no overflow. This limits each warm process, not all Vercel instances.
For server certificate verification configure `sslmode=verify-full` and the
dashboard-provided root certificate; `require` encrypts without verifying identity.

Alembic uses the separate migration URL when provided and otherwise uses the
normal database URL. The separate setting does not change application reads or
the importer: use the session/direct URL as `STOCKSIGHT_DATABASE_URL` when importing.
Never share or commit a real URL or use `VITE_*` for these settings.

Keep the existing Auth0 settings. Gavin must configure the eventual HTTPS app
Origin, Auth0 callback URLs, and same-origin `/api` routing when deploying.

## 3. Migrate the new database

From `backend` on macOS/Linux (Windows uses `.venv\Scripts\python.exe`):

```sh
.venv/bin/python -m app.environment_check
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
```

The expected head is `0005_backend_only_access`. Alembic owns the six application
tables plus its version table; do not create separate, incompatible stock tables
manually. API startup does not run migrations.

For a new empty project, the equivalent Alembic-generated bootstrap SQL can be
reviewed and run once in the project's SQL Editor. It includes the migration
version record, so subsequent Alembic upgrades recognize the schema. Use either
that full bootstrap or `alembic upgrade head` for initial creation; the bootstrap
is not a rerunnable script for an existing database. Later changes still belong
in Alembic migrations.

Migration 0005 enables PostgreSQL RLS and revokes table privileges from PUBLIC and
Supabase's `anon`/`authenticated` roles when present. No browser policies are
created. Use the trusted table-owning connection for this initial backend setup;
ordinary roles without ownership/BYPASSRLS cannot use these tables without a
separately designed policy. Auth0 identities are not Supabase `auth.uid()` values.
Future application tables need the same protection before exposure.

Do not downgrade a real project: earlier migrations remove data. Tests use only
separate disposable databases ending in `_test`.

## 4. Load an initial dataset deliberately

Gavin's local database and `prices_clean.parquet` do not travel with the repository.
Obtain that file through the team, outside Git, and follow [PRICES_IMPORT.md](PRICES_IMPORT.md).
Do not use `app.complete_backend` for Supabase: it intentionally only supports
the local Compose database.

For the intended team snapshot, begin with a small subset. Set the normal database
URL to the new project's session/direct connection for this import, then run:

```sh
.venv/bin/python -m app.import_prices /PRIVATE/PATH/prices_clean.parquet --symbols AAPL,MSFT,NVDA
.venv/bin/python -m app.import_prices /PRIVATE/PATH/prices_clean.parquet --symbols AAPL,MSFT,NVDA --write
.venv/bin/python -m app.doctor
```

Without `--write`, validation makes no database writes. A new empty database does
not need `--replace-existing-series`. Stop on a canonical-series conflict and
review which dataset belongs there; replacement changes the selected histories.
Check actual database/index size and plan capacity before importing all 494
symbols / roughly three million observations.

If the team snapshot is unavailable, a deliberately chosen **blank demo database**
can use `.venv/bin/python -m app.seed` for 506 historical AAPL fixture observations.
Label that dataset as historical. Do not seed over the team snapshot or blindly
run both import paths.

## 5. Verify before handing off to Gavin

`app.doctor` must report `Storage ready: database`; an empty database correctly
reports `DATA_NOT_IMPORTED`. Run the normal FastAPI app against this project and
check `/api/ready`, ticker search, price history and indicators. Restart the API
and confirm prices remain. Check actual Auth0 login/refresh/watchlist isolation on
the deployed app before claiming account acceptance. Never point reset-capable
test suites at this project.

Read-only SQL checks in the project SQL Editor:

```sql
select version_num from public.alembic_version;
select count(*) as symbols from public.stocks;
select count(*) as bars, max(session_date) as latest_session from public.daily_bars;
select pg_size_pretty(pg_database_size(current_database())) as database_size;
select tablename, rowsecurity from pg_tables
where schemaname = 'public'
  and tablename in ('stocks', 'price_series', 'daily_bars', 'user_identities',
                    'watchlist_entries', 'auth_sessions', 'alembic_version');
```

All seven listed tables should have `rowsecurity=true`. Confirm anonymous and
authenticated Data API requests cannot read or mutate these backend tables.
Using an administrative SQL Editor session alone does not prove that denial.

## References and current limits

- [Official connection modes, TLS and pooling](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Official row-level security documentation](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Yahoo Finance investigation](YAHOO_FINANCE.md)

Local verification is recorded in CURRENT_HANDOFF.md. A hosted project, imported
team data, working Vercel routing, live refresh and hosted Auth0 acceptance require
their own observed results; this setup code does not establish them.
