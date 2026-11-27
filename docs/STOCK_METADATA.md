# Company names and sectors

Issue #19 phase 3. StockSight shows a company name, GICS sector and GICS
sub-industry for each supported stock. They come from one reviewed, static file,
not a live feed:

- **Data:** `backend/app/fixtures/stock_metadata.csv` (columns `symbol`,
  `company_name`, `sector`, `sub_industry`; 494 rows).
- **Loader and rules:** `backend/app/stock_metadata.py`.
- **Rebuild script:** `backend/app/build_stock_metadata.py` (offline).

## Source and licence

[Wikipedia, "List of S&P 500 companies"](https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&oldid=1384572480),
pinned to revision 1384572480 (November 8, 2026). It was retrieved through the
MediaWiki API on November 24, 2026. The page text is CC BY-SA 4.0; the CSV is an
adaptation of its constituents table and is shared under the same licence, with
this attribution. The sector and sub-industry columns use the GICS taxonomy as
listed by that page. GICS is a classification system of MSCI and S&P Global, and
StockSight doesn't use MSCI's own data feed.

The API returns these source facts with `GET /api/sectors` and each stock
profile, and the Explore page and Methodology page link to the revision.

## Coverage and honesty rules

- All 494 supported tickers matched, including the share classes `BRK-B`
  (`BRK.B` in the source) and `BF-B`, and `CBOE` (a different template in the
  source). Nine source rows aren't in our price snapshot and were left out.
- Each sector must be one of the 11 GICS sectors; anything else is rejected
  rather than shown. In this revision, the EME row had a doubled cell separator
  on one line. The parser splits on every separator, so EME is correctly
  Industrials / Construction & Engineering.
- A supported stock missing from the file shows "Sector unknown", and its name
  falls back to a stored name only when that name isn't the importer's
  ticker placeholder. Nothing is inferred from a ticker.
- The database's `stocks.name`/`exchange` columns are **not** rewritten, and
  there's no migration. The file is read at startup and joined in Python, which
  the product plan allows for a reviewed static map. A `catalog_metadata` table
  can replace it later without changing the API.
- Exchange stays unknown in Explore. PR #16's TradingView listing map is a
  widget routing aid, not verified catalog metadata.

## Refreshing the file

1. Save the API response for a chosen revision:
   `https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles=List_of_S%26P_500_companies&rvprop=ids|timestamp|content&rvslots=main&format=json&formatversion=2`
   (add `&rvstartid=<revid>&rvlimit=1` to pin one).
2. Export the supported symbols, one per line (`select symbol from price_series`).
3. Run `python -m app.build_stock_metadata page.json symbols.txt
   app/fixtures/stock_metadata.csv`. It prints the revision and any symbols that
   are missing or have invalid sectors.
4. Review the CSV diff, then update `SOURCE` in `app/stock_metadata.py` and the
   counts in `tests/test_stock_metadata.py`. Run the backend tests.

The November 24 file was rebuilt with this script and was byte-identical to the
reviewed copy.

## Review status

Pending Parth's review of the source choice, as the product plan asks. Until
then, sectors are descriptive labels for filtering, not recommendations.
