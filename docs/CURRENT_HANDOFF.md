# StockSight current handoff

Update this file when implementation, delivery state or acceptance changes.
Use Git history for earlier checkpoints and the linked guides for setup and
contracts.

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
  during the earlier release check. The November 23 data migration updated the
  existing Supabase database without deploying application code. Production's
  AAPL response matches the new hosted snapshot and ends 2026-11-12. The existing
  read-only deployment smoke passed again for frontend delivery, database
  readiness, prices/indicators and guest/private-route protection.
- Supabase now holds all **494 source tickers and 1,214,087 daily bars**, retaining
  up to **2,500 latest accepted sessions per ticker** by Parth's explicit choice.
  All 494 histories end 2026-11-12; 29 have fewer than 2,500 accepted sessions.
  Earliest retained coverage across the universe is 2016-11-08; AAPL/MSFT/NVDA
  each start 2016-12-02. The original full Parquet and local research dataset
  remain unchanged. This is historical data, with no automated refresh.
- The dashboard confirmed the Free plan's 500 MB database allowance. Observed
  PostgreSQL size after import was **326,137,523 bytes**. Every ticker's stored
  count, date bounds and original source SHA256 matched the retained import plan.
  Migration head remains `0005_backend_only_access`; all seven public app/version
  tables retain RLS, `anon`/`authenticated` lack SELECT/INSERT/UPDATE/DELETE
  privileges, and private account/session/watchlist table counts are unchanged.
  AAPL's old fixture was backed up before its authorized replacement.
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
- November 23 source validation independently matched the recorded hash:
  2,947,701 accepted bars and 252 quarantines across 494 tickers. The hosted
  retention option selects the latest accepted sessions without editing the
  file, changing the full-history default, or reusing a short-window refresh as
  a snapshot. `app.migration_plan` provides a read-only source/target preview.
  Evidence is ignored under `.local-data/hosted-retained-import-result.json`,
  with original-AAPL backup and full source validation/quarantine reports there.
- Verification on November 23: **107 backend tests passed, 2 disposable-PostgreSQL
  cases skipped**; Ruff lint and format passed. Frontend lint and production
  build also passed before publishing the branch for review. Real Uvicorn HTTP and deployed
  HTTPS checks covered AAPL/MSFT/NVDA/ABNB/BRK-B/HUBB/ZTS in all four ranges:
  56 price/indicator pairs matched source values, stored snapshots and retained
  calculation history. All 252 quarantined ticker/date keys were absent from
  storage. Evidence is `.local-data/hosted-retained-http-verification.json`.
  The temporary local API used for these checks was stopped afterward.
- Import code, tests and documentation are on branch
  `feature/hosted-market-data`, based on main `afe8051`, for pull-request review.
  [Parth's dated work summary](PARTH_DATA_UPDATE_2026-11-23.md) explains the
  contribution and verification evidence in plain language. Check GitHub for
  the current branch/PR delivery status before continuing.
  The hosted data itself is already updated and visible to the deployed API.
  Preserve the ignored private connection in this checkout; do not seed or rerun
  an import during routine startup. Use the guides for a deliberate later change.
- API research is updated in [YAHOO_FINANCE.md](YAHOO_FINANCE.md). Alpaca is a
  technical candidate for a private daily-history/quote pilot; no account, keys,
  provider adapter or schedule has been configured. Public-display rights,
  feed/adjustment compatibility, an incremental writer and timestamped quote
  provenance must be settled before activating refresh. Keep the historical
  snapshot's actual date visible.
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
