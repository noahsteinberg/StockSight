# Architecture

Current implementation and phase boundaries are summarized in
[CURRENT_HANDOFF.md](CURRENT_HANDOFF.md). The UConn-inspired frontend redesign
and indicator integration are documented in [FRONTEND_REDESIGN.md](FRONTEND_REDESIGN.md).

## Implemented

- `frontend/src/App.jsx`: shared shell and state with hash-based page navigation
  through use-page-route.js. Pages.jsx provides Dashboard, Predictions, Model
  performance and Methodology. Analysis.jsx preserves the existing API-driven
  charts/indicators. See APP_VIEWS.md; prediction/evaluation pages are unavailable
  views until real ML endpoints exist. No routing dependency was added.
- `backend/app/main.py`: application factory and FastAPI instance. Routes mount under `/api`.
- `backend/app/api/health.py`: Pydantic response schema and process health route.
- `backend/app/config.py`: typed environment settings; optional `backend/.env` loading. Tests inject settings for a deterministic service name.
- app/api/stocks.py selects explicit fixture or SQLAlchemy repository reads; database mode requires PostgreSQL. app/seed.py imports the historical fixture independently, and Alembic owns schema changes.
- Vite proxies /api to localhost:8000 during development. Production hosting must supply equivalent routing.
- AuthProvider.jsx uses Auth0 Universal Login through the React SDK. app/auth.py
  validates API access tokens; app/api/accounts.py provisions verified identity
  references and restricts watchlist operations to the current user. Migration
  0003 adds identity/watchlist tables. No local password store is introduced.
- Watchlist.jsx and use-watchlist.js provide the personal dashboard; App.jsx shares
  selected-stock state with the existing Analysis.jsx chart. Auth0 configuration
  and current real-tenant acceptance are documented in AUTH0_WATCHLIST_HANDOFF.md.
- Migration 0004 adds opaque app sessions. Auth0 JWTs bootstrap an HttpOnly cookie;
  PostgreSQL stores its digest, expiry and CSRF state. The frontend restores the
  session independently of Auth0's silent iframe flow. See SESSION_HANDOFF.md for
  the cookie/bearer API contract and real-account verification.

- `app/indicators.py` calculates close-based SMA20 and Wilder RSI14 over a fixed
  bounded history, before trimming display ranges. The public indicator route
  shares storage/error behavior with prices. Frontend use-indicators.js consumes it,
  validates snapshot/date alignment, and supplies SMA/RSI plots and date inspection;
  numerical/window conventions are versioned in INDICATORS.md.
- `app/import_prices.py` validates and imports the team snapshot per symbol;
  `daily_bars.source_values` retains auxiliary source fields. This is not a
  live-provider adapter or scheduled refresh service.

## Planned boundary

Browser → FastAPI → PostgreSQL / selected market-data provider.

Offline ML pipeline → validated, versioned artifact → backend inference.

Browser-to-FastAPI fixture and imported PostgreSQL paths are implemented, including snapshot import, accounts/sessions and the indicator API. Live incremental provider ingestion and ML connections do not exist yet. Training should not run inside an HTTP request. Begin with one frontend and one backend; add modules only when real features require them. Backend schemas should define stable contracts before frontend integration. Use separate tests for deterministic calculations, provider adapters, persistence, and HTTP behavior as each is introduced.

Python supports the future pandas/NumPy/scikit-learn workflow for analysis, training, and inference. SQLAlchemy/Alembic and psycopg are implemented persistence dependencies. Tailwind and React Router are unnecessary for the current single page.
