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

## Manual UI verification retry November 15, 2026

Verified in a separate rendered browser tab: all range counts, keyboard first-date inspection, normalized search, unsupported-symbol recovery, observations table, API-down error and successful Retry after restart. A 390px viewport fit the controls but exposed very small chart tick labels. Whitespace-only search was reproduced as silent. See [review and evidence](reviews/PHASE_1_ADVERSARIAL_REVIEW.md). Automated browser tests and second-machine setup remain outstanding; no claim of isolated headless verification is made.

## Phase 1 hardening implementation November 15, 2026

Tracked by [GitHub issue #2](https://github.com/noahsteinberg/StockSight/issues/2). Whitespace-only ticker submission now produces accessible validation feedback. Chart dimensions track their container through ResizeObserver, keeping 12px tick labels readable on narrow screens. The date slider exposes the selected date and price as its accessible value.

Seven Playwright regression tests now cover the real fixture-backed API flow, all range counts, keyboard inspection/table access, blank/unsupported/normalized ticker behavior, controlled API failure and Retry, empty responses, a virtual-clock timeout with recovery, canceled older range requests, and 390px chart label sizing/overflow. Tests start their own frontend/API on ports 5174/8101 and do not reuse the manual demo servers. Failure/empty/timeout scenarios use intercepted responses; the primary chart path and retry recovery use the actual FastAPI service.

After installing backend/requirements-dev.txt in backend/.venv and running npm ci in frontend:

    cd frontend
    npx playwright install chromium
    npm run test:e2e

On Linux CI, use `npx playwright install --with-deps chromium`. If using another existing Python environment, set STOCKSIGHT_PYTHON to that interpreter's absolute path; do not commit machine-specific paths. The default is backend/.venv/Scripts/python.exe on Windows or backend/.venv/bin/python on Unix. STOCKSIGHT_API_TARGET configures only Vite's server-side development proxy and is set by the test runner for its isolated API.

The GitHub Actions browser job installs both runtimes and runs the suite; failures retain trace artifacts. Local execution passed all seven tests, frontend lint/build, and the development dependency audit after compatible updates to ESLint 10.15.0 and minimatch 11.0.8. These are point-in-time results, not a claim that hosted CI has run or a teammate has verified another machine. A clean local setup is being verified separately before handoff.

Clean local setup verification (November 15, 2026): cloned commit 6a3edce into stocksight-phase1-clean, created a new backend/.venv, installed requirements-dev.txt and npm ci, then ran backend pytest (4 passed), Ruff lint/format, frontend lint/build, and all 7 Chromium tests using the default interpreter path. All passed. This is a fresh checkout on the same Windows machine, not verification by another teammate or of Linux hosted CI. GitHub issue: #2. Gavin and Noah continue to jointly own frontend/backend integration.
