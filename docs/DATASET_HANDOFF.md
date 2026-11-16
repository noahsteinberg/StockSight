# StockSight dataset integration handoff

Updated November 16, 2026. Current application context is in
[CURRENT_HANDOFF.md](CURRENT_HANDOFF.md); import commands and replacement policy
are in [PRICES_IMPORT.md](PRICES_IMPORT.md). This file records data evidence, not
instructions to reimport an already completed snapshot.

## Current imported state

The PostgreSQL snapshot import completed through the approved execution path:
2,947,701 accepted bars across 494 symbols, 252 quarantined without repairs.
Stored counts/source hashes matched validation; restart persistence and real HTTP
search/history were verified. The source was unchanged when the continuation
reran the already completed import under explicit per-symbol replacement policy.
No further reimport is needed for account/session or indicator work.

Migrations now include `0004_app_sessions`; market data survived account/session
upgrades unchanged. The latest indicator phase confirmed the same market counts
and two watchlist entries. AAPL/MSFT each used 6,757 calculation observations and
returned date-aligned, range-stable indicators through the normal HTTP API.
See INDICATORS.md for that evidence; earlier test counts are historical.

The frontend supports imported symbol search/history with actual provenance,
`historical_snapshot` mode, Max=2,000 and has_earlier. Explicit offline fixture
mode remains AAPL-only with 506 bars. SMA20/RSI14 backend is implemented; frontend
indicator integration is pending and redesign is deferred.

The team identifies Yahoo Finance as source and S&P 500 stocks as intended scope.
That does not verify historical constituent membership, cleaning, permitted use,
adjustment semantics or ML suitability. USD is assumed; missing company/exchange
metadata is not fabricated. Auxiliary source values are preserved in JSON, while
chart/indicator input remains stored close. Live refresh is not implemented.

Do not seed the Plotly fixture over imported AAPL, delete volumes, or change
canonical histories as a troubleshooting step. Data/credentials/local evidence
stay ignored. The source file and database are local resources, not part of a
Git checkout or guarantee about another conversation's runtime access.

## Input file

Shared by Vlad; supplied by Gavin for inspection.

- Local path: `C:/Users/gavin/Downloads/prices_clean.parquet`.
- Size: 80,913,745 bytes, approximately 81 MB decimal.
- SHA256: `EE0B2ED66C8ABB87E0CF36798A32258BC902C0E1687DDEE2A485C80B44216E89`.
- Format: Apache Parquet; three row groups.
- Writer metadata: `parquet-cpp-arrow version 26.0.1`. This identifies the writer, not the upstream market-data provider.
- Metadata contained pandas/Arrow schema information but no explicit provider/provenance field was observed.
- The file stays outside Git. `*.parquet` and dataset directories are ignored; do not remove those protections or commit the 81 MB input.

Parquet is a compressed table format, not a database or trained model. The file appears suitable as a historical-data candidate; it does not itself implement future updates.

## Verified contents

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

## Data-quality findings

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

## Remaining provenance and ML questions

1. Yahoo Finance is team-reported provenance; what download date, reproducible source and permitted-use/caching/redistribution policy apply?
2. Can he provide the download/cleaning script and original input or reproducible source reference?
3. What exactly makes bad_bar true, and were invalid values deliberately nulled instead of removed?
4. Are OHLC and volume raw, split-adjusted, or otherwise transformed? How is adj_close calculated?
5. What do dividends and stock_splits encode, and which exchange calendar/currency applies to each symbol?
6. How were the 494 symbols selected? Does the file exclude delisted companies or use today's constituent list?
7. Why does NVDA coverage begin on the listed date, and are missing sessions expected elsewhere?
8. How should historical corrections and future updates be reproduced?

No answers are established merely by this file's column names or writer metadata.


## Implemented boundaries and evidence

- `backend/app/import_prices.py`: deterministic validation and bounded per-symbol
  import with explicit canonical replacement, quarantine and correction policy.
- `backend/app/db.py`: Numeric(18,6) OHLC, source_values, keys and constraints.
- `backend/app/repository.py`: bounded canonical history reads, including indicator
  calculation input; no whole-universe browser request.
- `backend/app/api/stocks.py`: explicit fixture/database selection and safe errors.
- `backend/app/indicators.py`: tested close-based SMA20/RSI14; no adjustment approval.
- `frontend/src/Analysis.jsx`: prices/volume, search, source/dates and bounded ranges.

Original full import evidence is ignored under
`.local-data/backend-completion-20261116T184037934756Z.json` and
`.local-data/backend-live-verification-20261116T184056Z.json`. The import phase
recorded 50 backend passes; the newer indicator suite records 95 passes with one
expected SQLite-only skip. Those are distinct dated runs, not additive counts.
Local reports need not exist elsewhere; use committed tests for reproduction.

The inspection metadata above describes the supplied source file, including
rejected rows, rather than claiming every source record was imported. PyArrow
is now deliberately pinned through requirements-import.txt. Browser/account
checks after the initial import are recorded separately in SESSION_HANDOFF.md.
