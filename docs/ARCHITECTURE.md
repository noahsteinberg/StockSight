# Architecture

## Implemented

- `frontend/src/App.jsx`: React page with an Analysis workspace and anchor navigation. Analysis.jsx fetches historical bars through the Vite API proxy and renders SVG prices/volume with an accessible table.
- `backend/app/main.py`: application factory and FastAPI instance. Routes mount under `/api`.
- `backend/app/api/health.py`: Pydantic response schema and process health route.
- `backend/app/config.py`: typed environment settings; optional `backend/.env` loading. Tests inject settings for a deterministic service name.
- app/api/stocks.py selects explicit fixture or SQLAlchemy repository reads; database mode requires PostgreSQL. app/seed.py imports the historical fixture independently, and Alembic owns schema changes.
- Vite proxies /api to localhost:8000 during development. Production hosting must supply equivalent routing.

## Planned boundary

Browser → FastAPI → PostgreSQL / selected market-data provider.

Offline ML pipeline → validated, versioned artifact → backend inference.

The browser-to-FastAPI historical-fixture path is implemented; PostgreSQL reads and migrations are implemented; provider ingestion and ML connections do not exist yet. Training should not run inside an HTTP request. Begin with one frontend and one backend; add modules only when real features require them. Backend schemas should define stable contracts before frontend integration. Use separate tests for deterministic calculations, provider adapters, persistence, and HTTP behavior as each is introduced.

Python supports the future pandas/NumPy/scikit-learn workflow for analysis, training, and inference. SQLAlchemy/Alembic and psycopg are implemented persistence dependencies. Tailwind and React Router are unnecessary for the current single page.
