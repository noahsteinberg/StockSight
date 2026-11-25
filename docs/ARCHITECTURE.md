# Architecture

For proposed discovery/comparison/preferences views and their approval gates,
read [the frontend product handoff](FRONTEND_PRODUCT_HANDOFF.md). Explore
(increment 1), Compare (2) and reviewed metadata plus the TradingView panel (3)
are implemented on stacked branches; see CURRENT_HANDOFF.md for their delivery state.

## Incremental daily refresh

An offline Python command fetches and validates completed Yahoo daily sessions,
then commits each symbol's incremental updates, correction history, retention
changes and revision together. It reuses the same market tables and numerical
validation as snapshot import. No provider dependency is required by public API
requests. Migration 0006 adds backend-only refresh-run/bar-change tables plus a
series update timestamp. See [daily refresh](DAILY_REFRESH.md); production
scheduled execution remains pending. The additive migration, compatible API,
seven-stock pilot and full 494-stock refresh passed November 23. History is still
updated by the offline command, with no provider call in public APIs. A GitHub
Actions workflow now exposes that command through manual preview/update runs;
its schedule is gated pending manual Actions acceptance (see DAILY_REFRESH.md).

## Application views

| URL fragment | View | Behavior |
| --- | --- | --- |
| #/explore?q=app&sector=Energy&page=2 | Explore stocks | Public paginated list of supported stocks (25 per page) with search, GICS sector filter, reviewed name/sector, latest stored close/date, daily change, save star and compare toggle |
| #/analysis?symbol=AAPL | Stock analysis | Company/sector line, separate TradingView latest-quote panel (hidden during replay), price and volume, SMA20/RSI14, inspection, historical replay, CSV, watchlist chips and Add to comparison |
| #/compare?symbols=AAPL,MSFT&range=1y | Compare stocks | 2–4 stocks indexed to 100 on common dates, keyboard/pointer readout, summary table and disclosures (shared cutoff, short overlap, splits, price-only change) |
| #/dashboard (#/watchlist) | Watchlist | Private watchlist, filtering, saved dates, open/remove and account states |
| #/predictions?symbol=AAPL | Predictions | Selected stock, unavailable generation/history and return to Analysis |
| #/performance | Model performance | Unavailable evaluation |
| #/methodology | Data & methodology | Source, coverage, adjustment, indicator and project information |

Root / opens Explore, and so does the brand. The sidebar lists Explore, Analysis,
Compare, Watchlist and Methodology. The Compare link carries the current selection.
Stocks are picked with the + button on Explore and Watchlist rows, or with Add
to comparison on Analysis. The tray (up to 4) is kept in this tab's
sessionStorage; it holds public tickers only, never private data. Predictions and Model performance are no longer in the
sidebar; they stay reachable from Analysis ("Predictions for X"), the Watchlist
page and each other. Legacy #analysis, #watchlist and #project resolve to their
corresponding views. Unknown pages provide recovery to Analysis. Browser
back/forward and refresh work via hash navigation. Page changes update the title,
active item and main-content focus. On Explore, the search text and page number
live in the URL: a search becomes a history step after a 300 ms typing pause, and
changing it does not move focus away from the search field. The skip link focuses
the current page. Navigation retains the selected stock, and a successful Auth0
callback returns to the Watchlist (#/dashboard).

## Implementation

- App.jsx owns the selected stock, account-scoped watchlist and navigation.
  use-page-route.js subscribes to hash changes. The desktop sidebar expands on
  hover/focus, and the mobile hamburger exposes the same routes.
- Explore.jsx renders the stock list. explore-api.js validates each
  GET /api/explore response before rendering, and use-explore.js cancels
  superseded requests, so a slow older search cannot replace newer rows.
  app/explore.py reads only the newest two stored closes per series.
- Compare.jsx owns the comparison URL state. CompareChart.jsx draws the native
  SVG lines; each line has its own colour and dash pattern, so the legend
  doesn't rely on colour alone. compare-api.js validates responses, and
  use-compare.js cancels superseded requests. use-compare-selection.js and
  CompareTray.jsx manage the selection. app/compare.py reads at most
  N + 40 bars per stock, up to the shared cutoff.
- app/stock_metadata.py loads the reviewed company/sector file once and
  supplies names to search, histories, Explore, Compare and the watchlist; see
  [STOCK_METADATA.md](STOCK_METADATA.md). use-stock-profile.js reads
  /api/stocks/{symbol}/profile for the Analysis context line.
- MarketQuote.jsx (Parth's PR #16) embeds TradingView's Single Ticker widget on
  Analysis only; see [TRADINGVIEW.md](TRADINGVIEW.md). HistoricalChart reports
  replay through onReplayChange so the quote is hidden beside past dates.
- Analysis.jsx integrates stock search, the native SVG PricePlot.jsx chart and
  the observations table. Local autocomplete is supplied by stock-suggestions.js.
  Price and indicator requests have independent retry states. The client
  compares snapshot IDs and dates before combining the responses.
- MarketQuote.jsx embeds TradingView’s free Single Ticker widget above Analysis.
  Its exchange-qualified symbol follows the selected stock using a static listing
  map. The widget owns its prices and freshness indicators; they do not enter PostgreSQL,
  chart snapshots, indicators, exports or model inputs. See [widget setup](TRADINGVIEW.md).
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
