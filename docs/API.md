# Current API

Local base URL: `http://127.0.0.1:8000`.

## GET /api/health

No authentication, parameters, database, or provider access. Returns HTTP 200 with `application/json`:

```json
{"status": "ok", "service": "stocksight-api"}
```

`status` is the literal `ok`. `service` uses `STOCKSIGHT_APP_NAME`, defaulting to `stocksight-api`. This is a process health check, not a database/provider readiness probe.

PowerShell: `Invoke-RestMethod http://127.0.0.1:8000/api/health`.

FastAPI supplies `/docs`, `/redoc`, and `/openapi.json`. There are no stock, user, watchlist, prediction, or evaluation endpoints. Define validation, pagination, error envelopes, authorization, and timestamp conventions alongside the first real feature.
