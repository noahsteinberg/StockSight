# StockSight — continuation handoff for Gavin and the next agent

For the latest login task and exact pending publication/configuration steps, start
with [LOGIN_CONTINUATION_HANDOFF.md](LOGIN_CONTINUATION_HANDOFF.md) (November 17).

## November 17 follow-up: embedded verification and error flow

After PR #12 was merged, live Auth0 logs first showed `Cross origin login not
allowed.` With explicit user approval, the existing SPA's cross-origin switch
was enabled and Allowed Origins (CORS) was limited to the rose production origin.
Subsequent attempts showed `Unable to configure verification page.`

The follow-up adds the dedicated `/cross-origin-verification.html` Vite entry,
using Auth0.js's verifier handshake with an origin/parent guard. After deployment,
its exact production URL must be set in Auth0's Cross-Origin Verification Fallback
URL field. It does not render the app, exchange user tokens or collect passwords.
The user requested removal of the hosted Auth0 login fallback link; it is removed.
Safe provider callback errors now survive the session restoration wrapper instead
of all being reported as an app-session restoration problem. Google is preserved.

Gavin chose to keep `vercel.app`. Auth0 documents that this verification fallback
cannot overcome blocked third-party cookies in Chrome/Safari; a same-site custom
domain is needed for reliable embedded password login in those conditions. Do not
disable browser privacy/security protections or claim successful real-user login.
See EMBEDDED_LOGIN.md for the setup and explicit acceptance boundary.

Follow-up verification: frontend lint/build and both public/account Playwright
suites passed (20 account cases). The verification-page tests cover standalone,
untrusted-parent and trusted Auth0-origin SDK handshake behavior with intercepted
provider traffic. These checks do not establish live password-login success or
overcome browser third-party-cookie restrictions. Deployment and the tenant's
verification fallback URL update remain pending.

November 17 continuation: read [NEXT_AGENT_HANDOFF.md](NEXT_AGENT_HANDOFF.md)
and [the detailed integration specification](FRONTEND_ML_INTEGRATION_SPEC.md).
Noah reports Auth0 settings are fixed. Full hosted account acceptance is still
separate from that configuration update. ML is explicitly paused; this handoff
does not authorize more research or implementation until the next user task.

Updated November 16, 2026. Start with the root [AGENTS.md](../AGENTS.md).

## November 17 embedded account pages

Gavin approved the static navy-chart account design and authorized local forms
with Auth0 managing all identities/passwords. The current branch was fast-forwarded
to `f433229` (all previous branch commits were already included) before integrating.
`AuthPage.jsx` now serves `/#/login`, `/#/signup`, and `/#/reset-password`.
Auth0.js 10.3.0 handles cross-origin username/password login and validated fragment
callbacks; Google retains the official React SDK's Authorization Code + PKCE.
Signup permits the tenant's existing optional-email behavior. The backend's
HttpOnly session, CSRF, expiry and account-switch contracts are unchanged.

Read [EMBEDDED_LOGIN.md](EMBEDDED_LOGIN.md) before tenant setup or live acceptance.
The `auth0/` directory retains earlier hosted-template drafts and disabled standalone
previews; those are not the functional React account pages and need not be uploaded.
No real tenant setting, user, password, imported data or deployment was changed.

Verification for this increment: frontend lint/build passed; 17 account browser
cases and 26 public browser cases passed. Accounts used disposable SQLite, signed
test identities, actual Auth0.js callback validation and intercepted provider HTTP.
Google PKCE was checked through the real React SDK. Guest desktop/mobile screenshots
were reviewed, including 1440/390/320px layout checks. npm reported zero vulnerabilities
after updating Auth0.js from 10.0.0 to the current patched 10.3.0 release.
This is not live-tenant, hosted browser, PostgreSQL, or deployment acceptance.
The user still needs the SPA's origin/CORS, Implicit grant and cross-origin settings
confirmed and a real-browser account test. Production cookie constraints and the
explicit hosted fallback are documented in EMBEDDED_LOGIN.md.

## November 17 deployment diagnosis

Noah's Vercel account imported current main (`ae3a80e`) into project
`prj_RjOsm0SDpprpf9iOWOA5NIfrAhtq`, named `stocksight`, with production domain
`https://stocksight-rose.vercel.app`. All seven environment-variable keys are
present for Production. Secret values were not retrieved.

