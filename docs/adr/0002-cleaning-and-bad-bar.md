# ADR-0002: Price cleaning rules and the bad_bar contract

**Date**: 2026-11-13
**Status**: accepted
**Deciders**: ML team, drafted with Claude Code

## Context

The raw Yahoo bars contain several kinds of bad data found by `stocksight_data.check`: an unsettled latest bar, years of back-filled zero-volume history before real listings (SW, FERG, AMCR), isolated flat no-trade bars (ODFL, DECK, NDAQ, …), tiny split-adjusted early prices, and two bars that even `adj_close` cannot fix (EXPE 2011-12-21, JCI 2007-07-02). Silently deleting rows would hide date gaps and let downstream code compute returns across them.

## Decision

`stocksight_data.clean` builds `data/clean/prices_clean.parquet` from untouched raw files with ordered, counted rules: cutoff at `--end-date`; trim stale early history (trigger: >50% zero volume in the first 252 rows; start at the first 252-row run without zero volume; only reviewed tickers may be trimmed); trim leading `adj_close < 0.10`; and minimum history (ADR-0001). Known-bad bars and flat zero-volume bars keep their row but get NaN prices and `bad_bar = True`; zero-volume bars whose prices vary keep their prices and get NaN volume. Assertions block writing if any invariant fails.

## Alternatives Considered

### Alternative 1: Delete bad rows
- **Pros**: Simpler table with no NaNs.
- **Cons**: Gaps become invisible, so a "1-day" return can silently span several days or a level shift.
- **Why not**: Hides exactly the errors the next step must avoid.

### Alternative 2: Forward-fill bad prices
- **Pros**: No missing values.
- **Cons**: Creates fake zero returns and keeps distortions on either side of excluded bars.
- **Why not**: Invents data.

## Consequences

### Positive
- Every removal is counted in `clean_log.json`; raw data stays reproducible.
- **Contract for downstream code**: prices are NaN exactly on `bad_bar` rows; any return or feature window touching one is invalid and must be dropped, never filled.

### Negative
- 214 `bad_bar` rows and 37 NaN-volume rows that feature code must handle.
- 370 tiny-price rows remain mid-history (NFLX, NVDA, TSCO, MNST) by choice.

### Risks
- New stale tickers after an index change. Mitigation: `STALE_REVIEWED_TICKERS` makes the run fail until a human reviews the trim.
