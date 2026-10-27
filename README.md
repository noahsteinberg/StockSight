# StockSight

A University of Connecticut CSE 4095 Agentic Programming team project exploring stock analysis and measurable machine-learning predictions.

**Status: early scaffold (Phase 0).** The responsive informational landing page and `GET /api/health` work. No accounts, market data, watchlists, predictions, or database connection exist yet.

## Planned MVP

- Accounts and persistent watchlists
- Stock search, historical charts, and technical indicators
- Next-trading-day direction predictions with a precisely defined target
- Prediction history and evaluation against observed outcomes

See [SPECIFICATION.md](SPECIFICATION.md) for scope and open decisions, and [TODO.md](TODO.md) for the phased roadmap.

## Architecture and structure

React + Vite (JavaScript, plain CSS) will communicate with a Python FastAPI API. PostgreSQL and SQLAlchemy/Alembic are planned. ML research will remain separate from API request handling. No router, chart library, database driver, or ML dependencies are installed yet.

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

Use Node.js 24 LTS (or a version accepted by `frontend/package.json`), npm, Python 3.12+, and Git. CI uses Node 24 and Python 3.13. Run each service in its own terminal. No API keys or database are needed.

### Frontend

```sh
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. Navigation scrolls to informational sections; all four feature areas are explicitly marked coming soon. The page does not call the backend.

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

Defaults work without an environment file. Optionally copy root `.env.example` to `backend/.env`; `app/config.py` loads that exact location. `STOCKSIGHT_APP_NAME` overrides the API name and health response service field. A root `.env` is not loaded automatically. Tests explicitly set the expected service name.

Never commit `.env` files or credentials. Vite exposes `VITE_*` values to browsers, so they must never contain secrets. Database and provider settings will be introduced when those integrations are implemented.

## Collaboration

Team: Noah Steinberg, Gavin Javier Pino, Parth Sachdev, and Vladislav Lagutin.

Use a focused feature branch, run the relevant checks, and open a pull request for teammate review before merging to `main`. [CONTRIBUTING.md](CONTRIBUTING.md) gives the workflow. GitHub Actions runs frontend lint/build and backend Ruff/pytest without external services. An actual hosted CI run still requires pushing the repository.

AI coding agents should read this file, [SPECIFICATION.md](SPECIFICATION.md), [TODO.md](TODO.md), and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing scope. Do not add placeholder predictions or claim planned functionality works.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [current API](docs/API.md)
- [Database plan](docs/DATABASE.md) and [ML foundation](ml/README.md)
- [Security](docs/SECURITY.md) and [deployment plan](docs/DEPLOYMENT.md)

StockSight is for education and research only, not financial advice. Predictions will be uncertain and must never be presented as guaranteed returns.
