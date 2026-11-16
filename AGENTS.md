# StockSight working instructions

## Start here

Read this file, [current continuation handoff](docs/CURRENT_HANDOFF.md),
[local startup](docs/LOCAL_START.md), [API](docs/API.md), and
[architecture](docs/ARCHITECTURE.md) before implementation. Read the relevant
specialist contract: [indicators](docs/INDICATORS.md),
[sessions](docs/SESSION_HANDOFF.md), [accounts](docs/AUTH0_WATCHLIST_HANDOFF.md),
or [imports](docs/PRICES_IMPORT.md). Use [TODO.md](TODO.md) for incremental work
and [ROADMAP.md](docs/ROADMAP.md) for the complete MVP gates and team ownership.

This is the canonical agent instruction file (`AGENTS.md`, not `agent.md`).
Current baseline: November 16, 2026. Read the checkout's `git status` and branch;
do not assume Gavin's uncommitted work, ignored configuration or local database
is present in another conversation or checkout. The current working branch is
`feature/auth0-watchlists`; indicator work and this documentation update follow
commit `6131c5e` and are delivered with this handoff in a local commit. Inspect
Git history for the actual current head. No push, merge or hosted CI success is
claimed. This worktree is the preferred continuation location.

Gavin's standing preference: commit completed changes after appropriate
verification at the end of each task. Include intended source/docs changes, keep
local data/credentials/evidence ignored, inspect the diff and preserve unrelated
work. Do not leave completed work uncommitted merely because a separate commit
request was not repeated. Local commits are expected; pushing or merging still
requires instruction.

## Implemented foundation and phase boundary

- React/Vite JavaScript and plain CSS; native SVG price/volume chart, ticker/company
  search, ranges, keyboard date inspection, accessible table and watchlist UI.
- FastAPI, SQLAlchemy/Alembic and PostgreSQL; migration head `0004_app_sessions`.
  Explicit fixture mode is available. No provider request runs inside chart APIs.
- Auth0 Universal Login/PKCE, verified API JWTs, private watchlists and opaque
  HttpOnly app sessions. Refresh restores the app session without relying on an
  Auth0 silent iframe. Username signup with optional recovery email is configured.
- SMA20/Wilder RSI14 backend API and frontend toggles/plots are implemented and
  locally verified. See INDICATORS.md for null
  warm-up values, fixed calculation history and versioned numerical conventions.
- ML training/inference, stored forecasts/outcomes, evaluation, incremental
  provider refresh and production deployment remain unfinished. Do not add fake
  scores, prices, forecasts or claims that the full MVP is complete.

Gavin subsequently authorized a UConn-inspired frontend redesign and existing
indicator integration. That phase is implemented; see docs/FRONTEND_REDESIGN.md
for reference research, changes and dated verification. Keep subsequent phases
digestible and follow the current request. ML remains for Vlad per Gavin's direction.
The following app-view phase adds hash navigation, a full private dashboard,
methodology and explicit unavailable prediction/performance views. Read
docs/APP_VIEWS.md before wiring ML; no prediction/evaluation APIs exist yet.
Preserve the team ownership table in ROADMAP.md; it is coordination, not a ban
on implementing across layers. Follow the current user's task scope.

## Execution and data safety

Before Docker commands, development-server startup or live HTTP/database tests,
run backend's virtual-environment Python with `-m app.environment_check` from
backend. This is a read-only execution-access check; see docs/ENVIRONMENT_ACCESS.md.

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
  Exact commands, test ports and acceptance steps are in CURRENT_HANDOFF.md.
