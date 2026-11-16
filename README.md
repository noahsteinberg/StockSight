# StockSight

A University of Connecticut CSE 4095 team project for historical stock analysis
and measurable machine-learning predictions. Educational use, not financial advice.

**Current foundation (November 16, 2026):** PostgreSQL-backed search/charts,
Auth0 signup/login, persistent app sessions, private watchlists and a tested
SMA20/RSI14 backend API. The frontend does not display indicators yet. ML,
forecasts/outcomes, evaluation and incremental provider refresh are unfinished.
The frontend redesign is deferred so work can proceed in separate phases.

**Start here:** [AGENTS.md](AGENTS.md), [current continuation handoff](docs/CURRENT_HANDOFF.md),
[local startup](docs/LOCAL_START.md), [API](docs/API.md) and
[architecture](docs/ARCHITECTURE.md). The handoff records the branch/working-tree
boundary, exact contracts, verification limits and proposed next increment.
No publication, hosted CI success or complete MVP is implied by local checks.

## Stack and source map

React/Vite JavaScript, plain CSS and native SVG communicate with FastAPI through
same-origin `/api`. PostgreSQL uses SQLAlchemy/Alembic. Auth0 owns credentials;
opaque HttpOnly server sessions restore login after refresh. Training will run
offline, separately from inference. No chart library, router or ML stack is installed.

| Directory | Contents |
| --- | --- |
| `frontend/src` | Analysis/chart, account context, private watchlist and existing styles |
| `frontend/e2e` | Chart and account/session browser tests |
| `backend/app` | API, authentication/sessions, repositories, indicators and imports |
| `backend/migrations` | Schema through `0004_app_sessions` |
| `backend/tests` | Numerical, HTTP-contract, migration, persistence and security tests |
| `docs` | Current handoffs, contracts, setup and dated reviews |
| `ml` | Planned feature/training/evaluation pipeline; no model implemented |

## Install and start

Use Node 24 LTS (package.json specifies supported versions), Python 3.12+, npm
and Git. CI uses Node 24/Python 3.13. PostgreSQL setup also requires Docker Desktop.
From a fresh checkout in PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m app.environment_check
```

Use the venv interpreter directly; activation is optional. On macOS/Linux use
`.venv/bin/python`. Before Docker or PostgreSQL verification add `--require-docker`
to the check. An access denial requires the runner's supported approval path,
not repeated restarts or reimports; see [execution access](docs/ENVIRONMENT_ACCESS.md).

For a deliberate database-free historical demo, from backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.demo:create_demo_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open [StockSight locally](http://127.0.0.1:5173). The explicit demo ignores saved
database settings and serves 506 historical AAPL observations. Its public price
and indicator APIs work; it does not verify accounts or PostgreSQL.
For the imported database and Auth0 setup, follow [LOCAL_START.md](docs/LOCAL_START.md).
Do not run `app.seed` over the existing team snapshot. API startup never imports,
migrates or silently falls back. No recurring live data feed is implemented.

## Configuration and verification

Root `.env` configures Compose; `backend/.env` configures FastAPI;
`frontend/.env.local` supplies public Auth0 SPA settings. Copy examples only for
a new setup and keep real values ignored. Vite `VITE_*` values are public and
must contain no secrets. Auth0 setup needs no client secret.

Use [the current handoff](docs/CURRENT_HANDOFF.md#verification-to-preserve) for exact
backend/browser commands, disposable database variables, test ports and evidence.
Latest backend phase: 95 passed, one expected skip, Ruff passed; live imported-data
HTTP indicator checks passed. Prior session phase: 11 chart and 9 account browser
tests plus frontend lint/build passed. These are dated local results. CI definitions
provision PostgreSQL and run backend and browser checks; hosted CI still needs a
verified run on the published head.

## Collaboration and scope

Team: Noah Steinberg, Gavin Javier Pino, Parth Sachdev, Vladislav Lagutin.
See [CONTRIBUTING.md](CONTRIBUTING.md) for review workflow, [TODO.md](TODO.md)
for incremental status, [SPECIFICATION.md](SPECIFICATION.md) for scope, and
[ROADMAP.md](docs/ROADMAP.md) for unchanged ownership and complete MVP gates.
Noah extends the working foundation; indicator UI is the proposed next phase,
with redesign separate and deferred. Never show fabricated predictions or call
the full MVP finished while ML, persistence/outcomes and evaluation remain absent.

## Documentation map

- [Current handoff](docs/CURRENT_HANDOFF.md) and [startup](docs/LOCAL_START.md)
- [API](docs/API.md), [indicator conventions](docs/INDICATORS.md), [architecture](docs/ARCHITECTURE.md)
- [Auth0/watchlists](docs/AUTH0_WATCHLIST_HANDOFF.md) and [sessions](docs/SESSION_HANDOFF.md)
- [Database](docs/DATABASE.md), [dataset evidence](docs/DATASET_HANDOFF.md), [import policy](docs/PRICES_IMPORT.md)
- [Security](docs/SECURITY.md), [deployment](docs/DEPLOYMENT.md), [ML plan](ml/README.md)
- [Frontend/backend acceptance guide](docs/FRONTEND_BACKEND_REVIEW.md)

Dated review reports and Phase 1 notes describe their historical scope. Current
contracts and startup instructions supersede old limitations and commands.
