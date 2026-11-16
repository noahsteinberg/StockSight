# StockSight — continuation handoff for Gavin and the next agent

Updated November 16, 2026. Start with the root [AGENTS.md](../AGENTS.md).
This is the current implementation summary; dated review reports preserve past
findings and are not current startup instructions.

## Checkout and delivery state

Gavin's implementation checkout is on `feature/auth0-watchlists`, following
`6e1c7e1` (indicator backend and prior handoff). The frontend redesign and
SMA20/RSI14 UI are delivered in the local commit containing this update. Check
`git status --short`, `git branch --show-current` and `git log -3 --oneline` in
the actual checkout. They have not been pushed or merged by this task.
Gavin requests a local commit for every completed change going forward; run the
appropriate checks and commit at each task boundary. Keep phases separate.
The next conversation should resume in this same worktree when available:
`C:/Users/gavin/.codex/worktrees/backend-adversarial-review/stocksight`.
The older `feature/frontend-redesign` review snapshot is not the complete current
foundation. Before continuing in another checkout, transfer the actual changes through
the team's normal commit/branch/review workflow; do not assume pulling main
includes them. No push, merge or hosted CI success is claimed here.

Ignored files do not travel with Git: environment settings, source Parquet,
PostgreSQL volume, installed dependencies and local evidence. Never copy account
sessions or credentials into a handoff. A fresh checkout can use explicit fixture
mode immediately after installing dependencies; database/auth verification needs
the configuration described below.

## What works and what remains

| Area | Current implementation | Remaining boundary |
| --- | --- | --- |
| Search and charts | UConn-inspired responsive research workspace; React → FastAPI → PostgreSQL history, SVG chart, ranges, inspection, table and feedback | Metadata enrichment |
| Data | Repeatable validated Parquet importer; 494 canonical series and 2,947,701 bars on Gavin's local database | Reproducible provider download, rights/adjustment/calendar review and incremental refresh |
| Accounts | Auth0 signup/login/logout; username with optional recovery email; HttpOnly server sessions restore on refresh | Production reset/account-disable revocation policy and complete password-reset acceptance |
| Watchlists | Private persistence, save/remove/open, capacity 100, account isolation; desktop sidebar/mobile stack and selected-stock state | Later product refinements |
| Indicators | SMA20 overlay and RSI14 panel/toggles; independent retries, snapshot alignment, null handling and date inspection | Future indicators only if separately scoped |
| ML / forecasts | Documentation and proposed target only | Features, chronological evaluation, trusted artifact, inference, persisted forecasts/outcomes and evaluation UI |
| Delivery | Local checks; CI definitions include disposable PostgreSQL and browser tests | Hosted CI on published head, second-machine setup and deployment/demo acceptance |

**Phase boundary:** Gavin subsequently authorized a UConn-inspired frontend
redesign and existing indicator integration. That phase is implemented and locally
verified; see [FRONTEND_REDESIGN.md](FRONTEND_REDESIGN.md) for research, changes,
evidence and limitations. ML remains for Vlad per Gavin's current direction.
No ML/provider refresh work was bundled. The complete MVP is not finished.

## Local setup

Use Node 24 LTS (see package.json engines), Python 3.12+ (CI uses 3.13), npm and
Git; Docker Desktop is needed only for local PostgreSQL. Install from committed
pins/lockfile, using `npm ci` and `backend/requirements-dev.txt`.
Follow [LOCAL_START.md](LOCAL_START.md) for executable startup commands.

Before Docker, server startup or live tests, run from `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.environment_check --require-docker
```

For fixture-only work, omit `--require-docker`. An access denial is different
from a stopped service. Gavin's ordinary sandbox was denied; the supported
approved execution path succeeded. This is machine/session-specific evidence,
not a promise about the next runner. See [ENVIRONMENT_ACCESS.md](ENVIRONMENT_ACCESS.md).

| Configuration file | Purpose |
| --- | --- |
| Root `.env` | Local Compose PostgreSQL credentials; copy root `.env.example` for a new setup |
| `backend/.env` | `STOCKSIGHT_DATABASE_URL`, Auth0 domain/audience, exact app Origin, absolute session lifetime |
| `frontend/.env.local` | Public `VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE` |

