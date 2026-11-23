# Current API

Continuation context: [CURRENT_HANDOFF.md](CURRENT_HANDOFF.md). Public stock
contracts below are implemented; prediction/evaluation routes do not exist.

The moving-average/RSI backend contract is in [INDICATORS.md](INDICATORS.md):
`GET /api/stocks/{symbol}/indicators?range=3mo`. It returns dated SMA20 and Wilder
RSI14 values, null warm-up values and explicit calculation-window metadata.
The frontend consumes it through independent SMA20/RSI14 toggles and checks
price/indicator snapshot alignment.

Local base URL: `http://127.0.0.1:8000`.

Private endpoints accept an Auth0 bearer token or the first-party app session.
Session creation/restoration/logout, CSRF headers and lifetimes are documented in
[the account guide](ACCOUNTS.md#session-api). The frontend uses the app cookie so a
page refresh does not require another Auth0 prompt.

## GET /api/health

No authentication, parameters, database, or provider access. Returns HTTP 200 with `application/json`:

```json
{"status": "ok", "service": "stocksight-api"}
```

`status` is the literal `ok`. `service` uses `STOCKSIGHT_APP_NAME`, defaulting to `stocksight-api`. This is a process health check, not a database/provider readiness probe.

PowerShell: `Invoke-RestMethod http://127.0.0.1:8000/api/health`.

FastAPI supplies `/docs`, `/redoc`, and `/openapi.json`. Auth0-protected current-user and watchlist endpoints are documented in [the account API contract](ACCOUNTS.md#watchlist-api). Prediction and evaluation endpoints remain unimplemented. Stock endpoints are described below.

## Historical stock API

GET /api/stocks?query=apple lists supported symbol/name matches.
GET /api/stocks/AAPL/prices?range=3mo returns dated OHLCV bars and provenance.
Ranges are 1mo (21 stored sessions), 3mo (63), 1y (252) and all (up to 2,000).
Session dates are calendar dates. The response includes symbol, name, source,
source_url, mode, adjustment, as_of and ascending bars (date, open, high, low,
close, volume). The bundled AAPL fixture uses historical unadjusted Plotly OHLCV displayed
in USD. The [source license](../backend/app/fixtures/SOURCE_LICENSE) is tracked
with the fixture.
See [import policy](PRICES_IMPORT.md) for the separate team snapshot.

## Storage selection and readiness

A nonempty STOCKSIGHT_DATABASE_URL selects database reads with the same history response. Missing/empty URL explicitly selects fixture mode. GET /api/ready checks storage/schema (200 or sanitized 503); /api/health remains liveness only. Stock routes return 503 DATA_UNAVAILABLE if database reads fail, without fixture fallback. Search is capped at 50 and all-history at the latest 2,000 daily bars.


## Search and chart integration

Submitting the Analysis search form calls `GET /api/stocks?query=...` with a ticker or company
name. The response is an array of `{symbol, name}`
objects, capped at 50 matches, with an exact ticker match ranked first and other
matches ordered alphabetically. Select a result to request its price history;
searching alone preserves the currently displayed chart. Empty matches and
storage errors have separate visible states. The local autocomplete suggestions
are curated separately. A selected suggestion still loads history from the API.

History now includes two required response fields:

- `session_limit`: 21, 63, 252, or 2000 for the requested range.
- `has_earlier`: true if stored observations exist before the returned window.

Prices and indicators also return an opaque `snapshot_id`. It identifies a
single stored series revision independent of range. When making separate
requests, compare this value before overlaying indicators. The database reads
the revision and its bounded bars in the same statement. Writers must advance
the series revision in the same transaction as a price correction.

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
