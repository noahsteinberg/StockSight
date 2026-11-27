# Daily price refresh

## Delivery state

The scheduled workflow is active. The
[November 27 scheduled run](https://github.com/noahsteinberg/StockSight/actions/runs/46035699596)
passed the update and deployed API checks. For the current hosted schema and
frontend release, see the [current handoff](CURRENT_HANDOFF.md).

### Original November 23 rollout

PR #18 merged into main at d65544a on November 23. Hosted migration
0006_market_refresh is applied and the compatible Vercel deployment is READY.
The migration used the Supabase migration tool with SQL generated from the
committed Alembic migration, a prior-version guard and short lock timeout; the
application Alembic version was advanced in the same transaction.
The migration preserved all 1,214,087 existing bars. Both new audit tables have RLS and
no anon/authenticated table privileges. Production smoke checks and 56 HTTPS
price/indicator responses across seven stocks and four ranges passed.

The hosted seven-stock pilot subsequently completed successfully. Full histories
and metadata were backed up locally before the tested writer inserted 49 records,
audited one HUBB volume correction and retained the configured latest 2,500 sessions
(42 oldest bars removed and recoverable through the audit). AAPL/MSFT/NVDA/ABNB/
BRK-B/HUBB/ZTS now end November 23. ABNB grew by seven; total bars are 1,214,094.
Seven identical reruns changed no bars. All 56 production price/indicator checks,
the deployment smoke and the real production browser refresh/indicator/CSV checks
passed. The other 487 series' metadata/coverage and account table counts are
unchanged. Authenticated hosted account acceptance was not rerun.

The private connection now exists in ignored backend/.env in Noah's updater
worktree. It does not travel with Git; never print or commit it. The Supabase
plugin connection does not automatically configure SQLAlchemy.

The subsequent full-universe preview passed for all 494 stocks. Full histories
were backed up before expansion. All 494 now end November 23, with 1,214,290
stored bars. Across pilot and expansion there were 3,458 inserts, one audited
HUBB volume correction and 3,255 audited retention removals. The original Parquet
remains unchanged. Database size after refresh was 331,454,131 bytes.

Seven pool timeouts in the first full write were resolved: CLI worker concurrency
now respects the database pool size, and all seven fresh previews/retries passed.
API connection settings remain unchanged. Targeted regression checks passed
(28 tests, 2 PostgreSQL-only skips in this local run); Ruff and frontend lint/build
passed. No schedule, TradingView merge or ML run has occurred.

Final full-universe acceptance: 988 production HTTPS responses (prices and
indicators for every stock) matched stored OHLCV, dates, revisions and update
timestamps. All histories end November 23; account/session/watchlist counts match
the pre-expansion baseline. Evidence, full backups and per-stock recovery run IDs
are under ignored backend/.local-data/hosted-universe-*.json,
universe-before-refresh/ and hosted-pool-retry-write.json.

The updater extends existing imported US-stock daily history through a separate
command. It never runs inside public chart requests. The full-snapshot importer
continues to mean complete replacement and must not receive a short refresh window.

## Install and preview

Use Python 3.12 in a separate refresh environment. From backend:

~~~powershell
python -m venv .venv-refresh
.\.venv-refresh\Scripts\python.exe -m pip install -r requirements-refresh.txt
.\.venv-refresh\Scripts\python.exe -m app.environment_check
~~~

For development, configure STOCKSIGHT_DATABASE_URL for a disposable PostgreSQL
database ending in _test. The updater does not create or migrate databases.
Use a private direct/session connection for migrations. Never print/share URLs.

~~~powershell
.\.venv-refresh\Scripts\python.exe -m alembic upgrade head
New-Item -ItemType Directory -Path .local-data -Force
.\.venv-refresh\Scripts\python.exe -m app.refresh_prices --symbols AAPL,MSFT,NVDA --report .local-data/refresh-preview-001.json
~~~

The updater requires the market-refresh schema introduced in
`0006_market_refresh`. The combined app release uses
`0007_user_preferences`. Coordinate schema changes with deployment.

No --write means no database writes, including no refresh-run audit insert.
The report must be a new file. It includes proposed inserts/corrections, rejected
and missing dates, adjusted-close observations, retention removals and timing.
Read the per-stock status, not just the process finishing.

## Explicit write and recovery

After the preview and isolated tests pass, the same command with --write applies
per-stock transactions. --all-supported explicitly selects the existing supported
universe instead of --symbols. It does not onboard new tickers.

~~~powershell
.\.venv-refresh\Scripts\python.exe -m app.refresh_prices --symbols AAPL,MSFT,NVDA --write --report .local-data/refresh-write-001.json
~~~

Exit 1 means a stock was blocked, failed or still has missing completed sessions.
Other stocks, or a valid prefix before a missing date, may already have committed.
The next run retries the gap; no later date is inserted past an unresolved gap.

For a reviewed rollback, --restore-run RUN_UUID --write restores inserted,
corrected and retention-removed records only while that run's applied revision is
still current. It refuses to overwrite a newer revision or changed audited bars.
Original snapshot source labels are restored; the data revision advances again.
Refresh audit records are retained. Back up pilot series/provenance before any
hosted write, and test recovery on the disposable database first.

Existing audited series cannot be deleted by the full-replacement importer without
a separate provenance-preserving migration because audit foreign keys protect them.

## Data rules

- Daily OHLCV and auxiliary values are fetched with yfinance 1.8.0; auto_adjust,
  back_adjust and repair are false, actions/keepna true.
- The command uses up to three workers, capped by the database queue-pool size,
  with 20-second request timeouts and three attempts
  with bounded backoff. Optional Yahoo/calendar packages do not enter the API's
  runtime requirements.
- The Supabase transaction-pooler engine on port 6543 intentionally has one
  connection; the CLI uses one worker there to prevent pool starvation. A private
  direct/session URL can use the normal pool and up to three workers for bulk work.
- It uses the XNYS session calendar for the supported US-equity universe, including
  early closes, and a 30-minute finalization buffer. Unsupported provider
  timezone/symbol/date responses fail; holidays do not create synthetic bars.
- Missing/invalid closes are rejected even after the clock says a session ended.
  An unchanged request may legitimately remain partial until Yahoo finalizes it.
- Twenty stored sessions provide overlap. Missing overlap, differing OHLC,
  historical gaps newly supplied by a provider, and split events block that
  stock for investigation. Halts or legitimate missing sessions need review.
- Volume corrections are auditable. Existing adjusted-close vintages/actions stay
  unchanged on overlap; newly observed values are recorded separately. Do not
  assemble these auxiliary vintages into an asserted consistent total-return
  series or silently replace frozen research inputs.
- Existing shared validation rejects bad values and rounds OHLC to six decimals.
  Yahoo does not provide the team's bad_bar flag; passing validation is not a
  claim that Yahoo certified the data or reproduced the original cleaning.
- The original Parquet SHA256 remains initial-import provenance. Each download
  has a fingerprint of its normalized response and each write has a run UUID.
- Each transaction rechecks the series revision and original bars under a row
  lock, applies changes, retains the latest 2,500 valid records, writes old/new
  audit records, and advances updated_at. Requests happen outside transactions.
- Identical reruns log a check but leave bars and snapshot IDs unchanged. Provider
  failures in write mode are journaled without changing prices.

## API and pages

Existing prices/indicators routes are unchanged. Their mode additionally accepts
daily_history and optional last_refreshed_at is returned consistently.
The snapshot ID uses the last data-update revision, falling back to imported_at
for original histories. Same-date corrections change both endpoints' identity.

Analysis shows Stored daily history and Latest stored close. Refresh data
refetches stored prices, enabled indicators and private watchlist summaries;
it does not download Yahoo data. Revisiting Analysis/Dashboard refreshes
authenticated watchlist summaries. Replay and CSV remain based on the displayed
stored observations. There is no hourly polling or new prediction feature.

## Verification recorded for this implementation

- Clean isolated yfinance 1.8.0 request returned the expected daily columns.
- Full backend suite: 161 passed, 2 skipped, including real disposable PostgreSQL.
  Skips are PostgreSQL-specific cases evaluated under the SQLite parameter.
- Public browser suite: 41 passed, including refresh/date/indicator/CSV coverage.
- Real seven-stock rehearsal loaded the unchanged original Parquet into a second
  disposable PostgreSQL database; previewed 42 new bars; applied 79 changes
  including retention deletions/correction; repeated with zero changes; verified
  56 regular localhost HTTP price/indicator responses; restored all original
  pilot histories. This is local evidence, not hosted acceptance.
- Rehearsal ran in 14.569 seconds after initial data loading. It is not a runtime
  estimate or provider-availability guarantee for 494 stocks.
- Account browser suite: 24 passed against its own disposable PostgreSQL database.
  Frontend lint/build, backend Ruff and pip check passed. A revisit-refresh race
  found by the existing retry test was corrected before the successful rerun.
- A later real CLI dry-run proposed 48 inserts: November 23 was available for
  six symbols, while HUBB still lacked that completed session. It exited 1 with
  attention_required and write_enabled=false, correctly preserving the pending
  stock instead of claiming complete coverage. No database write occurred.

Raw reports, downloaded data and test connection information stay outside Git.
The seven-stock report is in Noah's local tmp/stocksight-feed-audit-20261123/
implementation-local-pilot.json. Existing research environments were not modified.

## Hosted verification and scheduling

The hosted migration, compatible code deployment and seven-stock price pilot are
complete. Stored data, refresh, indicators and CSV passed production checks.
Hosted authenticated account acceptance remains a separate manual check. Keep
the ignored pilot backups and audit run IDs. Do not rerun migration 0006 or
seed/reimport the database.
The first full-universe preview and manual expansion are complete. For future
updates, report blocked stocks explicitly; never force incompatible prices.

The Daily price refresh workflow is in .github/workflows/daily-price-refresh.yml.
It supports manual preview/update runs on main. Scheduled updates are gated by
the repository variable STOCKSIGHT_REFRESH_SCHEDULE_ENABLED being exactly true;
leave it absent until manual preview and update runs both pass. The workflow
uses the same tested CLI, a non-cancelling concurrency group, a 30-minute timeout,
pinned checkout/setup actions and a per-stock job summary. A failed/partial run
stays failed; valid committed stocks remain usable and later runs retry gaps.
Successful update runs also execute the read-only production smoke check.

### One-time GitHub setup

1. Open repository Settings > Secrets and variables > Actions > Secrets.
   Add repository secret STOCKSIGHT_REFRESH_DATABASE_URL. Its value is only the
   full private PostgreSQL URL (including password), without the environment
   variable name or surrounding quotes. Do not paste it in chat or documentation.
2. Open Actions > Daily price refresh > Run workflow. Select main and mode preview.
   Run it, wait for green, and review the per-stock summary for missing/blocked data.
3. Run the workflow again on main with mode update. Wait for green, including the
   deployed API check. Manual dispatch from the browser remains a user action
   when the connector cannot dispatch workflows. No hosted Actions run is claimed
   until its result has actually been observed.
4. Only after both pass, open Settings > Secrets and variables > Actions > Variables.
   Add repository variable STOCKSIGHT_REFRESH_SCHEDULE_ENABLED with value true.
   Delete it or set false to pause scheduled writes. Manual runs still work.
5. Enable GitHub Actions failure notifications in your personal notification
   settings, and inspect red runs under Actions. Email delivery depends on those
   preferences; the workflow summary alone does not establish email acceptance.

The schedule is 01:17 and 06:17 America/New_York, Tuesday through Saturday:
these mornings follow Monday-Friday trading sessions. Native timezone scheduling
handles daylight-saving changes. The second run retries incomplete provider data;
it is safe when the first run already succeeded. Exchange holidays do not create
synthetic sessions. GitHub can delay schedules, and inactive public repositories
can have schedules disabled after 60 days. The laptop does not need to stay on.

This automates completed daily history, not streaming quotes or browser polling.
An open page needs Refresh data/reload; opening it normally reads current storage.
Manual Actions acceptance passed November 23: preview run 45328253600 checked
all 494 stocks with writes disabled; update run 45328799719 succeeded for all
494 with writes enabled and passed the production smoke check. Both found zero
pending inserts/corrections, missing sessions or blockers. Preview took about
three minutes; update about seven. Noah enabled scheduled updates after both
manual checks. No secret was copied into Git, workflow source or artifacts.

## References

- [Current handoff](CURRENT_HANDOFF.md)
- [Import rules and provenance](PRICES_IMPORT.md)
- [yfinance history API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)
- [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