Use the examples for a new machine; obtain any shared tenant settings through
the team. No SPA client secret is needed. Match the backend audience/domain to
the frontend. Register the exact `http://127.0.0.1:5173` callback/logout/web origin
in Auth0 and keep `STOCKSIGHT_APP_ORIGIN` identical. Restart Vite after env changes.
The SPA requires User-Delegated Access to the custom API. Preserve the existing
database connection and user IDs; do not recreate accounts to change identifiers.
See [AUTH0_WATCHLIST_HANDOFF.md](AUTH0_WATCHLIST_HANDOFF.md) for setup and
[SESSION_HANDOFF.md](SESSION_HANDOFF.md) for the authoritative session contract.

Normal ports: frontend 5173, API 8000, local Compose PostgreSQL 5433. API `/` can
return 404; `/api/health` checks liveness, `/api/ready` checks configured storage.
Never infer reachability from a ready log. Production must proxy `/api` to the API;
Vite's development proxy is not a production routing solution.

The database must migrate through `0004_app_sessions`. API startup does not
migrate, seed or import. An already imported database needs migration/readiness
checks, not another import. `app.seed` is only for a deliberately chosen blank
fixture/test database; it conflicts with the imported AAPL canonical series.
Do not drop volumes or downgrade the development database. New machines need
their own explicit initial dataset choice; see [DATABASE.md](DATABASE.md).

## Contracts and source map

| Contract / responsibility | Files to inspect |
| --- | --- |
| HTTP schema, bounded history, search/errors | `docs/API.md`, `backend/app/api/stocks.py`, `market.py`, `repository.py` |
| SMA20/RSI14, calculation cap, warm-up, reproducibility | `docs/INDICATORS.md`, `backend/app/indicators.py`, `backend/tests/test_indicators.py` |
| Auth0 JWT validation and verified owner | `backend/app/auth.py`, `api/accounts.py` |
| Cookie restoration, CSRF, expiry, revocation | `backend/app/sessions.py`, `api/sessions.py`, `frontend/src/AuthProvider.jsx` |
| Private client requests and owner-keyed state | `frontend/src/auth-context.js`, `use-watchlist.js` |
| Shared selected symbol and account/watchlist UI | `App.jsx`, `AccountControls.jsx`, `Watchlist.jsx` under `frontend/src` |
| Search/range fetch lifecycle and chart/table | `frontend/src/Analysis.jsx`, `PricePlot.jsx`, `styles.css` |
| Schema/migrations/importer | `backend/app/db.py`, `backend/migrations`, `backend/app/import_prices.py` |
| Explicit offline factory and test harness | `backend/app/demo.py`, `backend/tests/e2e_accounts_app.py`, `frontend/e2e/auth0-fixture.jsx` |

Public endpoints: `/api/stocks?query=...`, `/api/stocks/{symbol}/prices`, and
`/api/stocks/{symbol}/indicators`. Ranges are `1mo`, `3mo`, `1y`, `all`, meaning
21, 63, 252 and at most 2,000 stored sessions; the UI calls `all` Max. Search
returns at most 50 results, with exact ticker first. Missing company names stay
tickers. Unknown/empty symbol history is 404, invalid range 422, storage failure
sanitized 503 without fixture fallback.

Indicator points are `{date, sma_20, rsi_14}` aligned to price bars. Use API values,
retain nulls and match dates when joining responses. The fixed newest 10,000-bar
calculation window is independent of display range; only the displayed result is
trimmed. Metadata identifies methodology and anchor. Do not calculate RSI using
only the visible 21/63 bars. Read INDICATORS.md before implementing the UI.

Private calls use the existing `useAccount()` context / `authorizedFetch`, which
sends the app cookie, CSRF and expected-user headers. Do not bypass it with raw
watchlist fetches or introduce persistent Auth0 token storage. The backend accepts
verified bearer credentials too; invalid explicit bearer headers never fall back
to cookies. Preserve absolute session expiry, logout revocation, account-switch
isolation and owner-keyed UI state. Auth0 owns passwords and recovery; no local
password endpoint should be added.

## Data limitations

The team-supplied Yahoo Finance snapshot spans observations through 2026-11-12,
with source SHA256 and quarantine details in [DATASET_HANDOFF.md](DATASET_HANDOFF.md)
and [PRICES_IMPORT.md](PRICES_IMPORT.md). The input stays outside Git. Adjustment
semantics, upstream cleaning and historical universe membership are not verified;
USD is an assumption. `source_values` retains adjusted close/corporate actions,
but chart/indicator inputs use stored close. Do not silently substitute adjusted
close or label historical observations live. No recurring ingestion exists.

