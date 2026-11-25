# StockSight current handoff

## Next product work: Vlad / @Hab1yer

Read [FRONTEND_PRODUCT_HANDOFF.md](FRONTEND_PRODUCT_HANDOFF.md) for the proposed
stock-exploration product: Explore, preserved Analysis, 2–4-stock Compare, private
Watchlist, optional research preferences and honest future signal integration.
It gives exact user flows/questions, data gaps, proposed APIs/persistence,
incremental acceptance and PR #16 integration precautions. **Before coding,
the next AI must ask its supervising human to review the concrete plan, answer
unresolved UX questions and explicitly approve the increment.** Application code,
schema and PR #16 were not changed by this planning task.

The master implementation tracker is
[issue #19](https://github.com/noahsteinberg/StockSight/issues/19), assigned to
@Hab1yer. It contains the human-approval requirement and copyable agent prompt.

Reviewed main at e9a4620. PR #16 is unmerged and reports merge conflicts; port/rebase
it against current main only after review, preserving daily-refresh changes.
The catalog lacks sectors and imported names/exchanges may be placeholders.
Profiles, discovery, comparison and ML APIs do not exist yet. Do not fabricate
metadata, predictions or recommendation confidence while adding the views.

Noah reports setting STOCKSIGHT_REFRESH_SCHEDULE_ENABLED=true after both manual
Actions modes passed. Daily-history configuration is complete; first scheduled
event observation and failure-email preferences remain follow-ups. No live-price
values should be extracted from TradingView into daily_bars. A widget can be
integrated separately for display without a new backend streaming service.

Fresh checks for issue triage: CI run 45328102380 and both manual refresh runs
passed; frontend npm audit reported zero vulnerabilities. Frozen ML research
remains paused. Issue #19 was created and assigned to @Hab1yer. Issues #1/#2/#7/#11
were closed as completed with evidence; #5/#6/#8/#9 were closed as superseded
(not planned under their old standalone scope), with unfinished work preserved
in #19 and the new plan. Original issue bodies remain intact. PR #16 remains open.
No deferred prediction persistence, saved-ranking research or model serving was
claimed completed. The plan was published in commit 4e13e71; this checkpoint
records the subsequent issue cleanup. No application code or hosted data changed.

## Metadata and quote increment (issue #19, Phase 3) — November 24

Vlad asked to finish all remaining phases, accepting the plan's recommended
options. Decisions recorded for Phase 3:
- Company name, sector and sub-industry come from one reviewed static file,
  pinned to a public source revision. There's no schema migration and no
  rewrite of `stocks` rows; see STOCK_METADATA.md.
- Explore gets a GICS sector filter. Sort stays A–Z, because no other sort is
  approved.
- PR #16's quote panel lives on Analysis only. It is hidden (not removed)
  during historical replay. There are no widgets on Explore or Compare.

Implemented on local branch `feature/metadata-quote`, stacked on
`feature/compare-page`. Not pushed. PR #16's three commits were cherry-picked
with Parth's authorship kept. The only conflicts were import and Methodology
text conflicts in Analysis.jsx and Pages.jsx, resolved by keeping both sides.

- Data: Wikipedia "List of S&P 500 companies", revision 1384572480 (Nov 8,
  2026, CC BY-SA 4.0). All 494 supported tickers matched, including BRK-B,
  BF-B and CBOE. Every sector is one of the 11 GICS sectors (Industrials 80 …
  Communication Services 21). backend/app/build_stock_metadata.py reproduces
  the committed CSV byte for byte.
- API changes:
  - `sector` filter and `sector`/`sub_industry` fields on GET /api/explore.
  - New GET /api/sectors (counts, unknown coverage, source).
  - New GET /api/stocks/{symbol}/profile.
  - Search, price history, Compare and watchlist names now use the reviewed
    name instead of the ticker placeholder. Response shapes are unchanged
    apart from the new fields.
- UI changes:
  - Explore: a Sector select (with counts) kept in the URL, a sector line on
    each row, Reset filters, and a source note with the pinned link.
  - Analysis: a company/sector line, and the TradingView panel hidden during
    replay.
  - Methodology: a "Company names and sectors" section.
  - The chart heading no longer repeats a placeholder name.
- PR #16 checklist: stale Nov 12/"refresh unfinished" statements were fixed in
  TRADINGVIEW.md (and noted in Parth's handoff section). Its tests moved to
  #/analysis, and replay-hiding coverage was added.

Verification on November 24:
- Backend: 162 passed, 3 skipped. That includes the new sector, sectors,
  profile and company-name search tests and the metadata-file checks. Ruff
  lint/format pass.
- Frontend: lint and build pass.
- Browser suites: public 64/64 (new: sector filter/URL/reset, empty sector
  not broadened, replay hides the quote without reloading it, Analysis
  context line) and accounts 24/24.
- Local full data (Docker snapshot through 2026-11-12):
  - /api/sectors reports 494 supported, 0 unknown.
  - The Energy filter gives 21 rows; "berkshire" finds BRK-B.
  - Filtered Explore takes about 60 ms.
- Real vendor in the in-app browser: the BRK-B Analysis page loaded TradingView
  NYSE:BRK.B. Starting replay hid the embed and showed the notice; exiting
  replay showed the same iframe again. Explore at 320 px with a sector filter
  has no horizontal overflow.

Review asks: Parth (metadata source choice, widget integration), Gavin (API/UI
contracts). Next: Phase 4 preferences.

## Compare increment (issue #19, Phase 2) — November 24

Vlad approved Phase 2 as recommended: 2–4 stocks, the same ranges as Analysis,
a common-date chart indexed to 100, price change only (no volatility or
drawdown until Parth reviews the numerics), honest split, short-history and
cutoff states, a compare tray on Explore, and compare from the Watchlist.
Implemented on local branch `feature/compare-page`, stacked on
`feature/explore-page` (Phase 1 PR pending). Not pushed.

- Public GET /api/compare (rules in API.md): shared cutoff, common dates only,
  close/first × 100, and a check for each split inside the window. No schema
  change, data writes, provider calls or ML.
- Compare page (#/compare?symbols=&range=):
  - Edit by chip, by "Add ticker", or by range.
  - Native SVG chart with a dash pattern per line, a 100 baseline and a
    keyboard/pointer readout.
  - Summary table and disclosure notes.
  - Separate states for under-2 symbols, links with more than 4, unknown
    symbols (each removable), 503/retry, malformed data and no overlap.
- Sidebar adds Compare. A + toggle on Explore and Watchlist rows and "Add to
  comparison" on Analysis feed a tray (max 4, kept in this tab's
  sessionStorage, public tickers only).
- Data finding: the snapshot's closes are split-adjusted (NVDA is continuous
  across its 2024-06-10 10:1 split), but dividends aren't included, so the
  page labels results as price change, not total return.

Verification on November 24:
- Backend: 151 passed, 3 skipped, including 13 new compare tests (common
  dates, cutoff, adjusted/unadjusted splits, range trimming, overlap, 422/404/503,
  fixture mode). Ruff lint/format pass.
- Frontend: lint and build pass.
- Browser suites: public 56/56 (9 new compare cases, with synthetic TST
  responses plus the real fixture 404) and accounts 24/24.
- Local full-data check (Docker snapshot):
  - AAPL/MSFT/NVDA 1y gives 252 common sessions (AAPL +29.77%, MSFT +2.32%,
    NVDA −14.25%).
  - NVDA/AAPL/TSLA/BRK-B Max gives 2000; all five recorded splits are
    detected as adjusted.
  - ABNB/MSFT Max gives 1,488 (ABNB's history starts 2020-12-10).
  - Queries take 70–190 ms. MSFT's chart low (index ≈69) matches the stored
    min close ($352.83 vs a $511.14 start).
  - Phone layouts: at 320/390 px there is no overflow; the chart shows only
    start/end dates and the table hides the start→end column.

Next: review/merge Phase 1, then open a PR for this branch. Parth should
review the compare numerics (API.md). Phase 3 (metadata and PR #16) needs its
own approval.

## Explore increment (issue #19, Phase 1) — November 24

Vlad approved the Phase 0 direction:
- Explore, Compare and the existing watchlist ship first.
- Navigation is Explore · Analysis · Compare · Watchlist.
- "Recommendations" means explainable filter matches, never ML scores.
- Explore becomes the landing page.
- Predictions and Model performance leave the sidebar but keep their routes.
- The compare tray moves to Phase 2, so it ships with the Compare page.

The decision record is drafted for issue #19 (paste it from Vlad's local
issue19-phase0-comment.md). Implemented on local branch `feature/explore-page`
(not pushed, no PR yet):

- Public GET /api/explore (see API.md). It is a paginated summary of supported
  stocks with the newest stored close/date and the change between the two newest
  stored closes. Placeholder names (name == symbol) and UNKNOWN exchanges are
  returned as null. No schema change, data write, provider call or ML.
- Explore page (#/explore?q=&page=) with debounced search kept in the URL, 25 rows
  per page, Previous/Next, and separate loading, empty, past-the-end, 503/error
  and malformed-response states. Each row has a save star (guests are sent to
  sign-in) and an "earlier session" note when a stock's date trails the newest
  session. On phones, all columns fit at 320/390 px.
- Root / and the brand now open Explore. The sidebar is Explore, Analysis,
  Watchlist (#/dashboard, renamed) and Methodology. Predictions links to Model
  performance.
- Audit finding: about 490 of 494 hosted catalog names are placeholders, so
  most Explore rows show "Name not yet available". Verified names and sectors
  remain Phase 3 metadata work. PR #16 conflicts with main only in
  frontend/src/Pages.jsx; it is untouched.

Verification on November 24 (fixture mode, local; nothing hosted):
- Backend: 138 passed, 3 skipped (PostgreSQL-only). This includes 11 new
  explore tests on migrated SQLite: placeholders, paging, query, 422 and 503.
  Ruff lint/format pass.
- Frontend: lint and build pass. The public browser suite passed 47/47. In
  the final full rerun, the existing analysis-chart test "null warm-up values…"
  failed once and then passed 4/4 on repeat (timing flake, unrelated to Explore).
- Account suite: 24/24, after one fix. Explore rows are named by their content
  (e.g. "AAPL Apple Inc."), so they can't be confused with private watchlist
  links ("Open AAPL analysis").
- Explore browser cases use the real AAPL fixture plus clearly synthetic TST
  responses for multi-page, search, error and stale-response checks.

Full-data check, November 24:
- Vlad's local Docker PostgreSQL was loaded with `app.complete_backend` from
  the team snapshot (SHA256 matches PRICES_IMPORT.md). BACKEND VERIFIED: 494
  symbols, 2,947,701 rows. Local history ends 2026-11-12; hosted is newer.
- Live HTTP checks against app.main:app:
  - All 20 pages return the 494 stocks exactly once.
  - The first page took ~150 ms cold, later pages ~35 ms.
  - Every name is null locally: the local snapshot has no verified names, not
    even AAPL.
  - MSFT's Explore close/date/revision equal its price-history response.
- Browser checks: search and ticker ranking (e.g. "ms" puts MS first), the last
  page, and opening a stock's real chart all work. At 375 px, neither the page
  nor the table overflows.
- Fixes from this pass:
  - The summary now reads "N match(es) for “q”".
  - An empty search explains that company names aren't stored yet and suggests
    a ticker (searching "apple" finds nothing until Phase 3 metadata).
- Noted for Phase 3: Analysis shows the placeholder twice ("MSFT MSFT").

Not yet verified: hosted Auth0 saving from Explore, and Explore on the hosted
deployment (it reaches production only after review/merge to main). Next: human review of the branch, then push/PR when Vlad asks; Phase 2
(Compare + compare tray) needs its own approval.

## Daily refresh implementation — November 23

### GitHub automation prepared — November 23

Manual hosted Actions acceptance is now verified from job logs: preview run
45328253600 reported 494 preview results with writes disabled; update run
45328799719 reported 494 successes with writes enabled and passed the deployed
API smoke check (AAPL through November 23). Both had zero inserts/corrections,
missing sessions or blockers because the full universe was already current.
Preview took about three minutes; update about seven. The Actions secret is
therefore working. Noah's remaining activation step is the repository variable
STOCKSIGHT_REFRESH_SCHEDULE_ENABLED=true. The agent did not change that variable.
The setup notes below describe the earlier prepared state, before these runs.

Daily price refresh now has a workflow with manual preview/update modes and a
gated 01:17/06:17 America/New_York Tuesday-Saturday schedule. The job uses the
existing CLI, prevents overlapping writers, records selected per-stock results,
and smoke-checks production after successful writes. Ruff, the summary regression
test, YAML parsing, schedule/default checks and Bash syntax validation passed.

Activation still needs Noah's GitHub UI: add Actions secret
STOCKSIGHT_REFRESH_DATABASE_URL, run preview then update on main and review both
results, then set repository variable STOCKSIGHT_REFRESH_SCHEDULE_ENABLED=true.
The connector cannot set repository secrets or dispatch this workflow; no gh CLI
is installed. Noah requested exact browser instructions instead of automation of
his browser. No hosted Actions refresh run or automatic schedule is claimed yet.
See DAILY_REFRESH.md for exact setup and pause/recovery instructions. Do not
enable the variable before manual acceptance. Failure email preferences also
need user verification; per-stock workflow summaries are implemented.

### Full hosted data update completed — November 23

All 494 supported stocks now end 2026-11-23, with 1,214,290 daily bars retained.
The read-only universe preview passed for all 494. Full histories, series metadata
and a manifest were saved under ignored backend/.local-data/universe-before-refresh/
before expansion. Including the pilot, the update added 3,458 daily records,
audited one HUBB volume correction and retained the agreed latest 2,500 sessions
per stock (3,255 oldest records removed and preserved in the change audit).
The research Parquet was not edited. Database size after refresh: 331,454,131 bytes.

The first expansion completed 480 new stocks and left seven unchanged after
connection-pool timeouts. The shared web engine deliberately has one connection
on transaction-pooler port 6543; three CLI workers could starve that pool. The
CLI now caps its workers at the engine's queue-pool size (maximum three), without
changing API connection settings. A regression test uses a real one-connection
pool and short timeout. Targeted updater/Supabase tests: 28 passed, 2 skipped;
Ruff lint/format and frontend lint/build passed. A fresh preview and write retry
of CBOE/CRH/DVN/IBM/MAR/PCG/SWK all succeeded. Preserve the original failed-run
report as evidence; those errors are resolved, not outstanding data gaps.

Final universe verification passed: 988 production HTTPS responses (prices and
indicators for every stock) matched stored OHLCV, dates, revisions and refresh
timestamps. All 494 latest sessions are November 23. Account/session/watchlist
counts still match the pre-expansion baseline. The full report is ignored at
backend/.local-data/hosted-universe-verification.json; keep the full backup
manifest, hosted-universe-write.json and hosted-pool-retry-write.json for recovery.

Next: complete the manual GitHub Actions acceptance described above, then enable
the gated schedule. Hosted authenticated account acceptance
remains separate. PR #16, frontend discovery/comparison and ML are subsequent work.
The release and pilot checkpoints below describe the earlier staged rollout.

### Hosted release checkpoint — November 23

PR #18 is merged at main d65544a9dc004b879d936c8e37f7670fac9ef26a.
Its latest PR CI passed. The additive 0006_market_refresh migration was applied
through Supabase with a guarded Alembic version update. Production Vercel
deployment dpl_7q8qFZqaMRDjR8enV7W8hNcju9MT is READY and assigned to
https://stocksight-rose.vercel.app. At this pre-data-update checkpoint all 1,214,087
existing bars were unchanged and the two audit tables were empty and backend-only
(RLS, browser privileges revoked).
The deployment smoke check passed, as did 56 production HTTPS price/indicator
checks across AAPL/MSFT/NVDA/ABNB/BRK-B/HUBB/ZTS and all four ranges. Their dates,
snapshots and null refresh timestamps agree. Error/fatal runtime-log scan found
no matching records for the new deployment. Security advisor reports only the
expected informational RLS-without-policy notices for nine backend-only tables.
Raw read-only release evidence is outside Git under Noah's
tmp/stocksight-feed-audit-20261123/hosted-release-check.json.

### Hosted seven-stock pilot completed — November 23

Noah saved the private connection in this worktree's ignored backend/.env. A typo
in the project username was corrected; the password was preserved and not printed.
The connection independently confirmed the intended schema and data counts.
Full pilot histories/metadata were backed up before writes. Fresh downloads
passed all seven overlap checks with no missing completed sessions or OHLC
conflicts. The tested apply_refresh writer committed 49 new sessions, one HUBB
volume correction and 42 audited retention removals. AAPL/MSFT/NVDA/ABNB/BRK-B/
HUBB/ZTS now end 2026-11-23. Total stored bars: 1,214,094 across 494 stocks.

Verification after writing: 56 production HTTPS price/indicator responses matched
stored OHLCV, dates, revisions and refresh timestamps; production smoke passed.
Seven identical captured-download reruns changed zero bars and preserved revisions.
The other 487 series' metadata/counts/date bounds were unchanged, and private
account/session/watchlist counts matched the pre-write baseline. A real headless
production browser verified AAPL's November 23 date, stored-update label, Refresh
data, both indicator toggles, latest-date CSV export and the mobile refresh control,
with zero page errors. No error/fatal production runtime logs matched the check.
Hosted account save/logout/two-user acceptance was not rerun; count preservation
and guest-route checks do not replace that acceptance.

Local backups, normalized downloads, per-stock audit run IDs and reports are
ignored under backend/.local-data/hosted-pilot-*.json, hosted-download-*.json,
hosted-write-*.json, hosted-repeat-*.json and hosted-browser-verification.json.
Do not delete these recovery records. Recovery remains the guarded restore-run
procedure; no production rollback was exercised or needed.

The subsequent full-universe checkpoint above supersedes the pilot-only coverage.
PR #16 and ML remain separate. Do not rerun the completed migration. The
implementation/publication notes below are dated earlier evidence.

Implementation commit `3d836c6` is published on `feature/daily-price-refresh`.
GitHub Actions backend, frontend and browser jobs passed for that commit.
The working tree was clean after publication. After Noah reauthenticated GitHub,
the connector successfully created draft PR #18:
https://github.com/noahsteinberg/StockSight/pull/18
The earlier connector 403 is resolved; no credential-based fallback was used.
This earlier draft/publication checkpoint is superseded by the release above.

Implemented on feature/daily-price-refresh, based on main 2c955a0. See
[the daily refresh guide](DAILY_REFRESH.md) for commands, data rules and rollout.
The separate preview-first Yahoo updater reuses validation, records provenance
and corrections, preserves 2,500 sessions, and supports guarded restoration.
Migration 0006_market_refresh adds two backend-only audit tables and a nullable
series updated_at timestamp. Existing prices/indicators also accept daily_history
and return optional last_refreshed_at. Analysis can refetch stored data without
calling a provider. Watchlist summaries refresh on revisit/explicit refresh.

Verification: 161 backend tests passed, 2 skipped, including disposable PostgreSQL;
41 public browser cases passed. The real seven-stock local rehearsal previewed
42 inserts, committed 79 changes including trimming/correction, repeated with
zero changes, checked 56 regular localhost HTTP responses, and restored original
histories. All 24 isolated account browser cases passed, including login,
logout, watchlist persistence/isolation and retry recovery. Backend Ruff,
frontend lint/build and pip check passed. Yahoo/calendar dependencies are isolated
from the API runtime and included in development/test requirements.

At implementation completion, no hosted migration or release had occurred.
The release checkpoint above records their subsequent completion. Hosted price
updates, scheduling, TradingView and ML remain pending. Readiness fails closed
on a missing schema. Raw pilot evidence and downloads remain outside Git.

Update this file when implementation, delivery state or acceptance changes.
Use Git history for earlier checkpoints and the linked guides for setup and
contracts.

## November 23 market-price widget

*Phase 3 note (November 24):* the statements below about a November 12 history
end, unfinished refresh and the `feature/tradingview-prices` branch were true when
written. They are superseded: the hosted refresh is complete (see Daily refresh
above), the widget now shows the chart's actual `as_of`, and these commits were
integrated on `feature/metadata-quote` (see the Phase 3 section). Parth's
evidence below is preserved unchanged.

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
  At this pre-refresh checkpoint migration head was `0005_backend_only_access`; all seven public app/version
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
