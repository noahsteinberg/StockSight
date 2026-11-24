# Parth's database and stock-data update

November 23, 2026

## What I worked on

I moved the team's historical stock data into our shared Supabase database so
the website can use all 494 stocks in the file. I also added an import option
that lets us keep a useful amount of history within the free database limit,
checked the uploaded data, and researched an API for future updates.

This work uses the team's existing `prices_clean.parquet` file and StockSight
application. The file was supplied by the team; this update records my database,
import and verification work.

## What changed

| Item | Before this update | After this update |
| --- | --- | --- |
| Stocks in the hosted database | AAPL demo only | All 494 tickers from the file |
| Daily price records | 506 | 1,214,087 |
| Latest stored date | February 16, 2017 | November 12, 2026 for every ticker |
| History stored per stock | Small demo | Up to 2,500 latest valid trading days |
| Database size after the import | — | 326,137,523 bytes, about 326 MB |

A daily price record contains one stock's opening, highest, lowest and closing
price, plus its trading volume for that day. Stocks with shorter histories keep
all their valid records: 29 tickers have fewer than 2,500.

## Why I used 2,500 trading days

Our Supabase project is on the free plan with a 500 MB database limit. I first
tested a small Microsoft import and measured its storage use. That suggested
the complete history for every stock would take roughly 700 MB, above the limit.

I chose to include every ticker and keep its latest 2,500 valid trading days,
roughly ten years. The website's Max chart displays up to 2,000 days; the extra
stored history helps calculate indicators before the visible chart begins.
The complete original file remains unchanged outside GitHub for research and
any later full-history import.

## How I checked the file and upload

1. Checked that the file matched the team's recorded SHA256 fingerprint. This
   fingerprint identifies the exact file used.
2. Validated all 2,947,953 source rows. There were 2,947,701 accepted rows and
   252 rejected rows. Rejected rows included missing values, flagged bad data
   and an inconsistent price range; I did not invent replacement values.
3. Backed up the old AAPL history before replacing the demo, then imported the
   latest accepted history for each ticker. Rejected rows do not use up the
   2,500-day allowance.
4. Compared the stored count, first date, last date and source fingerprint for
   every one of the 494 tickers against the import plan. They all matched.
5. Checked all 252 rejected ticker/date combinations and confirmed none were
   stored in the database.
6. Checked prices and SMA20/RSI14 indicators for AAPL, MSFT, NVDA, ABNB, BRK-B,
   HUBB and ZTS in all four chart ranges. These checks ran against both a real
   local API server and the deployed website: 56 price/indicator pairs passed.
   Prices matched the source file, and prices and indicators used matching
   data snapshots.
7. Confirmed the database access protections remained in place on all seven
   app/version tables. Anonymous and ordinary Supabase browser roles have no
   direct table read/write privileges. Account, session and watchlist table
   counts were unchanged by the import.

The November 23 backend run passed **107 tests**, with **2 disposable-PostgreSQL
tests skipped**. Python lint and formatting checks also passed. Frontend lint
and the production build passed before sharing the code. Real hosted
database and HTTP checks are separate evidence from those automated tests.
Raw local reports and the old AAPL backup stay outside GitHub; this note records
the results without publishing credentials or account data.

Source file fingerprint:

```text
ee0b2ed66c8abb87e0cf36798a32258bc902c0e1687ddee2a485c80b44216e89
```

## Code and notes included for the team

- [Import code](../backend/app/import_prices.py): adds
  `--max-bars-per-symbol 2500`. Full-history import remains the default when
  this option is omitted. Validation totals and stored totals are reported
  separately, and the stored source description includes the history limit.
- [Import preview](../backend/app/migration_plan.py): checks a file and the
  existing database, shows which stocks would be added or replaced, and gives
  a storage estimate without writing to the database.
- [Import tests](../backend/tests/test_import_prices.py) and
  [preview tests](../backend/tests/test_migration_plan.py): cover invalid rows,
  keeping the latest valid days, repeat imports, source checks and replacement
  safeguards.
- [Import guide](PRICES_IMPORT.md), [Supabase guide](SUPABASE.md) and
  [current handoff](CURRENT_HANDOFF.md): explain how the team can continue.
- [API research](YAHOO_FINANCE.md): records options for fresh daily history and
  latest quotes, including feed coverage and public-display requirements.

## How teammates can see the result

Open [StockSight](https://stocksight-rose.vercel.app), refresh the page and search
for a ticker such as MSFT, NVDA, AMZN or ABNB. Use the Search action if a ticker
does not appear in the suggested list. The search API returns at most 50 matches
at once, so a broad search is not the complete list of 494 stocks.

For a direct check, open the public
[MSFT price response](https://stocksight-rose.vercel.app/api/stocks/MSFT/prices?range=1mo).
It reports `historical_snapshot` and `as_of: 2026-11-12`. The website already
reads the updated shared database; the GitHub branch shares the import code,
tests and explanation with the team.

## What comes next

The current data is historical and ends November 12, 2026. Automatic daily
updates and live quotes are still future work. Alpaca is a candidate for a
private API pilot; we still need an account and a feed whose display terms fit
our website. Before adding new data, we also need to compare its price basis
with the team's Yahoo snapshot and build an update process that preserves
history. The existing snapshot importer replaces a stock's history, so it must
not be used as a short-window daily updater.

The file's price-adjustment convention is still unverified. Company names and
exchange information are also incomplete, and USD is an assumption from the
team's US-stock scope. This migration expands the stored data available to the
app; model training and evaluation remain separate team work.
