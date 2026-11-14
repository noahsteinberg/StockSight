# ADR-0006: Point-in-time feature design and train-only selection

**Date**: 2026-11-14
**Status**: proposed
**Deciders**: ML team (pending review), drafted with Claude Code

## Context

The target (ADR-0004) is a small, decaying relative signal, so leakage of any kind would dominate results. Yahoo prices are back-adjusted (ADR-0003), the universe is today's constituents (ADR-0001), and labels overlap (ADR-0005). The feature set must be broad enough to explore, while being provably point-in-time and easy to extend safely. See [ml/docs/features.md](../../ml/docs/features.md).

## Decision

- **A registry.** Features live in `stocksight_data/features.py` (`FEATURES`), each with a lookback, family, scope, hypothesis and caveat.
- **One validity rule.** A feature is valid only when rows t-L..t are clean, consecutive sessions of the same ticker. This is implemented once as a clean-run length. Rolling is per ticker.
- **Ratios, ranks and returns only.** The one exception is split-invariant dollar volume, used only as a rank. Cross-day OHLC comparisons are rescaled by the day's adjustment factor. Oscillators use simple moving averages.
- **Generic tests cover every registry entry:** warm-up, bad bars, exact invariance to future data, price-level invariance, and back-adjustment invariance.
- **A default model set** (`model_features()`) excludes market-state features and survivorship-suspect size/liquidity ranks.
- **Univariate screening uses train only**, with labels computed from prices cut at the train end, block-bootstrap CIs, and Benjamini-Hochberg false-discovery control.

## Alternatives Considered

### Alternative 1: A technical-analysis library (TA-Lib, `ta`)
- **Pros**: Many indicators for free.
- **Cons**: EMAs with unbounded memory, implicit NaN filling, no `bad_bar` or session-gap awareness, and price-level outputs.
- **Why not**: Leakage and validity can't be guaranteed or tested per feature.

### Alternative 2: Rank-transform every feature
- **Pros**: Robust to tails; matches the relative target.
- **Cons**: Loses magnitude information that trees can use; fixes the transform before modelling.
- **Why not**: Left to the modelling step, fitted on training folds.

### Alternative 3: Include size/liquidity in the default set
- **Pros**: The strongest-looking univariate signals.
- **Cons**: Their train IC partly reflects selection on the outcome (today's small members were yesterday's winners).
- **Why not**: Kept available, but only as an explicit, recorded experiment.

## Consequences

### Positive
- Any new feature is tested automatically. Six planted bugs and a brute-force recomputation on real data confirm that the tests have teeth.
- Screening never reads validation or test outcomes.

### Negative
- Strict windows drop each ticker's first year for long-lookback features (coverage 0.94–1.0).
- The 535 MB feature file is not in git; it is rebuilt from the cleaned data in about a minute.

### Risks
- Survivorship affects the labels as well as the flagged features. All results stay conditional on today's survivors.
