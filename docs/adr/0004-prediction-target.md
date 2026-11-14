# ADR-0004: 5-session market-relative target

**Date**: 2026-11-14 (supersedes the 2026-11-13 next-day direction draft)
**Status**: proposed
**Deciders**: ML team (pending review), drafted with Claude Code

## Context

The first draft predicted next-day up/down. That target is dominated by the market's daily move: a model can look skilled just by guessing the overall direction, and the best naive edge (1-day reversal) is largely bid-ask bounce. For a stock-analysis app, "which stocks will do better than the rest" is a more useful and less noisy question. See [prediction contract](../../ml/docs/prediction-contract.md), sections 2 and 3.2.

## Decision

For each `(ticker, t)`: `r5 = adj_close[t+5] / adj_close[t] - 1` (t+5 = 5th NYSE session), `excess = r5 - market_r5`, where `market_r5` is the equal-weight **mean** of r5 across valid tickers on t (`MARKET_BENCHMARK`, switchable to median). Label 1 if excess > 0, 0 if < 0, tie (`<NA>`) if exactly 0. A row is valid only with rows on all 6 sessions t..t+5, no `bad_bar` in them and closes at both ends; dates need ≥ 150 valid tickers (`MIN_TICKERS_PER_DATE`; currently drops none, minimum is 340).

## Alternatives Considered

### Alternative 1: Next-day direction (previous draft)
- **Pros**: Simple; matches the original specification wording.
- **Cons**: Mostly predicts the market, not the stock; reversal baseline is microstructure noise.
- **Why not**: Replaced by team decision.

### Alternative 2: Median benchmark
- **Pros**: Exactly ~50/50 classes.
- **Cons**: Not the return of any portfolio; harder to explain as "beating the market".
- **Why not**: Kept as a config switch; the mean gives a 48.7% train beat-rate, which the always-majority baseline handles.

### Alternative 3: Cap-weighted index (e.g. SPY)
- **Pros**: The familiar "market".
- **Cons**: Needs another data source and market caps; dominated by a few mega-caps.
- **Why not**: The equal-weight universe is self-contained and consistent with the training universe.

## Consequences

### Positive
- The market-wide move cancels out: excess averages to exactly zero on every date.
- Validity rules are strict and tested (window gaps, `bad_bar`, sparse dates).

### Negative
- Adjacent labels share 4 of 5 return days, so they are autocorrelated; evaluation needs a block bootstrap and a 5-session purge (ADR-0005).
- Classes are slightly imbalanced (train 48.7% beat).

### Risks
- Off-by-one or leakage in the window. Mitigation: tests for t+5 across holidays/weekends and mutation checks (t+1 fails 10 tests).
