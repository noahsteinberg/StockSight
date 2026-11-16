# Current API

Local base URL: `http://127.0.0.1:8000`.

## GET /api/health

No authentication, parameters, database, or provider access. Returns HTTP 200 with `application/json`:

```json
{"status": "ok", "service": "stocksight-api"}
```

`status` is the literal `ok`. `service` uses `STOCKSIGHT_APP_NAME`, defaulting to `stocksight-api`. This is a process health check, not a database/provider readiness probe.

PowerShell: `Invoke-RestMethod http://127.0.0.1:8000/api/health`.

FastAPI supplies `/docs`, `/redoc`, and `/openapi.json`. There are no user, watchlist, prediction, or evaluation endpoints. Stock endpoints are described below. Define validation, pagination, error envelopes, authorization, and timestamp conventions alongside the first real feature.

## Phase 1 historical API

GET /api/stocks?query=apple lists supported symbol/name matches. GET /api/stocks/AAPL/prices?range=3mo returns dated OHLCV bars and provenance. Ranges: 1mo (21 sessions), 3mo (63), 1y (252), all. Unknown symbol: 404; invalid range: 422. All ranges end at the latest bundled historical observation. See [Phase 1](PHASE_1.md) for the contract and data conventions.

## Storage selection and readiness

A nonempty STOCKSIGHT_DATABASE_URL selects database reads with the same history response. Missing/empty URL explicitly selects fixture mode. GET /api/ready checks storage/schema (200 or sanitized 503); /api/health remains liveness only. Stock routes return 503 DATA_UNAVAILABLE if database reads fail, without fixture fallback. Search is capped at 50 and all-history at the latest 2,000 daily bars.


## Search/chart integration update (November 16, 2026)

The analysis form calls `GET /api/stocks?query=...` with a ticker or company
name. The response remains an alphabetically ordered array of `{symbol, name}`
objects, capped at 50 matches. Select a result to request its price history;
searching alone preserves the currently displayed chart. Empty matches and
storage errors have separate visible states.

History now includes two required response fields:

- `session_limit`: 21, 63, 252, or 2000 for the requested range.
- `has_earlier`: true if stored observations exist before the returned window.

The database reads at most `session_limit + 1` bars to detect the extra history,
then returns at most `session_limit` bars in chronological order. Fixture mode
has identical semantics. `all` remains the API range name for compatibility;
the browser labels it **Max**, because it is capped rather than unlimited.
`as_of` is the latest observed session, not the server clock. The browser shows
actual source/source_url/adjustment fields and the displayed date span.

Example coverage fields for `AAPL?range=3mo` on the bundled data:

```json
{"session_limit": 63, "has_earlier": true}
```

Unsupported or empty symbol history returns 404 with
`detail.code=UNSUPPORTED_SYMBOL`; invalid request parameters return 422;
unavailable configured storage returns sanitized 503 DATA_UNAVAILABLE. The UI
keeps search and history retries separate and cancels superseded requests.
