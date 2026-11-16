# Frontend/backend integration review

Prepared November 16, 2026 for Noah. Branch: `feature/frontend-redesign`.
Publication status: committed locally on `feature/frontend-redesign`; not pushed.
The initial integration commit is `bb4eeab`. A later documentation commit records
the publication blocker. No remote review branch or PR was created, and no merge
was performed. The original local branch and earlier commits are preserved.

Publishing was attempted after Gavin authorized it. Command-line Git failed with
`getaddrinfo() thread failed to start`; the GitHub connector rejected tree creation
with HTTP 403 `Resource not accessible by integration`. Its available permission
controls do not grant the repository write access needed for this operation.
From a normal terminal in this repository, publish the existing commits with:

```powershell
git push origin feature/frontend-redesign
```

Then run/check CI for that exact branch head. Publication and hosted CI must not
be reported as successful until their actual results are available.

## Completed integration scope

The historical stock-analysis slice now connects:

1. Ticker or company-name search in React to `GET /api/stocks?query=...`.
2. Selection of a returned stock to `GET /api/stocks/{symbol}/prices?range=...`.
3. FastAPI to the configured PostgreSQL repository (or explicit fixture mode).
4. Chronological response bars to the price/volume chart, keyboard date slider,
   and observations table.
5. Source, adjustment convention, latest observed date, and displayed date span
   from the API response to visible chart labels.

Search supports 40-character queries, up to 50 results, loading/no-match/error
states, a separate retry, and cancellation of superseded searches. A failed or
empty search leaves the current chart available. Select a search result to
change the chart; submitting a search alone does not switch symbols.

Range changes and price retries clear the old chart/selection, cancel obsolete
requests, and handle timeout, unavailable data, unsupported history, and empty
responses. Price ranges are latest trading sessions, not calendar durations.

The API adds `session_limit` and `has_earlier` in both storage modes. Database
queries fetch one extra row to detect earlier coverage without loading the full
series. The UI calls the capped `all` range **Max** and explains its 2,000-session
limit. It does not imply the whole Parquet history is being shown.

AAPL remains the only seeded symbol: 506 historical observations from
2015-02-17 through 2017-02-16. Company search is functional even though the demo
universe currently contains one stock. No live quotes are implied.

## Start the database-backed app

Use the existing ignored local configuration on Gavin's machine. For a fresh
checkout, follow [database setup](DATABASE.md) to create root/backend `.env`
files with matching local PostgreSQL settings; never copy credentials into Git.
Docker Desktop must be running. From the repository root:

```powershell
docker compose up -d --wait
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. Confirm
<http://127.0.0.1:8000/api/ready> reports `storage: database` before calling it a
database-backed walkthrough. `/api/health` alone does not verify storage.
Migration and fixture import are explicit; startup does not change the schema
or silently seed/fall back when database configuration is broken.

For a deliberate database-free walkthrough, set `STOCKSIGHT_DATABASE_URL` to an
empty string in the backend terminal before starting Uvicorn. Readiness then
reports fixture storage. Do not confuse this with PostgreSQL verification.

## Review walkthrough

1. On load, AAPL shows the latest 63 bundled sessions and historical source/date
   labels. Confirm the source link and adjustment text come from the response.
2. Search `apple`, choose **AAPL Apple Inc.**, and inspect the resulting chart.
   Repeat with a ticker containing spaces/lowercase; normalization is server-side.
3. Search `unknown`: no matches appear while the existing chart remains visible.
4. Switch 1M / 3M / 1Y / Max: expect 21 / 63 / 252 / 506 observations. Earlier
   coverage notices appear for shorter windows; Max fits this entire small seed.
5. Use the date slider with Home/End and open Price observations. Dates, closing
   prices, and volumes must agree with the API response.
6. Stop the API, search, and check the search error/retry without losing the
   chart. Restart it, retry search, and select the stock. Test a price retry by
   changing the range while the API is stopped.
7. For database persistence, restart the existing container without deleting its
   volume, restart the app, and confirm the same chart data is retrieved.

## Verification evidence from this change

- Frontend ESLint and production Vite build passed.
- Backend Ruff lint and formatting passed.
- Six focused backend tests passed using disposable SQLite storage: adapter
  search/history parity and unsupported-symbol error, bounded-history contract,
  2,001-row truncation/exact-2,000 boundary and source labels, invalid-import
  rollback, migration cycles, and foreign-key constraints. Repeat fixture
  imports also remain at 506 rows in the adapter-parity test.
- Playwright discovers all 11 browser tests, including new real-API company
  search/selection, independent search retry, response-derived provenance/cap
  labels, and superseded-search coverage.
- Full HTTP/browser execution could not complete in this agent session:
  Python's event loop stalled in local `socketpair` setup; Docker Desktop also
  terminated on startup in the initial attempt. On the follow-up, Docker was
  open but command-line access to its named pipe was denied. Interrupted blocked
  test runs are not passes. GitHub CI is the intended independent verification
  path once publication is possible; no hosted workflow was triggered in this session.
- PostgreSQL and the browser suite were verified in the prior increment (see
  DATABASE.md), but that evidence predates these changes. Re-run them for this
  exact diff on a normally running local environment before merge/demo signoff.

From backend, run the normal full checks:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
```

To include PostgreSQL integration cases, use `STOCKSIGHT_TEST_DATABASE_URL` for
an explicitly disposable database whose name ends in `_test`; those tests reset
their schema. Do not point that variable at the development database.

From frontend:

```powershell
npm run lint
npm run build
npm run test:e2e
```

Without `STOCKSIGHT_E2E_DATABASE_URL`, browser tests explicitly use fixture mode.
Set that variable to a migrated/seeded local database URL to test the PostgreSQL
path. The suite launches isolated servers on 5174/8101. No real API calls in the
browser should be replaced with mocks for the normal search/selection tests;
separate tests intercept responses only for controlled failure/metadata cases.

## Remaining project boundaries

The integration code in this review scope is implemented; Noah is reviewing it,
not being assigned an unfinished implementation list. Full runtime signoff
remains pending the environment-dependent checks above.

The 81 MB Parquet snapshot has not been imported. Its provider, adjustment
policy, and canonical-series conflict remain unresolved. The next independent
data increment is the read-only validation/dry-run work in
[DATASET_HANDOFF.md](DATASET_HANDOFF.md), followed by agreed ingestion rules.
Do not overwrite the current AAPL series to make the demo look broader.

Accounts/watchlists, technical indicators, provider refresh, ML prediction,
and prediction history are later roadmap work. They are not completed by this
historical search/chart integration. Team ownership assignments are unchanged.