The frontend renders, but public health, readiness and stock history returned
HTTP 500. Build logs show dependency installation from the tool-only
`backend/pyproject.toml`; runtime logs show `ModuleNotFoundError: pydantic`.
This branch adds the existing pinned runtime dependencies to pyproject and a
parity test against requirements.txt. No dependency versions, API behavior,
database data or authentication provider were changed.

Clean local Python 3.12 environment installation directly from the pyproject
dependency list succeeded. The manifest-parity and hosted-entrypoint tests passed
(5 tests); the new test passed Ruff lint/format checks and pip check found no
broken requirements. These checks do not establish Vercel runtime acceptance.

Noah authorized publication; fix `a2cece2` was pushed to main. Native Git integration
automatically created production deployment `dpl_FGJWUuT5dyvWkrz48n1ytEDwf4mo`
from that exact SHA and reached READY. Its build installed pyproject dependencies.
The repository's read-only `scripts/check_deployment.py` passed against the rose
domain: frontend HTML, health, database readiness, AAPL search/history/indicators,
guest session, private-watchlist rejection and invalid-range rejection. Storage
reported database, 63 visible bars ending 2017-02-16, Plotly historical Apple data.
No error/fatal records were returned for this deployment in the inspected window.

The production smoke workflow's default origin now targets the rose domain;
an existing repository PRODUCTION_URL variable, if present, takes precedence
and should match it. Its current value and hosted Actions execution were not
verified through the connected tooling. Earlier billing restrictions remain
historical evidence, not a current CI diagnosis.

Noah reports updating STOCKSIGHT_APP_ORIGIN. Verify the exact rose origin is also
in the existing Auth0 callback/logout/web-origin allowlists. The earlier proposed
stocksight.vercel.app address was not assigned. Browser host access was unavailable
in this agent session, so rendered chart interaction and authenticated login,
watchlist persistence, logout and two-account isolation remain for real-browser
acceptance. API acceptance does not establish those account flows.

This is the current implementation summary; dated review reports preserve past
findings and are not current startup instructions.

## Direct Supabase backend acceptance complete — November 16

Parth completed private password entry. The connection was validated for the
intended project, transferred into ignored `backend/.env` with mode 0600, and the
temporary credential file was removed. No secret was printed or added to Git.
The original private-entry and dashboard-only limitations below describe earlier
stages; the direct backend connection is now verified.

Fresh read-only checks against the actual hosted database passed:

- `app.doctor`: `Storage ready: database`.
- Alembic schema comparison: no new upgrade operations, head 0005.
- Stored AAPL digest matches all 506 fixture date/OHLC/volume records.
- Seven tables have RLS enabled, with no table access for either browser role.
- A temporary normal Uvicorn process served real localhost HTTP requests backed
  by Supabase, rather than the explicit fixture factory or TestClient.
- Health/readiness returned 200 and readiness explicitly reported `database`.
- Search found AAPL / Apple Inc. Price and indicator requests passed for 1mo,
  3mo, 1y and all (21/63/252/506 observations). All returned price bars matched
  the bundled source; indicator dates aligned and latest values were stable.
- Invalid range returned 422 and unsupported MSFT returned 404.
- Counts before/after remained one stock, one series, 506 bars and zero identity,
  watchlist and session records. No migrations, seeds, resets or writes ran during
  acceptance. The verification server was stopped after the checks.

Sanitized evidence is in ignored `.local-data/supabase-backend-acceptance.json`.
This establishes direct hosted PostgreSQL and normal backend HTTP integration.
The selected data remains historical AAPL, latest session 2017-02-16. Yahoo
Finance research/access is verified as recorded below; automated refresh remains
future work. Gavin still owns Vercel deployment, HTTPS routing and hosted Auth0
acceptance. No running frontend, public deployment or real account flow is claimed.

## Hosted Supabase bootstrap and approved demo — November 16

Parth created a Supabase project and authorized setup through its authenticated
dashboard. The public schema was confirmed empty before applying an equivalent
bootstrap of migrations 0001–0005. Seven tables now exist at
`0005_backend_only_access`. Dashboard SQL inspection confirmed RLS enabled on
all seven and no SELECT/INSERT/UPDATE/DELETE/TRUNCATE privilege for either `anon`
or `authenticated`. This is actual hosted SQL/catalog evidence, separate from
the earlier embedded PostgreSQL checks below.

