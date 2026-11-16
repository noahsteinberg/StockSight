# Frontend redesign — November 16, 2026

Gavin authorized the redesign and existing-indicator integration in this phase.
The React/Vite framework, Auth0 session context, private request wrapper, FastAPI
contracts and PostgreSQL schema remain unchanged. No dependencies were added.

## Reference review and chosen direction

- [HuskyScheduler](https://huskyscheduler.site/): inspected the rendered desktop
  application. A compact header, adjacent search/calendar panels, aligned toolbars,
  small consistent type and thin panel boundaries keep related tasks together.
  StockSight adapts the adjacent chart/watchlist workspace and grouped controls;
  it does not add docking or scheduler-specific menus.
- [Enigma](https://play-enigma.xyz/): inspected the rendered light appearance.
  Sparse navigation, monospaced headings, generous spacing and quiet outlined
  controls establish hierarchy with little ornament. StockSight keeps compact
  navigation and restraint, while using stronger text/control contrast and less
  introductory space to suit repeated stock research.
- Also researched [TradingView](https://www.tradingview.com/features/),
  [Koyfin](https://www.koyfin.com/data-coverage/stocks/), and
  [Stock Analysis](https://stockanalysis.com/stocks/aapl/).
  Stock Analysis is the strongest workflow reference: its stock identity and dated
  price lead into chart ranges, related data and watchlist actions. Its direct
  hierarchy suits students searching, inspecting and saving stocks. StockSight
  borrows that hierarchy rather than the broader trading tools or terminal
  density of the alternatives. No third-party layout/assets were copied.

## Implemented

- UConn-inspired navy (#000e2f), white surfaces and subtle cool-gray background;
  restrained blue actions, consistent borders, radii and spacing. Retained IBM
  Plex Sans/Mono typography already used by the project.
- Compact account/header navigation; chart/search workspace with adjacent private
  watchlist on desktop and stacked panels below 900px. Project details are under
  one native disclosure, instead of a large planned-feature list.
- Wider search, bounded scrollable results, result count and dismissal. Existing
  search errors/retry and chart preservation remain intact.
- Chart range controls grouped with the chart, date-aware price/volume inspection,
  open/high/low/volume summary and explicitly labeled displayed-period change.
- SMA20 overlay and Wilder RSI14 panel consume the existing indicator API.
  Toggles default off; values follow the inspected observation. Nulls create gaps
  and explicit insufficient-history feedback. No client recomputation or forecast.
- Independent indicator timeout/loading/retry and cancellation. Compare returned
  symbol, range, as_of, source, adjustment and every point date against prices
  before joining. Mismatch offers a combined price/indicator reload.
- Selected watchlist item is identified visually and with aria-current. Existing
  save/remove, ownership isolation, refresh restoration and logout are preserved.
- Shared loading/empty/success/error styling, sticky table headers, keyboard
  focus, skip link, reduced-motion behavior and readable SVG ticks. Range/stock
  changes reset the date inspection instead of retaining another view's index.

## Verification

- Frontend ESLint and Vite production build passed.
- All 19 chart/indicator Playwright tests passed against the real explicit fixture
  API: existing 11 chart cases plus eight new indicator cases. New cases cover
  toggles/range stability, API error retry, snapshot mismatch recovery, nulls/date
  inspection, stale requests, short history, timeout recovery and responsive layout.
- All nine account/session browser tests passed using the existing isolated
  SQLite account harness and signed test identities; official SDK signup/PKCE and
  invalid-callback cases passed. This is not a new real hosted Auth0 acceptance run.
- Screenshots visually inspected at desktop 1440px and mobile 390px, with additional
  320px overflow/viewport checks. Fixed clipped RSI upper-axis text during QA.
  Ignored artifacts: `.local-data/redesign-desktop.png`, `redesign-mobile.png`,
  and `redesign-small-mobile.png` (explicit fixture data, no account capture).
- Rendered normal application on port 5173 against existing imported PostgreSQL:
  AAPL SMA20/RSI14 loaded; searched/selected MSFT; switched 3M to 1Y and observed
  stable latest SMA20 529.64 and RSI14 48.44, dated 2026-11-12.
- No schema changes, imports, account modifications, push or merge. Automated
  redesign suites used isolated fixture/SQLite services, not a new PG test suite.

## Remaining boundaries

ML remains for Vlad under Gavin's current direction; team roadmap ownership tables
are unchanged. Provider refresh, adjustment/calendar validation, missing company
metadata, password-reset/revocation acceptance, hosted CI, second-machine setup
and production deployment remain outstanding. The full prediction MVP is not done.
The browser title/name may repeat a ticker when provider company metadata is absent;
no company names are invented. External Google Fonts are inherited from the earlier
UI; readable local fallbacks remain available.
