# Daily price refresh

## Delivery state

Implemented on an isolated branch from main 2c955a0. No hosted migration, data
write, schedule, TradingView merge or ML run has been performed.

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

Migration head is 0006_market_refresh. Deploying new code against the old schema
fails readiness closed; deploy code and migrate in a coordinated release.

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
- The command uses three workers, 20-second request timeouts and three attempts
  with bounded backoff. Optional Yahoo/calendar packages do not enter the API's
  runtime requirements.
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

## Hosted pilot and scheduling still to do

Back up AAPL/MSFT/NVDA/ABNB/BRK-B/HUBB/ZTS, review the hosted migration/preview,
apply the pilot and verify deployed ranges, indicators, dates, CSV and accounts.
Run a universe-wide preview before expanding; report blocked stocks explicitly.

After hosted acceptance, run this same command via GitHub Actions, first manually
and then at 01:17 America/New_York with a 06:17 retry. Store the connection only in
Actions secrets, use one concurrency group without cancelling an active writer,
and configure failure notifications and summaries. Schedule activation is
deliberately deferred. No scheduled workflow has been installed by this increment.

## References

- [Current handoff](CURRENT_HANDOFF.md)
- [Import rules and provenance](PRICES_IMPORT.md)
- [yfinance history API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)
- [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
