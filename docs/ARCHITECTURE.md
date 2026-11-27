# Architecture

For the combined release, human approval and next increments, read the
[release handoff](NEXT_RELEASE_AND_ML_HANDOFF.md).

## Incremental daily refresh

An offline Python command fetches and validates completed Yahoo daily sessions,
then commits each symbol's incremental updates, correction history, retention
changes and revision together. It reuses the same market tables and numerical
validation as snapshot import. No provider dependency is required by public API
requests. Migration 0006 adds backend-only refresh-run/bar-change tables plus a
series update timestamp. The compatible API, seven-stock pilot and full
494-stock refresh passed November 23. The active GitHub Actions workflow
invokes the same offline command on a schedule and supports manual preview and
update runs. See [daily refresh](DAILY_REFRESH.md).

## Application views

| URL fragment | View | Behavior |
| --- | --- | --- |
| #/explore?sector=Energy&sort=change_desc&page=2 | Explore stocks | Public paginated list of supported stocks (10 per page) with search, GICS sector filter, ticker or daily-change sorting, latest stored close/date, save star and compare toggle |
| #/analysis?symbol=AAPL | Stock analysis | Company/sector line, separate TradingView latest-quote panel (hidden during replay), price and volume, SMA20/RSI14, inspection, historical replay, CSV, watchlist chips and Add to comparison |
| #/compare?symbols=AAPL,MSFT&range=1y | Compare stocks | 2–4 stocks indexed to 100 on common dates, keyboard/pointer readout, summary table and disclosures (shared cutoff, short overlap, splits, price-only change) |
| #/dashboard (#/watchlist) | Dashboard | Private watchlist with stored closes, session dates and daily change, filtering, open/remove, compare toggle, optional preferences invitation and account states |
| #/preferences | Research preferences | Optional private form with purpose, sectors, horizon and default chart window, save/reset and guest sign-in prompt |
| #/explore?mine=1 | Explore: Use my preferences | Private list of stocks in the account's saved sectors with a match reason per row; sector filter disabled; no URL carries the sectors or any user ID |
| #/predictions?symbol=AAPL&horizon=5 | Predictions | Stock picker, full historical-pattern graph/examples for 5 or 21 stored sessions, and separate expandable ML availability/history |
| #/performance | Model performance | Unavailable evaluation |
| #/methodology | Data & methodology | Source, coverage, adjustment, indicator and project information |
| #/settings | Settings | Browser-local SMA 20 and RSI 14 defaults, account details, research preferences link, recovery and sign-out |

The root and StockSight logo open Dashboard. The sidebar lists Dashboard,
Explore, Analysis, Compare and Methodology, with Settings at the bottom.
Dashboard links to Explore. The Compare link carries the current selection.
Stocks are picked with the + button on Explore and Watchlist rows, or with Add
to comparison on Analysis. The tray (up to 4) is kept in this tab's
sessionStorage; it holds public tickers only. The selected stock's Predictions
view opens from "Research signal for X" in Analysis. Model performance opens
from Predictions and Methodology. Legacy #analysis, #watchlist and #project resolve to their
corresponding views. Unknown pages provide recovery to Analysis. Browser
back/forward and refresh work via hash navigation. Page changes update the title,
active item and main-content focus. Explore keeps search, sector, sort and page
in the URL. A search becomes a history step after a 300 ms typing pause, and
changing it does not move focus away from the search field. The skip link focuses
the current page. Navigation retains the selected stock, and a successful Auth0
callback returns to Dashboard (#/dashboard).

## Implementation

- Analysis links its 5/21-session choices to Predictions, preserving the stock
  and horizon in the URL. Predictions.jsx hosts PatternExplorer.jsx, loads an
  independent recent-price snapshot, and provides a supported-stock picker.
  The Predictions sidebar entry preserves stock context. ML status remains
  separate in an expandable section. pattern-api.js validates paths and summaries; app/patterns.py
  retrieves at most 2,500 bars plus a retention sentinel in one SELECT and
  computes descriptive setup matches. Snapshot mismatch hides results; replay
  hides Analysis's links. No model, provider request, persistence or schema change is
  involved. See [Historical Pattern Explorer](PATTERNS.md).

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
- use-preferences.js keeps the signed-in account's preferences (owner-keyed,
  no browser storage) for Preferences.jsx, the Explore "Use my preferences"
  list and the default chart range used by Analysis and Compare until a range
  is picked there. app/api/preferences.py owns the private routes and the
  user_preferences table (migration 0007).
- signal-api.js validates GET /api/stocks/{symbol}/signals; use-signal.js keys
  the request to the symbol. SignalPanel.jsx renders the status under the
  Analysis chart and on Predictions, and lists per-stock status on Compare,
  separate from price change. app/signals.py builds the typed response.
- Analysis.jsx integrates stock search, the native SVG PricePlot.jsx chart and
  the observations table. Local autocomplete is supplied by stock-suggestions.js.
  Price and indicator requests have independent retry states. The client
  compares snapshot IDs and dates before combining the responses.
- Settings initializes the indicator controls when Analysis opens. Changes to
  the controls on the chart apply to the current Analysis view. The saved
  defaults contain only two booleans and are shared by users of that browser.
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
