# StockSight dataset integration handoff

Prepared November 16, 2026. Starting application commit: `821288c` on `feature/frontend-redesign`.

## Immediate objective

Evaluate Vlad's historical dataset and prepare a separate, validated importer into the existing PostgreSQL foundation. Inspection is complete; the Parquet dataset has not been imported. Do not interpret this handoff as approval of its source, price-adjustment policy, or ML suitability.

## Current project state

- React/Vite renders historical AAPL prices/volume through FastAPI.
- PostgreSQL storage, SQLAlchemy models, Alembic migrations, and an explicit fixture importer are implemented.
- The existing fixture contains 506 AAPL bars from 2015-02-17 through 2017-02-16. Repeated imports update existing keys without duplicates.
- Explicit fixture mode remains available; database mode returns sanitized errors instead of silently falling back.
- Prior verification: 13 backend tests, seven browser tests against PostgreSQL, lint/format/build, and persistence after a container restart passed. These results predate integration of this new dataset.
- Provider ingestion, refresh scheduling, indicators, accounts/watchlists, and ML are still future work.
- Changes are committed locally. Pushing remains deferred at Gavin's request; do not push or merge without a new instruction.
- Operationally, Gavin is implementing frontend/backend integration. At his request, the existing ownership assignments in the project documentation remain unchanged. Do not wait for Noah to continue local implementation.

Related docs: [roadmap](ROADMAP.md), [database setup](DATABASE.md), [Phase 1](PHASE_1.md), and [review evidence](reviews/PHASE_1_ADVERSARIAL_REVIEW.md).

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

## Questions for Vlad before approving import

1. What is the upstream provider, download date, and applicable permitted-use/caching/redistribution policy?
2. Can he provide the download/cleaning script and original input or reproducible source reference?
3. What exactly makes bad_bar true, and were invalid values deliberately nulled instead of removed?
4. Are OHLC and volume raw, split-adjusted, or otherwise transformed? How is adj_close calculated?
5. What do dividends and stock_splits encode, and which exchange calendar/currency applies to each symbol?
6. How were the 494 symbols selected? Does the file exclude delisted companies or use today's constituent list?
7. Why does NVDA coverage begin on the listed date, and are missing sessions expected elsewhere?
8. How should historical corrections and future updates be reproduced?

No answers are established merely by this file's column names or writer metadata.

## Proposed implementation sequence

1. Add a read-only validation command that checks the input hash/schema, dates, ticker normalization, nulls, OHLC bounds, volume, and duplicate keys. Produce a summary and quarantine reasons without touching PostgreSQL.
2. Resolve provenance and adjustment conventions. Choose a canonical series policy before writing data. The existing price_series table permits one series per symbol, so importing AAPL over the existing Plotly series is not an automatic safe operation.
3. Preserve source precision until the conversion policy is defined. The dataset uses doubles with more than six decimal places; the current database stores Numeric(18,6). Validate OHLC again after rounding because conversion can change bounds.
4. Design storage for adjusted close and corporate actions, or explicitly defer those columns while preserving the original file. Add a reviewed Alembic migration if the agreed import needs new fields; do not silently discard metadata required for later research.
5. Implement a dry-run importer first, then bounded/chunked writes into a disposable database. Avoid a single multi-million-row SQL statement. Define atomicity and checkpoint behavior per symbol; a failed import must not be marked complete.
6. Quarantine or reject flagged, incomplete, and inconsistent records with counts/reasons. Keep the input unchanged. Any repair requires an explicit rule and provenance.
7. Test a small subset such as AAPL/MSFT/NVDA first. Verify no duplicates on repeat import, corrections on existing dates, rollback/resume behavior, source metadata, and parity between API responses and accepted rows.
8. Expand to the full accepted dataset after the small import passes. Reuse the browser/API response contract and retain visible source/date information.
9. Treat ongoing refresh as a separate ingestion task. This historical snapshot does not select or implement a live provider.

## Existing code boundaries to inspect

- `backend/app/db.py`: stocks, price_series, daily_bars, constraints, numeric precision.
- `backend/app/seed.py`: current atomic 506-row fixture upsert; a reference, not a scalable Parquet importer.
- `backend/app/market.py`: current fixture loader and historical response schemas.
- `backend/app/repository.py`: bounded newest-row queries, canonical series selection, symbol lookup.
- `backend/app/api/stocks.py`: fixture/database adapter selection and safe errors.
- `backend/migrations/`: explicit schema evolution.
- `backend/tests/test_database.py`: migration, repeat-import, correction, rollback, restart, and failure tests.
- `frontend/src/Analysis.jsx`: price/volume display, source/date labels, and range selection.

Important integration limits: API search is capped at 50 matches; all-history is capped at the most recent 2,000 sessions. Several supplied symbols have more than 6,000 observations. Decide whether to introduce pagination/date windows or label bounded history explicitly; never imply the entire dataset is displayed when it is not. History.mode currently only permits historical_fixture; a new dataset needs an agreed provenance/mode representation rather than reusing the Plotly label.

## Completion criteria for the next increment

- Provenance and adjustment policy recorded, or explicitly blocked pending answers.
- Deterministic validation summary tied to the input hash.
- Rejected/quarantined records counted by reason; no silent fabricated repairs.
- Import dry-run and disposable-database tests pass before modifying the demo's canonical data.
- Repeating import leaves row counts stable; corrections follow the declared policy.
- The API serves accepted rows with accurate source, dates, units, and bounded-coverage semantics.
- Browser search/chart tests pass for the supported imported subset.
- Large data and credentials remain outside Git; code/docs are committed locally and pushing stays deferred.

## Inspection environment and changes

Inspection used PyArrow 26.0.1 installed in a temporary directory, not added to project requirements. No application code, schema, or database data was changed for inspection. If Parquet ingestion is implemented, add and pin the reader dependency deliberately with tests. This handoff records observed file contents and proposed work only; it does not claim a successful import or validated predictive dataset.


## Follow-up integration work (November 16, 2026)

The stock-search/chart integration now consumes the existing stock-search route,
uses returned provenance labels, and displays bounded history explicitly.
History includes session_limit and has_earlier; the browser calls the `all`
range Max. See [Noah's review guide](FRONTEND_BACKEND_REVIEW.md) for the completed
integration scope, startup commands, and current verification evidence.

The Parquet inspection findings and import blockers above remain unchanged.
This increment does not import prices_clean.parquet, replace AAPL's canonical
series, or approve the unknown provider/adjustment policy.


## Publication authorization (November 16, 2026)

Gavin subsequently authorized verifying, committing, and publishing the integration
for Noah's review. The earlier push deferral is superseded for this review snapshot.
No merge or dataset import was authorized. See FRONTEND_BACKEND_REVIEW.md for the
local commit, publication blockers, and verification limits.
