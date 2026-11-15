# Phase 1 historical stock analysis

Implemented scope: ticker search, daily closing-price/volume chart, 21/63/252-session and full-history views, keyboard date inspection, accessible observation table, loading/empty/error/retry states, and a real FastAPI request. Only AAPL is supported initially. No accounts, database, indicators, or predictions are claimed.

## Data

The committed fixture is the public Plotly datasets `finance-charts-apple.csv`, retrieved November 15, 2026 from https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv. The repository MIT license is preserved alongside it in `backend/app/fixtures/SOURCE_LICENSE`. Values are historical unadjusted OHLCV, not current quotes; splits and dividends are not normalized here. The unused source indicator/adjusted columns are not exposed by the API. Provider selection and broader data-rights/adjustment review remain M2 work. No network call is made at application runtime.

Ranges represent the latest 21, 63, or 252 available trading observations and end at the last fixture date, not today. `all` is bounded by the committed fixture. The source does not provide currency metadata; the AAPL fixture is displayed in USD. Session dates are dates rather than invented UTC instants.

## API contract

- GET /api/stocks?query=apple returns supported symbol/name matches; unknown searches return [].
- GET /api/stocks/AAPL/prices?range=3mo returns symbol, name, source/source_url, mode, adjustment, as_of, range and ascending bars (date/open/high/low/close/volume).
- Unsupported symbols return 404 with detail.code/detail.message. Invalid ranges return FastAPI's 422 validation response. Unify validation envelopes when the API expands.

## Run and verify

From backend, create a Python 3.12+ virtual environment and install requirements-dev.txt as in README. Start `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. In a second terminal, from frontend run `npm ci` and `npm run dev`. Open http://127.0.0.1:5173. Vite proxies /api to FastAPI; production routing is not provided by Vite's build.

Backend: `python -m pytest`, `python -m ruff check .`, `python -m ruff format --check .`. Frontend: `npm run lint` and `npm run build`.

Browser acceptance: AAPL renders dated historical observations; changing range changes the observation count while retaining the latest date; keyboard date slider changes inspected date/value; invalid ticker produces a useful error; AAPL recovers; the observations table works without reading the visual chart. Stop the API and confirm an error/retry state. Check desktop and narrow layouts.

Team handoff: Noah owns browser refinement; Gavin owns contract/API changes; Parth verifies fixture/data conventions and next provider; Vladislav owns repeatable setup and persistence preparation. M2 replaces the fixture adapter behind the API contract, not the frontend data flow. Phase 1 completion does not claim the full submitted MVP.

## Verification recorded November 15, 2026

- Backend: four pytest tests passed; Ruff lint and formatting passed.
- Frontend: ESLint and production build passed.
- Browser: initial AAPL chart rendered; 3M displayed 63 sessions, 1M displayed 21, both ending 2017-02-16; MSFT showed an unsupported-symbol error; searching AAPL recovered. Desktop screenshot inspected.
- Outstanding M1 gate work: commit automated browser coverage, verify the network-failure/retry path and narrow viewport, and repeat setup on a second teammate machine. This first working implementation is not a claim that every roadmap M1 acceptance check has passed.
