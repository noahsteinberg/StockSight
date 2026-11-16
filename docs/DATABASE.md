# Phase 2 persistence foundation

This increment implements PostgreSQL storage, Alembic migrations, and an explicit idempotent import of the existing AAPL historical fixture. It does not choose a live provider or implement scheduled ingestion, accounts, indicators, or ML.

## Storage contract

- `stocks`: symbol, company name, exchange, currency.
- `price_series`: one canonical series per symbol with source URL, historical mode, adjustment convention, fixture SHA256, and import timestamp.
- `daily_bars`: composite primary key `(series_id, session_date)`, fixed-precision Numeric(18,6) OHLC, integer volume, foreign keys, and bounds/volume constraints. The primary key supports series/date queries; no redundant date index is required for this access pattern.

Daily session dates remain dates, not invented midnight UTC timestamps. The current canonical series is unadjusted USD AAPL historical data; it remains labeled historical after storage. Only one series per symbol is supported for this increment. Supporting multiple providers/adjustment policies requires an explicit canonical-series selection contract before ingestion work.

`GET /api/stocks` and `/api/stocks/{symbol}/prices` retain the Phase 1 JSON contract. Search escapes SQL wildcard characters and is capped at 50 results. Price queries select the newest bounded rows, then return them chronologically. `all` is bounded to the latest 2,000 sessions; the existing 506-row fixture fits entirely. No file import or schema creation happens during API startup.

If `STOCKSIGHT_DATABASE_URL` is set, API reads come from that database. A missing/empty URL selects the fixture adapter explicitly. Database failures return sanitized 503 responses and never switch to fixture data. `/api/health` remains a process-health check; `/api/ready` checks configured storage/schema. Readiness now checks all three market tables and usable joined history. Missing tables return SCHEMA_MISSING; empty storage returns DATA_NOT_IMPORTED. See LOCAL_START.md for recovery.

## Local setup on Windows

Requires Docker Desktop running, Node, and a Python environment installed as described in README. From the repository root:

1. Copy root `.env.example` to root `.env` and replace its local database password. This file configures Docker Compose, not FastAPI.
2. Copy `backend/.env.example` to `backend/.env`. Set `STOCKSIGHT_DATABASE_URL` to the example PostgreSQL URL with the same password. URL-encode special password characters. Both `.env` files are ignored by Git.
3. Run `docker compose up -d --wait`.
4. From backend, install `requirements-dev.txt`, run `python -m alembic upgrade head`, then `python -m app.seed`.
5. Start `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Start the frontend normally and open http://127.0.0.1:5173.

Use the virtual environment interpreter directly in PowerShell if activation is unavailable, for example `.\.venv\Scripts\python.exe -m app.seed`.

Compose binds only 127.0.0.1:5433 and uses a named volume. `docker compose stop` stops services without deleting data; `docker compose up -d --wait` starts them again. Do not use `docker compose down -v` against data you want to keep. Changing the Compose password after volume creation does not change the existing PostgreSQL role password; keep the existing configuration or deliberately migrate credentials. The developer role is a local setup role; production least-privilege provisioning remains deployment work.

## Migration and import behavior

`alembic upgrade head` is explicit. `alembic check` detects model/schema drift. New revisions can be generated with `alembic revision --autogenerate -m "..."`; review the generated migration before applying it. Downgrades remove tables and belong only in disposable tests or an approved recovery operation, not routine startup.

`python -m app.seed` atomically upserts the stock, series metadata, and all fixture bars. Running it twice preserves 506 bar keys; corrected values update existing dates. A constraint error rolls back the entire import. Import does not delete existing dates that are absent from a later fixture; future provider ingestion needs its own correction/removal policy. Import timestamp and fixture hash identify the import, not provider market freshness. Retain the fixture's source/license documentation.

## Tests and CI

The default backend suite migrates temporary SQLite files, imports twice, checks corrections and rollback, compares fixture/database API output, creates a new app/engine to test persistence, tests schema downgrade/re-upgrade, and checks safe failure. SQLite is a fast test adapter, not the target deployment database.

To also run PostgreSQL cases, create a separate disposable database named `stocksight_test` and set `STOCKSIGHT_TEST_DATABASE_URL` to its URL before `python -m pytest`. Tests refuse to reset a PostgreSQL database whose name does not end in `_test`. These tests downgrade their tables during cleanup; never point them at the normal development database.

For browser tests, set `STOCKSIGHT_E2E_DATABASE_URL` to a migrated/seeded database URL and run `npm run test:e2e` from frontend. The API test server explicitly overrides local `.env`: without that E2E variable it runs fixture mode; with it, it runs database mode. CI now provisions disposable PostgreSQL services, runs backend integration tests, migrates/seeds the browser database, and runs the same browser suite. Hosted CI is not claimed to have run locally.

## Next decisions

Parth and Vladislav should review provider access, permitted caching/redistribution, adjusted-price conventions, supported symbols, and ingestion refresh/failure semantics. Gavin and Noah jointly own keeping the browser/API contract stable. Adding more fixture rows is not equivalent to implementing provider ingestion. The milestone is persistence foundation only, not all of roadmap M2.

## Verification November 15, 2026

- Docker Desktop was started; PostgreSQL 17 ran in the project-local Compose service.
- `alembic upgrade head` succeeded against the new development database; `alembic check` reported no schema drift.
- Two seed runs each processed 506 bars; the database contained 506 unique rows.
- The PostgreSQL container was restarted and all 506 rows remained in its named volume.
- Thirteen backend tests passed across temporary SQLite and a separate disposable PostgreSQL test database, including migration cycles, contract parity, correction imports, rollback, orphan rejection, app restart persistence, and sanitized disconnected/unmigrated storage errors.
- All seven headless browser tests passed against the PostgreSQL-backed API, including actual range/normalization requests and controlled UI failure cases.
- Backend Ruff lint/format and frontend lint/build passed.
- The running local API reported `/api/ready` status ok with storage database.

Local credentials were generated in ignored root/backend `.env` files and were not committed. CI configuration was updated, but hosted CI and second-machine verification have not run. Provider selection/ingestion is still outstanding. Changes are committed locally; pushing remains deferred at the user's request.
