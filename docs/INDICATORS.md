# Indicator API — backend phase

`GET /api/stocks/{symbol}/indicators?range=3mo` is public and reads the same
canonical stored daily series as `/prices`. It performs no provider downloads,
imports, training or database writes. Fixture mode remains explicit. No schema
migration is needed. The later frontend redesign now consumes this endpoint;
see [FRONTEND_REDESIGN.md](FRONTEND_REDESIGN.md).

## Contract

Ranges match prices: `1mo` = 21 observations, `3mo` = 63 (default), `1y` = 252,
`all` = at most 2,000. Symbols are trimmed and uppercased. Unsupported/empty
history returns 404 `UNSUPPORTED_SYMBOL`, invalid range returns 422, and
configured storage failures return sanitized 503 `DATA_UNAVAILABLE` without
fixture fallback.

The response includes `symbol`, `name`, `source`, `source_url`, `mode`,
`adjustment`, `as_of`, `range`, `session_limit`, `has_earlier` and chronological
`points`. Each point has exactly `{date, sma_20, rsi_14}`; dates align one-to-one
with the same symbol/range price bars for an unchanged stored snapshot. Insufficient
history is JSON `null`, never zero or a missing date. `as_of` is the latest
stored observation, not today's date. Separate requests can observe different
snapshots if an import runs between them; clients should compare dates/as_of.

Calculation metadata:

| Field | Meaning |
| --- | --- |
| `methodology` | `close-sma20-wilder-rsi14-v1` |
| `calculation_limit` | 10000 stored observations per symbol |
| `calculation_sessions` | Number actually used before display trimming |
| `calculation_start` | First observation used to initialize calculations |
| `calculation_has_earlier` | Older stored observations were excluded by the calculation cap |
| `has_earlier` | Stored observations precede the displayed window |

## Numerical conventions

- Input is stored `close`, including its reported adjustment convention. Do not
  describe these as adjusted indicators when the underlying source is unverified.
- SMA20 is the arithmetic mean of the current close and 19 preceding closes.
  First valid value is at observation 20; the previous 19 are null. Its unit is
  the same price unit as the source.
- RSI14 uses 14 close-to-close changes (15 closes) for its first value. Average
  gain/loss are the arithmetic means of the first 14 positive/negative change
  magnitudes, counting zero changes as zero. Thereafter each average updates as
  `(13 * previous_average + current_magnitude) / 14` (Wilder smoothing).
- RSI is `100 * average_gain / (average_gain + average_loss)`, in [0,100].
  Gain-only input gives 100, loss-only gives 0. When both averages are exactly
  zero, StockSight deliberately returns 50; libraries differ on this convention.
  There is no intermediate rounding or epsilon-based zero threshold.
- Periods count stored observations, not calendar days. Weekends and missing
  sessions are not filled or interpolated; consecutive stored closes define the
  next change even across a gap. This does not certify that ingestion has no gaps.
- Calculations use only current and preceding observations. No future bars enter
  a value. Float64 arithmetic is used; presentation rounding belongs to clients.
- No EMA, standard deviation, MACD, Bollinger bands, predictions or Buy/Sell
  scores are implemented by this endpoint.

Wilder's recursive gain/loss update can also be inspected in the primary
[TA-Lib RSI implementation](https://github.com/TA-Lib/ta-lib/blob/main/src/ta_func/ta_RSI.c).
StockSight's flat-price rule and fixed history cap are explicit local choices;
the contract does not promise parity with every library or its defaults.

## History and stability

Read at most 10,001 newest rows from one canonical series; use the newest 10,000
and the extra row only to detect truncation. Calculate both indicators over this
fixed window, then trim to the requested display range. Changing range against
an unchanged snapshot therefore preserves every overlapping value, including
the first displayed value. The API never scans the entire stock universe.

If more than 10,000 observations exist, Wilder RSI is initialized at the reported
window start rather than at the original series inception. As new observations
arrive, that anchor can advance; historical values can change slightly. Source
corrections or replacement imports can also change results. Consumers must retain
the methodology and calculation start when reproducing outputs. A future ML
pipeline must share these conventions or version its alternative explicitly.

## Verification and next phase

`backend/tests/test_indicators.py` covers hand-derived mixed RSI seed/recursive
values, exact SMA values, rising/falling/flat/short input, gaps, no future leakage,
date alignment, all display ranges, the calculation cap, restarts, explicit
fixture/database equivalence, empty history and sanitized failures. Database tests
run on SQLite and opt-in disposable PostgreSQL using the existing test fixture.

The later frontend phase implements SMA/RSI rendering, toggles, units,
insufficient-history states and browser acceptance, including real fixture API
and imported PostgreSQL browser checks. See FRONTEND_REDESIGN.md for scope.
ML, persisted forecasts/outcomes and model
evaluation remain outstanding MVP work. Team ownership in ROADMAP.md is unchanged.

Local verification on November 16, 2026: the full backend suite passed with 95
tests and one expected SQLite invocation skipped for a PostgreSQL-only concurrency
check; its PostgreSQL invocation passed. Ruff lint and format checks passed.
Real HTTP requests to the normal API confirmed AAPL and MSFT on the imported
snapshot, with all four ranges aligned to prices and overlapping values stable.
Each symbol used 6,757 calculation observations; Max returned 2,000 points.
Read-only before/after counts remained 2,947,701 bars, 494 series and two watchlist
entries. No frontend files or schema changed. Screen capture was not used.
Sanitized local evidence is ignored under `.local-data/indicator-verification.json`
and `.local-data/indicator-live-http.json`; hosted CI was not run in this phase.