## Verification to preserve

These are dated local results, not a new run in the next conversation:

- Latest redesign: frontend lint/build passed; 19 chart/indicator browser tests
  passed against the real fixture API; nine account/session cases passed against
  the isolated SQLite harness, including SDK boundary checks. Desktop/mobile
  screenshots inspected and 1440/390/320px overflow checks passed. Normal-app
  PostgreSQL browser checks confirmed AAPL/MSFT indicators and stable MSFT latest
  values across 3M/1Y. No new hosted Auth0 acceptance, PG automated suite, hosted CI
  or deployment is claimed. Details and ignored screenshot paths are in
  FRONTEND_REDESIGN.md.
- Latest backend indicator phase: 95 passed, one expected SQLite invocation of a
  PostgreSQL-only concurrency test skipped; its PostgreSQL invocation passed.
  Ruff lint/format passed. Fixture and PostgreSQL indicator contracts were tested.
- Real HTTP against imported PostgreSQL: AAPL/MSFT, all four ranges aligned to
  prices and stable overlapping indicators; market/watchlist counts unchanged.
- Previous session phase: 11 chart and 9 account/session browser tests passed
  against disposable PostgreSQL, plus frontend lint/build. Those results predate
  the redesign; the latest indicator UI browser checks are listed above.
- Real Auth0: original/second-account signup/login, refresh, distinct watchlists,
  removal and logout verified; user confirmed recovery email receipt. No full
  password change was performed or independently verified.
- No hosted CI, second-machine acceptance or deployment is claimed. Local reports
  under `.local-data` are ignored and may not exist in another checkout.

From backend (run the environment check first):

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/continuation-check-001
```

Choose a fresh basetemp suffix per run. Set `STOCKSIGHT_TEST_DATABASE_URL` only to
a separate disposable PostgreSQL database ending in `_test` to include PG cases;
those tests migrate/downgrade tables. No value means SQLite-only database tests.

From frontend, after installing Chromium with `npx playwright install chromium`:

```powershell
npm run lint
npm run build
npm run test:e2e
npm run test:e2e:accounts
```

Browser suites start their own services; do not start extra copies on their ports.
Charts use 5174/8101 and explicit demo mode by default. To verify PostgreSQL, set
`STOCKSIGHT_E2E_DATABASE_URL` to a separately migrated/fixture-seeded disposable
database. Accounts use 5175/5176/8102 and a separate
`STOCKSIGHT_E2E_ACCOUNTS_DATABASE_URL` ending in `_test`, or disposable SQLite by
default. The account harness creates its test schema/data; never give it the
normal database. `STOCKSIGHT_PYTHON` can override the venv interpreter path.
Run suites sequentially when using a shared disposable test database.

Account browser tests use a test-only SDK boundary and real signed test tokens;
separate cases check actual SDK PKCE/callback handling. They do not prove a real
hosted code exchange. Test identity endpoints and SDK aliases must stay absent
from production. The account suite disables capture; chart traces are retained
on failure. No continuous screen capture is needed; use visual capture only when
necessary and keep sensitive artifacts ignored.

## Frontend increment — implemented

The authorized redesign includes SMA20/RSI14 toggles, plots, units, null warm-up
handling and current source/date context. Browser tests cover real fixture API
ranges and controlled short-history/failure/mismatch cases. Private requests still
use the unchanged session wrapper. Preserve independent retry, cancellation,
snapshot/date checks and bounded-history meaning in subsequent work. The new
use-indicators.js hook owns public indicator requests; PricePlot.jsx owns SVG
presentation. No client-side indicator computation was introduced.

Full MVP gates and unchanged team ownership remain in [ROADMAP.md](ROADMAP.md).

## Suggested prompt for the next conversation

> Continue StockSight in the current worktree. Read AGENTS.md and
> docs/CURRENT_HANDOFF.md, then inspect git status before changing files.
> The UConn-inspired redesign and SMA20/RSI14 frontend integration are implemented
> and locally verified; read docs/FRONTEND_REDESIGN.md. ML remains for Vlad.
> Work in one digestible phase at a time. Before live operations run
> the backend virtual-environment environment check. Preserve imported market
> data, existing accounts/watchlists and uncommitted changes. Do not push or
> merge without instruction. Report current state before starting the next phase.
