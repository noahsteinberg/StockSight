# Import the team historical dataset

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

The agent's sandbox cannot access Docker's named pipe or the database, even when
Docker Desktop is open. Running this command in a normal developer terminal is
required in that environment. Its safeguards have local automated coverage;
live PostgreSQL completion is pending until an actual success report exists.

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
The agent cannot start/access Docker in this session, so the normal PostgreSQL
import and browser acceptance steps remain outstanding.
