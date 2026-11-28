# Current API

## Historical pattern comparisons

`GET /api/stocks/{symbol}/patterns?horizon_sessions=21` returns descriptive
historical comparisons. Supported horizons are exactly 5 and 21 stored sessions;
default 21. The symbol is normalized to uppercase. Unknown symbols or those with
no history return 404 `UNSUPPORTED_SYMBOL`, invalid horizons return 422, and
storage failures return sanitized 503 `DATA_UNAVAILABLE` without fixture fallback.

The response includes `methodology=historical-price-patterns-v1`, symbol/name,
`as_of`, `snapshot_id`, source/source_url/adjustment, `horizon_sessions`,
`calculation_start`, `calculation_sessions` (at most 2500), `has_earlier`,
`eligible_candidates` and `excluded_event_windows`. The snapshot agrees with
price history for the same revision. Explicit fixture mode serves AAPL only.

Available responses have `reason=null`, `current_setup` (20-session change,
daily variability and price vs. 50-session average, all percent), 8–12 matches,
`matched_count`, `summary` (median/quartile ending changes and rose/fell/unchanged
counts), and `points` (per-step quartiles and median, including step zero).
Each match contains `date`, `end_date`, `setup`, `change_pct`, and `path` of
`horizon_sessions + 1` values, starting at zero.

Unavailable responses have reason `insufficient_history`, `insufficient_matches`
or `invalid_history`, null summary, zero matched_count and empty matches/points.
`current_setup` is null when a usable setup cannot be computed. No forecast,
probability or provider call is generated. See [the calculation and limitations](PATTERNS.md).

## Incremental daily-history extension

After migration 0006 and an explicit refresh, prices and indicators may return
mode daily_history and optional last_refreshed_at (null for original fixtures).
Existing modes and routes remain supported. This date describes the last stored
data change, not a live quote or the most recent no-op check. as_of remains the
latest stored session. Snapshot IDs advance atomically with data corrections;
unchanged refresh runs leave them stable. Public HTTP requests never ingest
provider data. See [daily refresh](DAILY_REFRESH.md).

Continuation context: [CURRENT_HANDOFF.md](CURRENT_HANDOFF.md). Public stock
contracts below are implemented. The research-signal route exists but always
answers "unavailable" (no approved model); prediction-history and evaluation
routes do not exist.

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

## Explore API

### Research ideas

`GET /api/research-ideas?query=&sector=&method=momentum` returns up to six
research candidates. Method is `momentum` or `variability`. Query is capped
at 40 characters and sector uses the same reviewed taxonomy as Explore.
`GET /api/me/research-ideas?query=&method=` requires the existing account
session/bearer and uses only that account's saved sectors. Empty saved sectors
yield an empty private list. Existing private cache/CSRF/ownership rules apply.

Response fields are `calculation_version: research-ideas-v1`, `method`,
`query`, `sectors`, `latest_session`, `matching_count`, `eligible_count`
and `items`. Each item contains `symbol`, `name`, `sector`, `metric_pct`,
`reason`, `as_of` and `series_revision`.

Both research-ideas routes accept `page` (1–1000, default 1) and return
`page` and `page_size: 6`. The complete filtered universe is ranked before
paging. Explore's stock list pages independently with five rows per page.

Eligibility requires 21 valid positive closes ending at the newest stored
universe session and no recorded split event in that window. Momentum is
`100 * (last / first - 1)`, descending. Variability is sample standard
deviation of the 20 percentage close changes, ascending. Ties sort by ticker.
Missing/stale histories are excluded and reflected in the coverage counts.
Invalid inputs return 422 and storage failures return sanitized 503 responses.

### Stock list

GET /api/explore?query=&sector=&sort=ticker&page=1&page_size=25 returns one public page of
supported stocks (those with a stored price series), ordered by symbol. A query
matches ticker, stored name or reviewed company name, case-insensitively, and an
exact ticker ranks first. `sector` is optional and must be one of the 11 GICS
sector names (for example `Information Technology`); it combines with `query`.
`sort=change_desc` and `sort=change_asc` sort all matches by daily close change
before pagination. Missing changes sort last; equal changes use ticker order.
Exact ticker promotion applies to the default `ticker` order.
`query` is at most 40 characters; `page` is 1–1000; `page_size` is 1–50 (default 25).
Invalid values (including an unknown sector) return 422, and storage failure
returns 503 DATA_UNAVAILABLE. A filter that matches nothing returns no items; it
is never broadened.
A page past the end returns an empty `items` array with the real totals.

Response: `query` (normalized to uppercase), `sector` (echoed or null), `page`,
`page_size`, `total_supported`, `total_matching`, `latest_session` (newest stored
session across all series) and `items[]`. Each item has `symbol`, `name`,
`exchange`, `sector`, `sub_industry`, `last_close`, `as_of`, `daily_change_pct`
and `series_revision`.

- `name`, `sector` and `sub_industry` come from the reviewed metadata file
  ([STOCK_METADATA.md](STOCK_METADATA.md)). Without a reviewed row, `name` falls
  back to the stored name unless it only repeats the ticker (the importer's
  placeholder), and `sector`/`sub_industry` are null. `exchange` is null when it
  is `UNKNOWN`. The UI shows "Name not yet available"/"Sector unknown" for nulls.
