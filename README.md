# StockSight

A University of Connecticut CSE 4095 team project for historical stock analysis
and measurable machine-learning predictions. Educational use, not financial advice.

StockSight supports historical stock search and charts, SMA20/RSI14, chart
inspection and replay, Auth0 accounts, private watchlists and validated offline
daily-data refresh with a GitHub Actions runner. Predictions, model evaluation
and the proposed Explore/Compare/preferences features remain future work.

Start with the [current handoff](docs/CURRENT_HANDOFF.md) for the latest checkout,
release and verification status. Use [local startup](docs/LOCAL_START.md) to run
the app.

For the next product work, Vlad (@Hab1yer) and his AI should read the
[frontend product handoff](docs/FRONTEND_PRODUCT_HANDOFF.md). It proposes stock
discovery, comparison, optional preferences and future ML connectors, with
mandatory human review/approval before feature coding. It is not implemented UI.

## Stack and source map

React/Vite JavaScript, plain CSS and native SVG communicate with FastAPI through
same-origin `/api`. PostgreSQL uses SQLAlchemy/Alembic. Auth0 owns credentials;
opaque HttpOnly server sessions restore login after refresh. Training will run
offline, separately from inference. The chart uses native SVG and navigation uses URL fragments.

| Directory | Contents |
| --- | --- |
| `frontend/src` | Analysis/chart, account context, private watchlist and existing styles |
| `frontend/e2e` | Chart and account/session browser tests |
| `backend/app` | API, authentication/sessions, repositories, indicators and imports |
| `backend/migrations` | Schema/access controls through `0006_market_refresh` |
| `backend/tests` | Numerical, HTTP-contract, migration, persistence and security tests |
| `docs` | Current handoff, contracts, setup and product plans |
| `ml` | Offline research evidence and evaluation protocols |

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
as described in [execution access](docs/LOCAL_START.md#execution-access).

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
migrates or silently falls back. [Daily refresh](docs/DAILY_REFRESH.md) runs
separately from web requests; it updates completed sessions, not streaming quotes.

## Configuration and verification

Root `.env` configures Compose; `backend/.env` configures FastAPI;
`frontend/.env.local` supplies public Auth0 SPA settings. Copy examples only for
a new setup and keep real values ignored. Vite `VITE_*` values are public and
must contain no secrets. Auth0 setup needs no client secret.

Run the documented [lint, build, backend and browser checks](docs/LOCAL_START.md#verification).
Use a disposable database for tests that migrate or reset schemas.

## Collaboration and scope

Team: Noah Steinberg, Gavin Javier Pino, Parth Sachdev, Vladislav Lagutin.
See [contributing](CONTRIBUTING.md) for review workflow,
[specification](SPECIFICATION.md) for scope and [roadmap](docs/ROADMAP.md)
for team responsibilities and MVP gates.

## Documentation

- [Current frontend/product plan for Vlad](docs/FRONTEND_PRODUCT_HANDOFF.md): proposed pages, workflows, data contracts and approval gates

- [Parth's November 23 data migration: work summary and evidence](docs/PARTH_DATA_UPDATE_2026-11-23.md)
- [Current handoff](docs/CURRENT_HANDOFF.md) and [local startup](docs/LOCAL_START.md)
- [Architecture and navigation](docs/ARCHITECTURE.md), [API](docs/API.md) and [indicators](docs/INDICATORS.md)
- [Auth0 accounts, sessions and watchlists](docs/ACCOUNTS.md) and [security](docs/SECURITY.md)
- [Database](docs/DATABASE.md), [historical imports](docs/PRICES_IMPORT.md) and [provider research](docs/YAHOO_FINANCE.md)
- [Vercel deployment](docs/VERCEL.md) and [Supabase setup](docs/SUPABASE.md)
- [ML research](ml/README.md), [frontend integration spec](docs/FRONTEND_ML_INTEGRATION_SPEC.md) and [product integration plan](docs/ML_PRODUCT_INTEGRATION_PLAN.md)
