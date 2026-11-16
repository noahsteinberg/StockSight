# Application views

Implemented November 16, 2026 after the UConn frontend redesign (`b0e256a`).
No routing dependency, backend route, schema, import, or ML implementation was added.

## Navigation

| URL fragment | View | Behavior |
| --- | --- | --- |
| `#/dashboard` | My dashboard | Private watchlist, filtering, saved dates (UTC), open/remove, sign-in/loading/empty/error/success states |
| `#/analysis?symbol=AAPL` | Stock analysis | Existing search, price/volume, SMA20/RSI14, inspection, save, and link to the selected stock's prediction page |
| `#/predictions?symbol=AAPL` | Predictions | Selected stock and return-to-analysis link; explicit unavailable generation/history, disabled generation action |
| `#/performance` | Model performance | Explicit unavailable evaluation state; no artificial metrics or baseline results |
| `#/methodology` | Data & methodology | Data source/range/adjustment limitations, SMA/RSI conventions, watchlists and project information |

Root `/` continues to open Analysis for compatibility. The brand opens Dashboard.
Legacy `#analysis`, `#watchlist`, and `#project` resolve to the corresponding views.
Unknown pages provide recovery to Analysis. Symbol parameters are normalized and
validated; unrecognized symbols still receive the normal API error. Browser
back/forward and refresh work without server route rewrites. Page changes update
the title, active navigation and main-content focus. The skip link focuses the
current page without changing its route. Navigation remembers selected-stock context.

`use-page-route.js` uses React's useSyncExternalStore to observe hash navigation.
`Pages.jsx` contains the new view components; `Watchlist.jsx` shares private
states/actions between its compact sidebar and expanded dashboard presentation.
App owns a single existing useWatchlist instance, so all mutations retain the
current authorizedFetch wrapper and server-derived owner. Filter text is keyed to
the active account and private items remain owner-keyed. Auth0's successful callback
now replaces the URL with `/#/dashboard` and notifies the route subscriber.
Auth0 still owns authentication; no client token persistence was introduced.

## ML boundary

Gavin assigned ML to Vlad. Predictions and performance are navigable unavailable
views, not implemented ML features. They do not call nonexistent endpoints, store
fake forecasts, claim that history is empty, or display example accuracy. Generation
is disabled with a visible explanation. The selected stock can be opened in Analysis.

To activate these pages, integrate the agreed backend contracts for trusted-model
inference, stable persisted forecasts, owner authorization, retry/deduplication,
cutoff/target/model provenance, pending-to-resolved outcomes and same-sample held-out
baseline evaluation. Add real loading/error/empty/populated-state tests at that
boundary. Do not enable generation merely because an offline model exists.

## Verification

- ESLint and Vite production build passed.
- Full browser run passed 25 public cases (11 chart, eight indicator, six new page
  cases) plus 11 isolated account/session cases. A final seventh page case and
  stock-context navigation refinement passed in the focused seven-case page run.
- Page cases cover navigation/history/refresh, active state/focus, legacy and unknown
  paths, selected stock, skip link, explicit ML unavailability without ML requests,
  and desktop/mobile overflow at 1440/390/320px.
- New account cases exercise real signed-test identity and SQLite-backed watchlist
  persistence: dashboard filtering/open/removal across refresh, failure/retry,
  sign-out privacy and populated dashboard fit at 320px. Earlier account isolation,
  expiry, SDK PKCE and invalid callback cases also passed.
- Public suites use the real explicit fixture API. Account suites use the existing
  test-only identity boundary and isolated SQLite; they are not new hosted Auth0
  acceptance or PostgreSQL verification.
- Visually inspected ignored desktop/mobile screenshots under
  `.local-data/pages-{dashboard,predictions,performance,methodology}-{1440,390}.png`.
  These screenshots contain guest states only. No real-account capture was taken.

No push, merge, deployment, second-machine or hosted CI success is claimed.
The full prediction MVP remains unfinished until the ML integration above is delivered.
