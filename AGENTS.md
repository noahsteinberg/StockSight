# StockSight working instructions

## Start here

Read [the current handoff](docs/CURRENT_HANDOFF.md), [local startup](docs/LOCAL_START.md),
[API](docs/API.md) and [architecture](docs/ARCHITECTURE.md). Use the specialist
guides for [indicators](docs/INDICATORS.md), [accounts](docs/ACCOUNTS.md) and
[imports](docs/PRICES_IMPORT.md). [ROADMAP.md](docs/ROADMAP.md) holds team
ownership and MVP gates.

Use docs/CURRENT_HANDOFF.md as the sole continuation handoff. Update it with
current work, delivery state and evidence. Keep durable procedures and contracts
in their guides. Inspect the actual branch and working tree before making
changes. Ignored configuration, local data and unpublished commits vary by
checkout.

## Product implementation requires human review first

For the next product/frontend work, read
[the release and next increments](docs/NEXT_RELEASE_AND_ML_HANDOFF.md) before changing application
code, contracts, schema, dependencies or UX. Vlad (@Hab1yer) coordinates it.
Present concrete proposed changes and a small wireframe, ask the supervising
user concise multiple-choice questions about unresolved UX decisions, and wait
for explicit approval of the increment before coding. Record answers; do not
re-ask decisions already approved. Return the tested result for human review
before merge/deployment unless that specific action was already authorized.
Planning/documentation/issue consolidation can proceed when requested; they
do not automatically authorize a future agent's feature implementation.

Gavin's standing preference: commit completed changes after appropriate
verification at the end of each task. Include intended source/docs changes, keep
local data/credentials/evidence ignored, inspect the diff and preserve unrelated
work. Do not leave completed work uncommitted merely because a separate commit
request was not repeated. Local commits are expected; pushing or merging still
requires instruction.

## Implemented foundation and phase boundary

- React/Vite JavaScript and plain CSS; native SVG price/volume chart, ticker/company
  search, ranges, keyboard date inspection, accessible table and watchlist UI.
- FastAPI, SQLAlchemy/Alembic and PostgreSQL; repository migration head
  `0007_user_preferences` (issue #19 phase 4); hosted head `0006_market_refresh`
  until 0007 is applied in a reviewed, coordinated release.
  Production schema/API and the full 494-stock hosted refresh were verified
  November 23. Both manual Actions modes passed; Noah reports enabling the
  schedule variable. The first actual scheduled event remains unobserved.
  See docs/DAILY_REFRESH.md before activating incremental updates.
  Explicit fixture mode is available. No provider request runs inside chart APIs.
  Supabase setup and connection/security behavior are in docs/SUPABASE.md;
  docs/YAHOO_FINANCE.md records provider research without enabling refresh.
- Auth0 Universal Login/PKCE, verified API JWTs, private watchlists and opaque
  HttpOnly app sessions. Refresh restores the app session without relying on an
  Auth0 silent iframe. Username signup with optional recovery email is configured.
- SMA20/Wilder RSI14 backend API and frontend toggles/plots are implemented and
  locally verified. See INDICATORS.md for null
  warm-up values, fixed calculation history and versioned numerical conventions.
- Dashboard, Explore, Compare and optional private research preferences are
  implemented on the combined release branch. Product ML inference, stored
  forecasts and outcomes, and evaluation remain unfinished. Keep the
  typed unavailable state until an output is approved.

Read the [application view contracts](docs/ARCHITECTURE.md) before wiring ML.
Preserve team ownership in ROADMAP.md and follow the current task scope.

## Execution and data safety

Before Docker commands, development-server startup or live HTTP/database tests,
run backend's virtual-environment Python with `-m app.environment_check` from
backend. This is a read-only execution-access check; see docs/LOCAL_START.md.

Distinguish permission_denied from not_running/not_listening. If access is denied,
do not repeatedly restart servers or scan/import the dataset to troubleshoot it.
Use the configured approval mechanism if available; otherwise report the precise
execution limitation and continue useful offline checks. Project code cannot
grant permissions withheld by the session runner. Never report a service reachable
solely because its process printed a ready message.

Use a unique subdirectory under backend/.pytest_cache as pytest --basetemp when
the sandbox's redirected temporary directory is inaccessible. Do not replace
integration tests with direct calls and then describe them as HTTP/browser tests.

Keep source datasets, credentials and local verification reports outside Git.
Use the explicit demo factory for offline fixture runs; do not silently fall back
from configured database reads. Import commands and replacement semantics are in
docs/PRICES_IMPORT.md. No screen capture is needed for normal backend operations.

The existing imported database must not be seeded with `app.seed`, reset, or
reimported to fix a listener/access problem. Do not delete Docker volumes.
Use a separate disposable database ending in `_test` for destructive test setup;
never use the normal development URL in any test-database variable.
Screen capture is allowed only when necessary; no continuous capture. Keep real
passwords, cookies, bearer tokens, reset links and personal account identifiers
out of tool output, Git and documentation. Users enter hosted Auth0 credentials
themselves. Test identity routes/SDK aliases must remain test-only.

## Preserve these integration contracts

- `/api` is same-origin through Vite (production needs equivalent routing).
  Use `127.0.0.1:5173` consistently with Auth0 callbacks and app Origin settings.
- The frontend uses `AuthProvider.jsx` / `useAccount()` / `authorizedFetch` for
  private calls. Preserve cookies, CSRF headers, expected-user checks, expiry,
  logout revocation and account-switch isolation; never persist Auth0 tokens.
- Price/indicator ranges count stored sessions: 21, 63, 252, or Max 2000.
  Honor provenance, `as_of`, `has_earlier`, nulls and the actual adjustment label.
  Indicators calculate before display trimming; clients must not recompute RSI
  from the visible slice. No live-price or adjusted-price claim is established.
- Before finishing, run checks relevant to changed behavior and update the handoff.
  Distinguish numerical/unit, TestClient, live HTTP, browser, PostgreSQL and hosted
  Auth0 evidence. Old test counts are dated evidence, not a new verification run.
  Verification commands and test ports are in LOCAL_START.md.
