# StockSight

A University of Connecticut CSE 4095 Agentic Programming team project exploring stock analysis and measurable machine-learning predictions.

**Status: historical data and account/watchlist foundation.** Search and charts read the team snapshot from PostgreSQL. Auth0 sign-in UI and private persistent watchlist APIs are implemented; real hosted signup/login verification awaits tenant configuration. Indicators, predictions and refresh ingestion remain planned. See [account setup and API handoff](docs/AUTH0_WATCHLIST_HANDOFF.md) and [dataset status](docs/DATASET_HANDOFF.md).

## Planned MVP

- Accounts and persistent watchlists
- Stock search, historical charts, and technical indicators
- Next-trading-day direction predictions with a precisely defined target
- Prediction history and evaluation against observed outcomes

See [SPECIFICATION.md](SPECIFICATION.md) for scope and open decisions, [TODO.md](TODO.md) for the existing checklist, and [team roadmap](docs/ROADMAP.md) for the proposed team milestones, responsibilities, and professor-demo acceptance criteria.

## Architecture and structure

React + Vite (JavaScript, plain CSS) will communicate with a Python FastAPI API. PostgreSQL persistence uses SQLAlchemy and Alembic migrations. ML research will remain separate from API request handling. The chart uses SVG and an accessible observations table. No router, external chart library, or ML dependencies are installed.

```text
StockSight/
├── .github/                  # CI and pull-request template
├── frontend/                 # React landing page, Vite, ESLint
│   └── src/                  # App.jsx, main.jsx, styles.css
├── backend/
│   ├── app/                  # main.py, config.py, api/health.py
│   └── tests/                # Health endpoint contract test
├── database/README.md        # Future persistence foundation
├── ml/README.md              # Future ML pipeline and evaluation
├── docs/                     # Architecture, API, security, deployment
├── .env.example
├── CONTRIBUTING.md
├── SPECIFICATION.md
└── TODO.md
```

## Local setup

For current commands and 503 recovery, see [local startup](docs/LOCAL_START.md) and the [integration adversarial review](docs/reviews/INTEGRATION_ADVERSARIAL_REVIEW.md). Use the explicit demo factory to view charts without PostgreSQL.

Use Node.js 24 LTS (or a version accepted by `frontend/package.json`), npm, Python 3.12+, and Git. CI uses Node 24 and Python 3.13. Run each service in its own terminal. No API keys are needed; fixture mode works without a database. Database mode requires the local PostgreSQL setup.

### Frontend

```sh
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. Start the backend too, then search AAPL or Apple, select a result, and choose a range. Vite proxies /api to FastAPI on port 8000. The demo uses historical observations, not live prices.

```sh
npm run lint
npm run build
npm run preview
```

`npm run preview` serves the built page locally, usually at <http://localhost:4173>. Use `npm ci` for reproducible installs from the committed lockfile.

### Backend (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Using the interpreter directly avoids PowerShell activation-policy issues. On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` (create the environment with `python3 -m venv .venv` if necessary).

Health: <http://127.0.0.1:8000/api/health>. Interactive API documentation: <http://127.0.0.1:8000/docs>.

```json
{"status": "ok", "service": "stocksight-api"}
```

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
```

Runtime-only environments can install `requirements.txt`; contributors and CI install `requirements-dev.txt`.

### Environment

Defaults use the historical fixture without an environment file. Copy `backend/.env.example` to `backend/.env` for API settings; `app/config.py` loads that exact location. Root `.env.example` is for Docker Compose; see [database setup](docs/DATABASE.md). `STOCKSIGHT_APP_NAME` overrides the API name and health response service field. A root `.env` is not loaded automatically. Tests explicitly set the expected service name.

Never commit `.env` files or credentials. Vite exposes `VITE_*` values to browsers, so they must never contain secrets. STOCKSIGHT_DATABASE_URL already selects storage; a saved nonempty URL requires running, migrated, seeded PostgreSQL.

## Collaboration

Team: Noah Steinberg, Gavin Javier Pino, Parth Sachdev, and Vladislav Lagutin.

Use a focused feature branch, run the relevant checks, and open a pull request for teammate review before merging to `main`. [CONTRIBUTING.md](CONTRIBUTING.md) gives the workflow. GitHub Actions runs frontend lint/build and backend Ruff/pytest without external services. An actual hosted CI run still requires pushing the repository.

AI coding agents should read this file, [SPECIFICATION.md](SPECIFICATION.md), [TODO.md](TODO.md), and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing scope. Do not add placeholder predictions or claim planned functionality works.

## Documentation

- [Execution-access diagnostics](docs/ENVIRONMENT_ACCESS.md)
- [Team dataset import](docs/PRICES_IMPORT.md)
- [Frontend/backend review guide](docs/FRONTEND_BACKEND_REVIEW.md)
- [Architecture](docs/ARCHITECTURE.md) and [current API](docs/API.md)
- [Database plan](docs/DATABASE.md) and [ML foundation](ml/README.md)
- [Security](docs/SECURITY.md) and [deployment plan](docs/DEPLOYMENT.md)

StockSight is for education and research only, not financial advice. Predictions will be uncertain and must never be presented as guaranteed returns.

### Browser regression tests

With backend dependencies installed in backend/.venv, from frontend run `npx playwright install chromium` then `npm run test:e2e`. The suite starts isolated services on ports 5174/8101. See [Phase 1](docs/PHASE_1.md) for interpreter overrides, scope, and verification evidence. Normal manual development continues on ports 5173/8000.
