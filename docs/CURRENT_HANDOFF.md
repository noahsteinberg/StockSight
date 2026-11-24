# StockSight current handoff

Update this file when implementation, delivery state or acceptance changes.
Use Git history for earlier checkpoints and the linked guides for setup and
contracts.

## November 23 market-price widget

- Parth approved a free TradingView widget after Alpaca's automated support reply
  did not grant permission to publicly display/cache Basic/Paper market data.
  Alpaca remains private testing only; no Alpaca data was written to Supabase.
- Analysis now includes a separate latest-market-price panel with TradingView
  attribution and a delay notice. The selected ticker controls its listing.
  The static listing map covers all 494 imported tickers, including share classes;
  a mapped listing does not guarantee the vendor permits that widget's display.
- The historical database still ends November 12, 2026. The widget supplies no
  raw API data for storage, indicators, watchlists, CSV or models. Incremental
  refresh remains unfinished. See [integration notes](TRADINGVIEW.md).
- This change is on `feature/tradingview-prices`, based on current main `afe8051`.
  It is independent of migration PR #15, which was open/unmerged when work began.
  No public deployment or merge has been performed by this task.
- Verification: frontend lint/build and backend Ruff lint/format pass; **95 backend
  tests passed, 2 PostgreSQL cases skipped** on this main-based branch. The four
  new widget browser tests use a mocked provider. The local Playwright run was
  blocked before tests could execute: its bundled Chromium is unavailable for
  macOS 13, and the installed Chrome launch exited with SIGABRT. CI must run the
  browser suite; do not count these launch failures as application assertions.
- Separate real-browser checks loaded TradingView prices for AAPL and MSFT,
  switched stocks, and confirmed a 320px page with no horizontal overflow. The
  compact Single Ticker widget replaced Symbol Info after that larger widget
  clipped its content on narrow screens. Historical AAPL/MSFT reads used the
  existing hosted snapshot through November 12; no data was imported or changed.

## Frontend release

- Analysis has a full-width chart, a horizontal row of saved tickers, and a star
  beside the stock title. Watchlist chips use the latest two stored closes.
  The Dashboard retains the filterable watchlist table.
- Search has an abortable local suggestion provider with a 200 ms debounce,
  prefix and typo matching, up to eight options, and keyboard navigation.
  The explicit Search action still uses the stock API.
- Desktop navigation expands on hover and focus. At 740 px or below the
  hamburger opens the menu. The active highlight uses 300 ms edge transitions
  with a 30 ms trailing delay and switches instantly under reduced motion.
- Hover previews a session and click/tap pins it. Keyboard inspection remains
  available. Historical replay limits the displayed data and CSV to the visible
  prefix while keeping the indicator calculation anchored to the API snapshot.
- The last local preview used the explicit AAPL fixture on port 5173. The tested
  widths were 1440 px and 320 px. The combined frontend and signup changes
  passed lint, build, 40 public browser cases and 24 isolated account cases.
  The watchlist increment previously passed 95 backend tests, with two
  PostgreSQL-only cases skipped.
- Signup attempts to sign the user in immediately after account creation.
  If the provider blocks that step, the account stays created and the page
  offers regular sign-in and the hosted Auth0 fallback.

## Last observed hosted state

- [Production](https://stocksight-rose.vercel.app) served main at `9672b12`
  during the last release check. Read-only smoke passed for database readiness,
  public prices and indicators with matching snapshot IDs, and private-route
  protection. Supabase has the approved 506-bar AAPL sample ending 2017-02-16.
  Local PostgreSQL holds the separate 494-symbol team snapshot.
- The production bundle and dedicated cross-origin verifier were checked. The
  login form offers **Trouble signing in?** for hosted Auth0 password login with
  PKCE if a browser blocks cross-site cookies or an interactive challenge is
  needed. The exact tenant verification URL and complete production account
  flow still need live confirmation. Keep user-entered credentials private.
- Earlier development-tenant checks verified refresh, logout and isolation for
  two real accounts. The user confirmed receipt of a recovery email. A full
  password change and a second-machine setup remain unverified.
- To close release acceptance, follow [the account guide](ACCOUNTS.md#verification)
  and verify current hosted Actions status separately. Earlier Actions billing
  errors were dated evidence. See [deployment checks](VERCEL.md#acceptance).

## Data and predictions

- The local team import is complete. See [import provenance](PRICES_IMPORT.md)
  for the validated source hash, quarantines and known coverage limits. Leave
  the existing dataset in place during routine startup. Accurate company and
  exchange metadata still need a verified source.
- Predictions and Model performance are visible unavailable views. Offline
  research produced no approved serving model. Noah paused further research.
  The [ML research guide](../ml/README.md) records frozen evidence and protected
  evaluation limits. Follow [team ownership and release gates](ROADMAP.md).
- If the team resumes product integration, start with the typed unavailable
  AAPL signal contract in the [frontend and ML spec](FRONTEND_ML_INTEGRATION_SPEC.md).
  Confirm hosted data coverage and adjustment policy before adding any refresh.
  Persistence, inference and evaluation are later increments.

## Working references

- [Start locally and run verification](LOCAL_START.md)
- [App navigation and architecture](ARCHITECTURE.md)
- [API](API.md) and [indicator conventions](INDICATORS.md)
- [Accounts and sessions](ACCOUNTS.md)
- [Deployment](VERCEL.md) and [Supabase](SUPABASE.md)
