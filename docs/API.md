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