- `daily_change_pct` is `(latest close / previous stored close − 1) × 100`, or
  null with fewer than two stored sessions. It is price change only, not total
  return, and not a forecast.
- `series_revision` matches the `snapshot_id` that the stock's price history
  reports.

Each row reads only its two newest bars; no full histories, indicators or provider
requests run. Explicit fixture mode returns the single AAPL fixture.
`GET /api/stocks` (search, capped at 50) keeps its `{symbol, name}` shape; it now
also matches reviewed company names and returns them instead of placeholders.
Price/indicator histories and watchlist rows report the reviewed name the same way.

## Sectors and stock profiles

GET /api/sectors returns `total_supported`, `unknown` (supported stocks without a
reviewed sector), `sectors[]` (all 11 GICS sectors with `name` and `count` over
supported stocks) and `source` (`name`, `url` pinned to one revision,
`revision_date`, `retrieved`, `taxonomy`, `license`). Storage failure returns 503.

GET /api/stocks/{symbol}/profile returns `symbol`, `company_name`, `sector`,
`sub_industry` (each nullable) and the same `source`. A symbol without stored
history returns 404 UNSUPPORTED_SYMBOL. Explicit fixture mode serves AAPL only.
No provider calls or schema changes are involved.

## Compare API

GET /api/compare?symbols=AAPL,MSFT&range=1y compares 2–4 supported stocks on a
common basis. Range is 1mo, 3mo, 1y (default) or all, the same session counts as
price history. Symbols are case-insensitive and de-duplicated. Fewer than 2 or
more than 4 distinct symbols, or a malformed ticker, returns 422 INVALID_COMPARISON.
Symbols without stored history return 404 UNSUPPORTED_SYMBOL, naming each one in
`detail.symbols`. Storage failure returns 503. Explicit fixture mode stores only
AAPL, so it always returns that 404.

Numerical rules (pending Parth's review):
- **Shared cutoff:** the window ends at the newest session every selected stock
  has stored. `aligned_to_shared_cutoff` is true when their latest dates differ;
  each stock's own `as_of` and `last_close` are still reported.
- **Common dates only:** dates missing for any stock are excluded, never
  forward-filled. The window is the last N common dates (21/63/252/2000).
  `common_sessions` can be below `requested_sessions` when a history is shorter.
  With fewer than 2 common dates, every stock has `metric_status`
  `insufficient_overlap` and `dates` is empty.
- **Indexing:** `indexed[i] = close[i] / close[first common date] × 100`.
  `period_change_pct = last indexed − 100`. Closes exclude dividends, so this is
  price change, not total return.
- **Splits:** each `stock_splits` event inside the window is checked against the
  stored closes. A move within 25% of the split factor on that day means the
  stored prices are unadjusted there (`price_adjusted: false`). The stock's
  `metric_status` is then `split_unadjusted` and its `period_change_pct` is null.
  The team snapshot's recorded splits (e.g. NVDA 2021/2024, AAPL 2020) are
  continuous, i.e. already adjusted.

Response fields: `range`, `requested_sessions`, `common_sessions`, `start`, `end`,
`aligned_to_shared_cutoff`, `dates[]` and `stocks[]`. Each stock has `symbol`,
`name` (null for placeholders), `as_of`, `last_close`, `series_revision`,
`start_close`, `end_close`, `period_change_pct`, `metric_status`,
`split_events[]` (`date`, `ratio`, `price_adjusted`) and `indexed[]`, aligned
with `dates`.

## Research signal status

GET /api/stocks/{symbol}/signals?horizon_sessions=1 (issue #19 phase 5) returns
the schema in [FRONTEND_ML_INTEGRATION_SPEC.md §4](FRONTEND_ML_INTEGRATION_SPEC.md):
`schema_version`, `ticker`, `status`, `unavailable_reason`, `message`,
`horizon_sessions` and the signal fields `target_kind`, `as_of_session`,
`target_session`, `published_at`, `direction`, `raw_score`, `probability`,
`signal_strength`, `universe_percentile`, `risk_level`, `model_version`,
`data_snapshot` and `provenance`.

- No model is approved, so a supported stock always gets 200 with `status:
  "unavailable"`, `unavailable_reason: "model_not_approved"`, the message
  "No approved model signal is available." and every signal field null.
  Nothing is computed, generated or stored when the route is called.
- `horizon_sessions` must be 1 (the only horizon the research spec defines);
  any other value returns 422 and is never mapped to another horizon.
- A symbol without stored history returns 404 UNSUPPORTED_SYMBOL; storage
  failure returns 503 DATA_UNAVAILABLE. Fixture mode serves AAPL only.
- The response model rejects contradictions: an unavailable response can't carry
  any value (zero is a value, not "unavailable"), and an available one needs
  its target, dates, model/data versions and provenance. Available responses
  exist only as a test fixture until a model, artifact and persistence layer
  are separately approved.

The frontend adapter (signal-api.js) applies the same checks and shows nothing
for an inconsistent response.

## Private preferences and discovery

GET/PUT/DELETE /api/me/preferences and GET /api/me/discovery are private account
routes; their contract is in [the account guide](ACCOUNTS.md#watchlist-api).
Discovery reuses Explore pagination and sort options and adds a `match_reason`
per item.

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
