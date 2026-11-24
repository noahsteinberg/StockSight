# Yahoo Finance investigation for Parth

November 23 implementation follow-up: [DAILY_REFRESH.md](DAILY_REFRESH.md)
documents the separate updater, isolated evidence and hosted rollout status.
The historical investigation below records earlier findings and proposed rules;
it is not the current delivery checklist. Hosted refresh verification is recorded
in the daily guide and current handoff; nightly scheduling remains disabled.

Prepared November 16, 2026. The meeting assigned research into fresh Yahoo Finance
data, with the existing stored snapshot kept for the current presentation.
This document is an integration proposal, not a running refresh service.

## November 23 API comparison

Parth wants fresh completed daily history plus latest available quotes. He has
no market-data API account yet and chose to finish the file migration first.
No provider key, scheduled job or quote endpoint has been configured.

Alpaca is the leading technical candidate for a private research pilot. Its
[Basic plan](https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api)
provides 200 historical calls per minute, history since 2016 and IEX-only live
equity data. It requires a key ID and secret, stored only on the server. The
[official FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) distinguishes
IEX from consolidated SIP: free historical SIP queries must end at least
15 minutes ago; latest SIP endpoints require a subscription. Use an explicit
feed and show its timestamp/coverage. IEX represents one exchange, so its prices
and volume must not be treated as consolidated market data.

[Twelve Data Basic](https://twelvedata.com/pricing) offers 8 credits per minute
and 800 per day, with internal non-display usage. That daily quota leaves little
room for separate daily-history and quote requests for 494 symbols. Public
StockSight display also needs a provider plan or permission that covers the
actual audience; confirm that before activating a public feed. Alpaca's
[data terms](https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf)
need the same review. These are candidates, not an approved public-data license.

For the next implementation, compare overlapping daily bars with the team Yahoo
snapshot before deciding whether to replace or extend its canonical series.
Keep latest bid/ask/trade quotes in a separate timestamped contract rather than
overwriting a completed daily close. Refresh outside browser requests, retain
up to the agreed hosted history limit, and preserve the prior success date on
provider failure. The incremental writer and provider-series provenance remain
unfinished.

## Finding

The practical Python research option is the community `yfinance` package. Its
basic `Ticker.history`/`download` path retrieves Yahoo data without a paid API key.
It is not an official Yahoo SDK or a guaranteed production market-data service.
The maintainers describe it as a research/educational tool and identify personal
use restrictions for Yahoo's API. A public website's caching/redistribution rights
need review before selecting it as a production feed.

Start with **completed daily sessions** for this next-session prediction project.
Daily history is distinct from streaming real-time quotes. Do not label a cached
daily close or an unfinished current-day bar as a live price.

## Existing API contract

| Frontend request | Current source and behavior |
| --- | --- |
| `GET /api/stocks?query=AAPL` | Searches supported stored symbols/names; at most 50 results |
| `GET /api/stocks/AAPL/prices?range=3mo` | Reads stored OHLCV and series provenance; latest 63 stored sessions |
| `GET /api/stocks/AAPL/indicators?range=3mo` | Computes backend SMA20/RSI14 from stored close, then trims display |

Preserve these routes. Browser requests should keep reading PostgreSQL rather
than synchronously downloading Yahoo history. `as_of` must stay the latest stored
session, not the server clock. Search currently covers the stored universe; the
meeting's "any stock" goal requires an explicit later symbol-onboarding contract.

## Provider request and mapping

Use explicit options because yfinance defaults to adjusted OHLC:

The read-only feasibility check used an isolated environment with
`python -m pip install yfinance==1.8.0`; it did not add provider dependencies to
the API runtime. That version returned five observations each for AAPL and MSFT,
November 9–13, with unique ascending dates, America/New_York session timezone,
and no missing OHLCV/adjusted-close values. No database was updated.

```python
import yfinance as yf

yf.config.debug.hide_exceptions = False  # surface download failures (yfinance 1.8.0)
frame = yf.Ticker("AAPL").history(
    start="2026-11-09",        # inclusive
    end="2026-11-14",          # exclusive; fixed completed sessions for research
    interval="1d",
    auto_adjust=False,
    back_adjust=False,
    actions=True,
    repair=False,
    keepna=True,
    timeout=15,
)
```

No key is supplied for this history path. This example downloads into memory and
does not update StockSight. A scheduled implementation must derive its cutoff
from the agreed exchange calendar/timezone and data finalization policy.

| Provider field | Storage target |
| --- | --- |
| Exchange-local daily index date | `daily_bars.session_date` as a date |
| `Open`, `High`, `Low`, `Close` | OHLC rounded and validated as Numeric(18,6) |
| `Volume` | Nonnegative signed 64-bit integer |
| `Adj Close`, `Dividends`, `Stock Splits` | Auxiliary source values, preserved separately |

`auto_adjust=False` avoids yfinance's automatic dividend adjustment; it does not
establish that every underlying Yahoo value is untouched by splits. Record the
actual provider/options/version and verify adjustment meaning before training.
Never substitute adjusted close for the chart's close silently. Retain nulls for
validation, reject malformed/duplicate/out-of-order bars, and treat timezone
conversion as an explicit session-date policy.

## Recommended next implementation

1. Add a bounded offline download command with explicit symbols/date interval,
   provider version and request metadata. Save raw input and a hash outside Git.
2. Compare an overlap against the existing team snapshot before adopting it.
   Its historical adjustment/cleaning policy is still unverified. Use a separately
   versioned canonical series and an explicit reviewed replacement if conventions
   differ; never append incompatible prices to the old series.
3. For a verified matching provider series, update bars by `(series_id, session_date)`
   with idempotent correction-aware writes. Re-fetch a recent overlap, lock each
   symbol's update, and commit its bars/provenance/watermark together. A split or
   adjustment change may require a full versioned rebuild, not a short overlap.
4. Apply bounded timeouts/retries with backoff. A failed or empty symbol download
   must retain its prior data date and success marker. Keep per-symbol failure
   evidence and continue serving clearly dated stored history.
5. Schedule after finalized trading sessions through the backend hosting platform.
   Do not refresh all 500 stocks inside a browser request or train on every fetch.
   Begin with a few symbols and expand only after rate/capacity checks.

The current `app.import_prices.write_symbol` deliberately replaces a complete
symbol snapshot. It deletes old bars inside that symbol's transaction. **Do not
pass a five-day download to it as an incremental update**: that would replace the
entire history with five days. An incremental writer and ingestion-state records
are separate future work.

Fresh downloaded bars, model training and model evaluation are separate steps.
No direction, confidence, risk score or model accuracy follows from Yahoo quotes.
No new prediction endpoint or automatic retraining is implemented here.

## Primary references

- [yfinance maintainers' README and usage boundary](https://github.com/ranaroussi/yfinance/blob/main/README.md)
- [Ticker.history](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)
- [Download options, adjustment defaults, inclusive start/exclusive end](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html)
- [Existing StockSight import contract](PRICES_IMPORT.md)

Read-only provider feasibility results, when run, belong in CURRENT_HANDOFF.md;
they do not prove scheduled ingestion or storage integration.
