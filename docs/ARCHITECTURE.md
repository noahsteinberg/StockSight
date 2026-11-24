# Architecture

## Incremental daily refresh

An offline Python command fetches and validates completed Yahoo daily sessions,
then commits each symbol's incremental updates, correction history, retention
changes and revision together. It reuses the same market tables and numerical
validation as snapshot import. No provider dependency is required by public API
requests. Migration 0006 adds backend-only refresh-run/bar-change tables plus a
series update timestamp. See [daily refresh](DAILY_REFRESH.md); production
activation and scheduled execution remain pending.

## Application views

| URL fragment | View | Behavior |
| --- | --- | --- |
| #/dashboard | My dashboard | Private watchlist, filtering, saved dates, open/remove and account states |
| #/analysis?symbol=AAPL | Stock analysis | Stock lookup, price and volume, SMA20/RSI14, inspection, historical replay, CSV and watchlist chips |
| #/predictions?symbol=AAPL | Predictions | Selected stock, unavailable generation/history and return to Analysis |
| #/performance | Model performance | Unavailable evaluation |
| #/methodology | Data & methodology | Source, coverage, adjustment, indicator and project information |

Root / opens Analysis for compatibility. The brand opens Dashboard. Legacy
#analysis, #watchlist and #project resolve to their corresponding views.
Unknown pages provide recovery to Analysis. Browser back/forward and refresh
work via hash navigation. Page changes update the title, active item and
main-content focus. The skip link focuses the current page. Navigation retains
the selected stock, and a successful Auth0 callback returns to Dashboard.

## Implementation

- App.jsx owns the selected stock, account-scoped watchlist and navigation.
  use-page-route.js subscribes to hash changes. The desktop sidebar expands on
  hover/focus, and the mobile hamburger exposes the same routes.
- Analysis.jsx integrates stock search, the native SVG PricePlot.jsx chart and
  the observations table. Local autocomplete is supplied by stock-suggestions.js.
  Price and indicator requests have independent retry states. The client
  compares snapshot IDs and dates before combining the responses.
- FastAPI mounts public and private API routes under /api. app/config.py reads
  typed settings. app/api/stocks.py selects fixture or PostgreSQL storage.
  app/import_prices.py validates and imports histories per symbol. Alembic owns
  schema changes, and daily_bars.source_values retains source auxiliary fields.
- AuthProvider.jsx uses Auth0.js for embedded password login and the React SDK
  for Google and hosted PKCE. Backend token checks and opaque sessions gate
  all private watchlist calls. use-watchlist.js keeps results owner-scoped,
  while Watchlist.jsx serves the Dashboard and the Analysis chip row.
- Vite proxies /api to localhost:8000. Production uses equivalent same-origin
  routing through Vercel. See [the account guide](ACCOUNTS.md) and [API](API.md).

## Planned boundary

Browser → FastAPI → PostgreSQL / selected market-data provider.

Offline ML pipeline → validated, versioned artifact → backend inference.

Browser-to-FastAPI fixture and imported PostgreSQL paths are implemented, including snapshot import, accounts/sessions and the indicator API. The separate incremental updater is implemented and locally verified; hosted activation and scheduling remain pending. ML serving is not implemented. Training and provider downloads do not run inside public chart requests. Keep one frontend and one backend and use the existing bounded API contracts.
