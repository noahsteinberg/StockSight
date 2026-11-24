# Free market-price widget — Parth's November 23 update

## What changed

StockSight's Analysis page has a separate TradingView Single Ticker panel above
the historical chart. It follows the selected stock and shows the provider's
price and daily change. TradingView's logo/link remain visible,
with an additional attribution link and a clear notice that prices may be delayed.
There is no paid subscription, API key or account setup in this integration.

The historical chart, indicators, watchlist changes and CSV still use StockSight's
stored daily prices. The hosted file import ends **November 12, 2026**. Widget
prices do not extend that history or become model-training data. This change
adds a newer price display; it does not implement daily database refresh.

Alpaca's automated support response did not grant free public-display/caching
permission for Basic/Paper data. We therefore kept its API checks private and
used a widget intended for public embedding. No Alpaca prices were published
or written to the shared database. Do not turn on public Alpaca refresh without
the required permission.

## How it works

- `frontend/src/MarketQuote.jsx` creates TradingView's official Single Ticker
  embed. Each mount/retry owns one container; changing stocks removes the old
  iframe and script. Changing history ranges leaves the widget in place.
- A failed script or a script that creates no frame within 12 seconds offers
  Retry and a link to the provider. Vendor-rendered unsupported-symbol or
  no-data messages remain visible inside the widget. An iframe's existence
  does not prove price availability; we do not inspect or extract its prices.
- `frontend/src/tradingview-symbols.js` maps the 494 imported tickers to listing
  exchanges checked on November 23: 158 NASDAQ, 335 NYSE and one CBOE listing.
  `BF-B` and `BRK-B` explicitly become `NYSE:BF.B` and `NYSE:BRK.B`. Unknown
  tickers show an unavailable state instead of guessing a market.
- The map was matched against Nasdaq Trader's `nasdaqlisted.txt` and
  `otherlisted.txt` directories, excluding test issues. CBOE's TradingView
  listing was checked separately. These are listing identifiers, not prices.
  Recheck this map when stocks change listing venue or the imported universe
  changes. Database company/exchange metadata is not altered by this UI change.
- The browser contacts TradingView directly using its standard embed. The
  provider receives the normal embed request, including the selected symbol
  and referring page. Backend credentials are never passed to it.

## Checks

The automated widget tests use an explicitly mocked vendor script to check
stock changes, share classes, cleanup, history-range independence, failed-script
recovery and a 320px layout. They do not establish actual vendor data coverage.
Real-browser checks of the official widget are recorded in CURRENT_HANDOFF.md.

## Official references

- [Single Ticker widget](https://www.tradingview.com/widget-docs/widgets/tickers/single-ticker/)
- [Official Single Ticker embed script](https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js)
- [Free website widgets](https://www.tradingview.com/widget/)
- [Official Single Ticker embed example and dynamic symbols](https://www.tradingview.com/widget-docs/tutorials/iframe/build-page/dynamic-symbols/)
- [Data FAQ: delays, restricted symbols and no raw-data API/export](https://www.tradingview.com/widget-docs/faq/data/)
- [General FAQ: attribution and widget behavior](https://www.tradingview.com/widget-docs/faq/general/)
- [Nasdaq directory definitions](https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs)
- [Nasdaq listings](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt)
- [Other exchange listings](https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt)
- [TradingView's CBOE listing](https://www.tradingview.com/symbols/CBOE-CBOE/)