Parth explicitly selected the small historical AAPL demo. The import SQL was
generated by capturing the existing `app.seed.seed_fixture` statements, wrapped
in a transaction and a guard against replacing another canonical AAPL series.
Hosted verification confirmed:

- AAPL / Apple Inc.; 506 bars, 2015-02-17 through 2017-02-16.
- Series `plotly-aapl-unadjusted-v1`, mode `historical_fixture`.
- Every stored date/OHLC/volume value matched the bundled fixture's canonical
  six-decimal digest: `8c1e84b0602f5ff0b126dd87197ce424` (MD5 integrity comparison,
  not a security credential).
- Seven RLS-protected tables, zero tables accessible to the two browser roles.

The team Parquet snapshot was not imported. This demo is deliberately historical;
the Yahoo feasibility work below does not turn it into a current feed.

The session and transaction pooler details were read from the actual Connect
dialog. Its database password remains a user-held secret. The local backend's
private connection still needs that password configured; no direct psycopg,
FastAPI-over-Supabase, Vercel, or real Auth0 result is claimed by the dashboard
checks. A local private-entry helper was supplied outside Git; it preserves
other env settings, encodes the password, saves `.env` with mode 0600, and runs
the environment check and sanitized doctor command after entry. Helper checks
covered encoding, retained settings, duplicate-key removal and atomic private
writes. Project details and screenshots stay outside Git.

The user's Terminal was subsequently denied reading the helper under Documents
(`Operation not permitted`). A separate standard-library-only helper was prepared
in a private temporary folder, with no Documents access required for password
entry. It stages the URL in an owner-only file inside an owner-only directory;
the agent can then transfer it into the ignored backend `.env`, remove the staged
secret, and verify storage. No credential has been supplied or connection verified
at this point. Checks passed for password encoding, file/directory permissions,
refusal to overwrite an existing entry and refusal to follow a symlink. The
temporary helper's read-only `--check` passed from outside Documents.

## Supabase preparation and provider investigation — Parth, November 16

This increment starts from published main `efc6534` (the merge of Gavin's app-view
work), in a fresh checkout on `feature/supabase-setup`. Earlier branch/delivery
notes below are historical. No source dataset, credentials, or local database
was present in this checkout.

- [SUPABASE.md](SUPABASE.md) describes project creation, private connection settings,
  reviewed migrations, initial dataset choices and hosted acceptance.
- Dashboard-style PostgreSQL URLs select the installed psycopg driver. Supabase
  connections require TLS, preserve stronger verification settings, and port
  6543 disables prepared statements with one pooled connection per process.
- Optional `STOCKSIGHT_MIGRATION_DATABASE_URL` lets Alembic use a direct/session
  connection while Vercel uses transaction pooling for the normal API URL.
- Head `0005_backend_only_access` enables PostgreSQL RLS and revokes application
  table/version-table access from PUBLIC and the Supabase browser roles if they
  exist. No browser policies are introduced; the initial backend uses the trusted
  table-owning connection and retains existing Auth0/session authorization.
- [YAHOO_FINANCE.md](YAHOO_FINANCE.md) records the provider/API-contract findings,
  mapping and correction/failure policy. No refresh writer or scheduler was added.

New checks from backend on macOS/Python 3.13:

```sh
.venv/bin/python -m app.environment_check
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
mkdir -p .pytest_cache
.venv/bin/python -m pytest -q --basetemp=.pytest_cache/supabase-003 --tb=short
```

Result: Ruff passed; 88 tests passed, two skipped (the existing PostgreSQL-only
concurrency case and new browser-role isolation case). These exercise unit,
SQLite/TestClient and offline PostgreSQL SQL-generation paths. The dedicated
PostgreSQL test also attempts SELECT/DELETE/TRUNCATE as both browser roles and
checks retained owner access when run against an appropriate disposable PG DB.
It must not target the hosted application database.

