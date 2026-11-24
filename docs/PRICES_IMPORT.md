# Import the team historical dataset

The local team snapshot has already been imported successfully. This guide is
for deliberate initial imports or authorized replacements, not routine startup.
Use [CURRENT_HANDOFF.md](CURRENT_HANDOFF.md) and LOCAL_START.md to resume existing
work without reimporting or seeding over the canonical series.

Noah's November 16 team messages identify Yahoo Finance as the intended source
and S&P 500 stocks as the project scope. Vlad identifies prices_clean.parquet as
the supplied dataset. This is team-reported provenance, not an independently
verified download/cleaning pipeline or evidence of historical index membership.

The source file remains outside Git. The local input is in Gavin's Downloads.
The validated SHA256 is
ee0b2ed66c8abb87e0cf36798a32258bc902c0e1687ddee2a485c80b44216e89.

## Verified validation results

- 2,947,953 source records; 494 tickers.
- Dates span 2000-01-03 through 2026-11-12.
- 2,947,701 accepted rows; 252 quarantined rows.
- Overlapping reasons: flagged_bar 214, missing_value 251, ohlc_bounds 1,
  rounded_bounds 1. Reason counts are not additive row totals.
- No input repair or modification. Structural/schema/key-order errors abort
  validation; flagged/incomplete/inconsistent values are quarantined.

Raw accepted OHLC is rounded to Numeric(18,6) using ROUND_HALF_EVEN and checked
again against bounds. The source file/hash preserves original OHLC precision.
The new nullable source_values JSON column retains adjusted close, dividends,
stock splits and quality flag alongside each imported accepted bar. Those values
are not substituted into the chart's closing-price field.

The OHLC adjustment convention remains unverified and is labeled accordingly.
USD is an explicit assumption from the team's US-stock scope; exchange and
company-name metadata are absent. Unknown names display their ticker rather
than invented company names; existing known names are preserved. A future
metadata import can add accurate company search names and exchange identifiers.

## Commands

### Complete the local backend in one command

From backend in your normal PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m app.complete_backend --replace-existing-series
```

Docker access is checked first. A denied or unavailable engine stops setup before the expensive data scan. See [execution access](LOCAL_START.md#execution-access).

This defaults to prices_clean.parquet in your Downloads folder. An optional first
argument supplies another path. It checks the configured URL is this project's
local Compose database, installs the pinned reader if missing, validates the
source, starts Compose, migrates, imports AAPL/MSFT/NVDA, and checks their counts
and in-process HTTP API responses before importing all accepted symbols.
It then verifies every selected symbol's stored count and source hash, checks
API responses again, and checks migration/model consistency. Successful evidence
is saved under ignored .local-data/backend-completion-TIMESTAMP.json.

The replacement flag authorizes replacing selected canonical histories, including
the small Plotly AAPL fixture, with the team snapshot. The database volume is
preserved. Errors stop the sequence; per-symbol import progress remains visible
and the unchanged input can be rerun. BACKEND VERIFIED is printed only after the
checks complete; it does not claim browser verification or that Uvicorn is running.
Restart the regular app.main:app API afterward and refresh the frontend.

### Individual steps

Run from backend in your own terminal. Install the optional reader first:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-import.txt
```

Validation only, with no database connection or writes:

```powershell
.\.venv\Scripts\python.exe -m app.import_prices "$env:USERPROFILE\Downloads\prices_clean.parquet" --symbols AAPL,MSFT,NVDA
```

Omit --symbols to validate all tickers. Optional --report PATH and --quarantine
PATH write a JSON summary and rejected ticker/date/reason JSONL. Output paths
must not already exist and cannot overwrite the input or each other. Keep data
and generated reports under the ignored .local-data directory or outside Git.

