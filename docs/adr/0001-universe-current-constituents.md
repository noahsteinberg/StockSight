# ADR-0001: ML universe: current S&P 500 constituents

**Date**: 2026-11-13
**Status**: accepted
**Deciders**: ML team, drafted with Claude Code

## Context

The model needs a fixed, reproducible set of stocks with daily history from 2000. Free point-in-time S&P 500 membership history is not readily available, while the current constituent list (with GICS sectors) can be scraped from Wikipedia. Tickers with very short histories add little training data and make chronological splits uneven.

## Decision

We use the current S&P 500 constituents (fetched by `stocksight_data.universe`) and keep only tickers with at least 756 cleaned rows (~3 years). This gives 494 tickers for the 2026-11-12 snapshot. SW is excluded by this rule after its stale pre-listing history is trimmed (592 real rows); it returns automatically once it has enough history.

## Alternatives Considered

### Alternative 1: Point-in-time historical membership
- **Pros**: Removes survivorship bias; matches what was investable at each date.
- **Cons**: Needs a membership history source and prices for delisted companies, which Yahoo often lacks.
- **Why not**: Not feasible with free data in this course timeline.

### Alternative 2: Keep all tickers regardless of history length
- **Pros**: Includes recent IPOs and spin-offs.
- **Cons**: Tickers with weeks or months of data cannot contribute to all splits and need many warm-up rows.
- **Why not**: Little benefit for a daily direction model.

## Consequences

### Positive
- Simple, reproducible universe with sector metadata.

### Negative
- **Survivorship bias**: every stock in the data survived into today's index, so historical up-rates and any backtest look better than reality. Results must state this.
- The universe changes whenever the index changes; each dataset snapshot must record its `tickers.csv`.

### Risks
- Overstating model quality. Mitigation: report the bias next to every metric and compare models only against baselines on the same universe.