Initial fresh-checkout pytest setup failed because the `.pytest_cache` parent
did not yet exist; creating the parent resolved it. Native PostgreSQL initdb
was denied `shmget` shared-memory access, so no local PG server started and the
opt-in PG invocation could not connect. Do not describe these as PostgreSQL
acceptance. No hosted Supabase migration/readiness/account result is established.
No frontend files changed, and no new browser/hosted Auth0/CI checks were run.

An additional isolated **embedded PostgreSQL (PGlite)** check executed the generated
full migration SQL with and without pre-existing browser roles. Both reached head
0005 with seven RLS-protected tables and retained table-owner access. With
Supabase-like default grants, all 42 attempted SELECT/DELETE/TRUNCATE operations
across seven tables and two browser roles were denied (SQLSTATE 42501). This
verifies SQL execution/access behavior in the embedded engine; it does not verify
psycopg connections, Supavisor, concurrent PostgreSQL, or a hosted Data API.

Read-only Yahoo feasibility: isolated `yfinance==1.8.0` returned five daily bars
each for AAPL/MSFT, 2026-11-09 through 2026-11-13, America/New_York dates, unique
ascending index and zero missing OHLCV/adjusted-close fields. Explicit unadjusted
request options retained adjusted close and corporate actions separately. No
API key was provided; no stored data was changed. This is a small successful
provider request, not real-time streaming, scheduling or production permission.

The hosted bootstrap/demo follow-up above supersedes this phase's original
outstanding project/migration/data steps. Private backend connection and actual
application acceptance are still pending.
Gavin remains responsible for Vercel deployment under the meeting's assignment.

## Checkout and delivery state

Gavin's implementation checkout is on `feature/auth0-watchlists`, following
`b0e256a` (frontend redesign and indicator UI). The new dashboard, navigation,
ML-unavailable views and methodology page are delivered with this update. Check
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
| Watchlists | Private persistence, save/remove/open, capacity 100, account isolation; compact sidebar and full dashboard with filtering/saved dates | Later product refinements |
| Indicators | SMA20 overlay and RSI14 panel/toggles; independent retries, snapshot alignment, null handling and date inspection | Future indicators only if separately scoped |
| ML / forecasts | Navigable Predictions/Model performance unavailable states; selected-stock context; no ML calls or metrics | Vlad's ML, inference, persisted forecasts/outcomes and live evaluation UI integration |
| Delivery | Local checks; CI definitions include disposable PostgreSQL and browser tests | Hosted CI on published head, second-machine setup and deployment/demo acceptance |

**Phase boundary:** Gavin subsequently authorized a UConn-inspired frontend
redesign and existing indicator integration. That phase is implemented and locally
verified; see [FRONTEND_REDESIGN.md](FRONTEND_REDESIGN.md) for research, changes,
evidence and limitations. ML remains for Vlad per Gavin's current direction.
The following app-view phase adds Dashboard, Predictions, Model performance and
Methodology navigation; see [APP_VIEWS.md](APP_VIEWS.md). ML pages deliberately
remain unavailable until their real backend contracts exist. No ML/provider refresh
work was bundled. The complete MVP is not finished.

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

App navigation uses `#/dashboard`, `#/analysis`, `#/predictions`, `#/performance`
and `#/methodology`; optional validated `symbol` query context connects Analysis
and Predictions. Root `/` remains Analysis. Legacy anchors are accepted. See
APP_VIEWS.md for history, focus, Auth0 callback and dashboard contracts.

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

- Latest app-view phase: lint/build passed; full 25 public browser and 11 account/
  session cases passed. A final stock-context refinement and seventh page case
  passed in the focused seven-case page run. Guest desktop/mobile screenshots
  inspected; 1440/390/320px overflow checks and signed-test dashboard filtering,
  persistence, removal and sign-out privacy passed. Fixtures/isolated SQLite only;
  no new hosted Auth0, PostgreSQL or deployment verification. See APP_VIEWS.md.
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
> Dashboard, navigation and explicit ML-unavailable pages are implemented;
> read docs/APP_VIEWS.md before continuing. Do not invent forecasts or metrics.
> Work in one digestible phase at a time. Before live operations run
> the backend virtual-environment environment check. Preserve imported market
> data, existing accounts/watchlists and uncommitted changes. Do not push or
> merge without instruction. Report current state before starting the next phase.