Start Docker Desktop and run docker compose up -d --wait from the repository
root. Confirm backend/.env points to that PostgreSQL instance. From backend:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.import_prices "$env:USERPROFILE\Downloads\prices_clean.parquet" --symbols AAPL,MSFT,NVDA --write --replace-existing-series
.\.venv\Scripts\python.exe -m app.doctor
```

--write is required to touch storage. Without --replace-existing-series, a
conflict with the existing Plotly AAPL series aborts before any symbol writes.
The replacement option deliberately changes the selected symbols' canonical
histories; use it only for this agreed transition. It does not change unrelated
symbols. Do not run app.seed afterward: that command is for the Plotly fixture.

After the subset passes PostgreSQL/browser checks, repeat the import command
without --symbols to import all accepted symbols. Each symbol's old snapshot is
replaced atomically in bounded 250-row insert batches. Repeating the unchanged
file preserves counts; corrections replace dates, and rejected dates disappear
from that symbol's new snapshot. A symbol with no accepted bars is not replaced.

Atomicity is per symbol, not for the whole universe. A failure can leave earlier
symbols completed; stderr lists committed symbols. There is no global success
report until all selected accepted counts and the final input hash agree. Rerun
the unchanged file to resume safely. Keep the input unchanged for the operation.
No refresh scheduler or live Yahoo download is introduced.

### Limit retained history for a hosted database

The optional `--max-bars-per-symbol N` keeps the latest N **accepted** sessions
for every selected ticker. Validation still scans the complete selected source
and quarantines invalid bars before selecting the retained window. The default
remains the complete accepted history. This is an explicit snapshot-retention
choice, not an incremental refresh operation.

For example, after reviewing the target and backing up histories being replaced:

```sh
.venv/bin/python -m app.migration_plan /PRIVATE/PATH/prices_clean.parquet --symbols AAPL,MSFT,NVDA --inspect-target --max-bars-per-symbol 2500
.venv/bin/python -m app.import_prices /PRIVATE/PATH/prices_clean.parquet --max-bars-per-symbol 2500
.venv/bin/python -m app.import_prices /PRIVATE/PATH/prices_clean.parquet --max-bars-per-symbol 2500 --write --replace-existing-series
```

The first command inventories the configured target and previews create/replace
actions without writing to the database. Its storage estimate is conservative;
measure an actual pilot and inspect the project's plan before a full import.
An offline preview explicitly leaves the target uninspected. The second command
validates all file symbols and reports the retained count without connecting.
The last command replaces the selected histories and requires deliberate approval
for that dataset transition. Never run it merely to start the application.

The original file stays unchanged. Its full SHA256 remains attached to each
series, while the adjustment/provenance label records the retained-session limit.
Reports distinguish accepted source rows from imported or planned retained rows.
Symbols with fewer accepted sessions retain all of them. Rejects do not consume
the retention allowance. Repeating the import replaces the retained window
atomically per symbol, including removal of dates outside that window.

The UI's Max view still returns at most 2,000 observations. Retaining 2,500
provides up to 500 preceding sessions for indicator warm-up at the start of that
view. Wilder RSI starts at the beginning of the available retained history; it
can differ slightly from calculations using the complete original history.
No model retraining or change to the local full-history research dataset follows
from this hosted retention choice.

## API and browser

Start the regular app.main:app API and npm run dev as in LOCAL_START.md.
/api/ready must report database. Search supports up to 50 matches; narrow a
query instead of assuming the list is the complete 494-symbol universe.
History reports mode historical_snapshot, team Yahoo source, dated coverage
and the unverified adjustment policy. Max remains capped at 2,000 observations
with has_earlier=true when appropriate. The unchanged explicit demo entry point
continues to show only the original small AAPL fixture.

## Verification limits

Full source validation and synthetic rollback/correction/conflict tests passed.
Real AAPL/MSFT/NVDA subset import evidence is in the ignored local verification
report. Disposable SQLite checks exercise the SQLAlchemy/import/API-function
contracts; they do not establish live PostgreSQL or HTTP/browser success.
The November 16 continuation completed the PostgreSQL import, verified every
symbol's stored count/hash, confirmed no schema drift and checked persistence
after a container restart. Real localhost HTTP responses for AAPL/MSFT/NVDA
matched repository histories across all four supported ranges. All 50 backend
tests passed with disposable PostgreSQL coverage, and Ruff lint/format passed.
The original import and HTTP reports were written to the ignored .local-data
directory as backend-completion-20261116T184037934756Z.json and
backend-live-verification-20261116T184056Z.json. Later local browser checks
loaded AAPL indicators and selected MSFT against the imported snapshot.

## Source-file audit

The inspection scanned all rows, not only the first sample. Results apply to the file hash above.

| Item | Observed value |
| --- | --- |
| Total records | 2,947,953 |
| Distinct tickers | 494 |
| Earliest date across all symbols | 2000-01-03 |
| Latest date across all symbols | 2026-11-12 |
| Duplicate ticker/timestamp pairs | 0 |
| Adjacent ticker/timestamp ordering violations | 0 |
| Non-midnight timestamps | 0 |
| Timestamp timezone | None specified in the Arrow schema |

### Columns

| Column | Arrow type | Intended meaning to verify |
| --- | --- | --- |
| date | timestamp[ms] | Trading-session date stored at midnight; timezone/calendar not documented |
| ticker | large_string | Stock symbol; exchange and company-name metadata absent |
| open, high, low, close | double | OHLC price values; adjustment convention unconfirmed |
| adj_close | double | Adjusted close; formula and point-in-time behavior unconfirmed |
| volume | int64 | Reported trading volume; adjustment convention unconfirmed |
| dividends | double | Corporate-action information; units/semantics unconfirmed |
| stock_splits | double | Corporate-action information; split representation unconfirmed |
| bad_bar | bool | Quality flag; generating rule not supplied |

Do not assume the 494 symbols are a historical S&P 500 universe, all US stocks, or free of selection/survivorship bias. The universe-selection process is unknown.

### Example symbol coverage

| Symbol | Records | First date | Last date |
| --- | --- | --- | --- |
| AAPL | 6,757 | 2000-01-03 | 2026-11-12 |
| MSFT | 6,757 | 2000-01-03 | 2026-11-12 |
| NVDA | 6,728 | 2000-02-14 | 2026-11-12 |
| GOOGL | 5,595 | 2004-08-19 | 2026-11-12 |
| AMZN | 6,757 | 2000-01-03 | 2026-11-12 |
| TSLA | 4,120 | 2010-06-29 | 2026-11-12 |

Different histories are present. These counts do not establish complete trading-calendar coverage or listing-date correctness.

### Data-quality findings

| Check | Observed count |
| --- | --- |
| Null values in each of open/high/low/close/adj_close | 214 per column |
| bad_bar=true | 214 |
| Null volume | 37 |
| Null volume while bad_bar=false | 37 |
| Flagged rows or missing OHLC/volume, combined distinct rows | 251 |
| Open outside reported low/high range | 1 additional unflagged row |
| High below low | 0 among non-null comparisons |
| Close outside reported low/high range | 0 among non-null comparisons |
| Nonpositive close or adjusted close | 0 among non-null comparisons |
| Negative volume | 0 among non-null comparisons |
| Nonfinite numeric values | 0 among non-null values |
| Nonzero dividend records | 34,393 |
| Nonzero split records | 582 |
| close different from adj_close | 2,481,946 among non-null comparisons |

Null date/ticker/dividends/stock_splits/bad_bar counts were zero. Missing values are separate from the nonfinite checks; a zero nonfinite count does not mean the columns have no nulls.

Concrete OHLC anomaly: HUBB, 2021-05-05. Open `195.97999572753906`, low `196.2100067138672`, high `198.63999938964844`, close `198.1300048828125`, volume `127234`, bad_bar=false. Open is below low. The current database's OHLC constraints reject this row.

The filename and bad_bar flag are insufficient import validation: 37 missing-volume records and this OHLC anomaly are not covered by that flag. Do not invent replacement volume, forward-fill OHLC, or silently alter the anomalous price.

### Remaining provenance and ML questions

1. Yahoo Finance is team-reported provenance; what download date, reproducible source and permitted-use/caching/redistribution policy apply?
2. Can he provide the download/cleaning script and original input or reproducible source reference?
3. What exactly makes bad_bar true, and were invalid values deliberately nulled instead of removed?
4. Are OHLC and volume raw, split-adjusted, or otherwise transformed? How is adj_close calculated?
5. What do dividends and stock_splits encode, and which exchange calendar/currency applies to each symbol?
6. How were the 494 symbols selected? Does the file exclude delisted companies or use today's constituent list?
7. Why does NVDA coverage begin on the listed date, and are missing sessions expected elsewhere?
8. How should historical corrections and future updates be reproduced?

No answers are established merely by this file's column names or writer metadata.
