# Frontend/backend acceptance guide

Updated November 16, 2026. The authoritative continuation summary is
[CURRENT_HANDOFF.md](CURRENT_HANDOFF.md); start with [AGENTS.md](../AGENTS.md).
The older frontend-redesign branch review predates imported data, accounts/app
sessions and the indicator backend. Do not use that snapshot as current status.
This documentation task does not publish a branch or demonstrate hosted CI.

## Working integration

Search → select stock → bounded historical prices/volume is implemented, including
request cancellation, separate search/history retries, provenance/date labels,
keyboard inspection and an accessible table. Auth0 signup/login/logout, refresh
restoration and private persistent watchlists are integrated. Saved stocks reopen
the shared Analysis view. Indicator API is implemented; its frontend is not.
The current design stays in place. Redesign is a separate deferred phase.

## Walkthrough against the actual API

Start using [LOCAL_START.md](LOCAL_START.md). Check `/api/ready` for the intended
storage mode before calling the walkthrough PostgreSQL-backed. Fixture mode is
AAPL only (506 bars ending 2017-02-16); imported mode has 494 series with differing
coverage and source-derived labels. Some names remain tickers.

1. Search a supported ticker or company name and select a result. Search alone
   must leave the existing chart intact; unknown queries show no matches.
2. Change 1M / 3M / 1Y / Max and compare displayed dates and values to `/prices`.
   Limits are 21 / 63 / 252 / 2000, bounded by actual stored history. Preserve the
   earlier-history notice; Max does not mean the entire imported file.
3. Use the keyboard date slider and observations table. Inspect the API-provided
   source, adjustment label and historical as_of; never imply live quotes.
4. Exercise controlled unavailable/timeout/retry states and superseded requests.
   Do not restart/import repeatedly if the runner itself denies network access.
5. With configured Auth0, save a stock, refresh, reopen it from the watchlist,
   remove it and verify persistence. Keep the user's original data intact after
   any acceptance scenario. Users enter credentials themselves.
6. Verify logout, expiry and two-account isolation using disposable automated
   identities or user-directed hosted sign-in; never request passwords. Existing
   real two-account checks are already recorded in SESSION_HANDOFF.md.

## Next assigned increment: indicator UI

Consume `/api/stocks/{symbol}/indicators?range=...`; read INDICATORS.md first.
Add SMA20/RSI14 toggles and plots to the existing view with units, period labels,
null warm-up handling and accessible values. Match dates and symbol/range before
combining responses, cancel obsolete requests and keep independent retry states.
Preserve chart/watchlist/session functionality and test mobile/keyboard use.
Do not bundle redesign or display unavailable ML as working predictions.

## Evidence and checks

The indicator backend phase passed 95 tests with one expected SQLite invocation
skipped for a PostgreSQL-only test; its PG invocation passed. Ruff passed. Live
HTTP checks against imported AAPL/MSFT confirmed all ranges and indicator/date
alignment. Prior session work passed 11 chart and 9 account browser tests against
disposable PostgreSQL plus frontend lint/build. Those browser results predate the
indicator backend change; no indicator UI exists to validate yet.

Run relevant checks using CURRENT_HANDOFF.md. A test-only Auth0 harness does not
prove hosted credential exchange. No hosted CI or second-machine acceptance is
claimed. Historical reviews in docs/reviews retain the limitations at their dates;
current handoffs supersede resolved import/session/runtime blockers.
