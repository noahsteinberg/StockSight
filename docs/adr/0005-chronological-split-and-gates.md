# ADR-0005: Chronological split, 5-session purge, block bootstrap and frozen gates

**Date**: 2026-11-14 (revised for the 5-session target; first drafted 2026-11-13)
**Status**: proposed
**Deciders**: ML team (pending review), drafted with Claude Code

## Context

Random splits on stock time series leak future information. With a 5-session target (ADR-0004), a label near a split boundary depends on prices inside the next split, and adjacent labels share 4 of 5 return days, so rows are neither independent across tickers on a date nor across nearby dates. The naive edge is tiny (validation reversal 5d: 0.5048 balanced accuracy), so success criteria must be fixed before any model is trained. See [prediction contract](../../ml/docs/prediction-contract.md), sections 3.5–5.

## Decision

Splits by `as_of_date`, identical for all tickers: train 2000-01-03 → 2018-12-31, validation 2019-01-02 → 2021-12-31, test 2022-01-03 → 2026-11-12. A row belongs to a split only if both t and t+5 are inside it (5-session purge: 2,370 rows before validation, 2,455 before test). Confidence intervals use a **moving-block bootstrap** over sorted dates (blocks of 10 sessions, all tickers of a date together, 1,000 draws). Gates, frozen once in `data/reports/gates_frozen.json` (tied to the dataset SHA-256): balanced accuracy > reversal 5d (0.50476) with the CI lower bound of **model − reversal 5d** > 0; accuracy ≥ always majority (0.5079); Brier < constant 0.4870 (0.24996); every validation year ≥ 0.50. A model and the baselines are scored on the same rows, with thresholds recomputed there by the frozen rules. Model selection happens with purged walk-forward inside train; validation is used once per finalist. The test end is pinned at 2026-11-12; test is evaluated once, at the end, to a separate report with an access log.

## Alternatives Considered

### Alternative 1: Random train/test split
- **Pros**: Simple.
- **Cons**: Leaks future regimes and overlapping label windows.
- **Why not**: Invalid for time series; forbidden by the specification.

### Alternative 2: Resample single dates (no blocks)
- **Pros**: Simpler; was used for the next-day target.
- **Cons**: Ignores the overlap between adjacent 5-day labels; the validation CI comes out 1.8× too narrow ([−0.0016, +0.0107] vs [−0.0067, +0.0156]).
- **Why not**: Would make noise look significant.

### Alternative 3: Walk-forward validation only
- **Pros**: Tests stability across regimes.
- **Cons**: More code and compute for a first model.
- **Why not**: Planned as a robustness check (with the same purge between folds), not the primary protocol.

## Consequences

### Positive
- No label crosses a split boundary; uncertainty estimates account for overlapping labels.
- Thresholds are fixed before training, so they cannot be tuned to a model.

### Negative
- Even the best naive baseline is not significant in validation, so the significance gate is demanding.
- Training metrics are optimistic because neighbouring rows are near-duplicates.

### Risks
- Peeking at test. Mitigation: test runs only with `--include-test`, once, and the result is recorded.
