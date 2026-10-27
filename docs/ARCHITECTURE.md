# Architecture

## Implemented

- `frontend/src/App.jsx`: one informational React page with anchor navigation. Plain CSS handles layout and responsive styling; there is no application router or API client yet.
- `backend/app/main.py`: application factory and FastAPI instance. Routes mount under `/api`.
- `backend/app/api/health.py`: Pydantic response schema and process health route.
- `backend/app/config.py`: typed environment settings; optional `backend/.env` loading. Tests inject settings for a deterministic service name.
- Tooling runs independently for frontend and backend. No external service is required.

## Planned boundary

Browser → FastAPI → PostgreSQL / selected market-data provider.

Offline ML pipeline → validated, versioned artifact → backend inference.

These connections do not exist yet. Training should not run inside an HTTP request. Begin with one frontend and one backend; add modules only when real features require them. Backend schemas should define stable contracts before frontend integration. Use separate tests for deterministic calculations, provider adapters, persistence, and HTTP behavior as each is introduced.

Python supports the future pandas/NumPy/scikit-learn workflow for analysis, training, and inference. SQLAlchemy/Alembic are likely future choices, not current dependencies. Tailwind and React Router are unnecessary for the current single page.
