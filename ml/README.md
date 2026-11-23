# StockSight ML research

The project has offline research evidence and no approved serving model.
The [current handoff](../docs/CURRENT_HANDOFF.md) tracks whether research is
active. Product architecture and promotion gates are documented in the
[ML product integration plan](../docs/ML_PRODUCT_INTEGRATION_PLAN.md).

## Frozen results

- [Open-source model audit](docs/OPEN_SOURCE_MODEL_AUDIT.md)
- [Next-session model round](docs/NEXT_SESSION_ROUND2_RESULTS.md)
- [Continuous-target experiment protocol](docs/NEXT_SESSION_TARGET_ROUND.md)
- [Continuous-target results](docs/NEXT_SESSION_TARGET_ROUND_RESULTS.md) and
  [paired ranking review](docs/NEXT_SESSION_TARGET_ROUND_REVIEW.md)

The earlier five-session relative classifier and confidence-filter follow-up
did not qualify for promotion. The next-session work did not improve absolute
direction enough to qualify either. Excess-return ranking remained weak and
positive in six development folds, with later-period decay. The paired review
records uncertainty and publication timing limits.

## Evaluation and reproducibility

The supplied snapshot's hash, adjustment and coverage limits are documented in
[the import guide](../docs/PRICES_IMPORT.md). Development target dates end
2018-12-31. Next-session 2019-2021 access requires a recorded candidate-selection
protocol. Preserve the record of earlier five-session validation access.
Final 2022-01-03 through 2026-11-12 remains reserved.

Define the target, cutoff, calendar and adjustment policy before any fit. Keep
features past-only, fit preprocessing only on training folds, and purge labels
that cross split boundaries. Use the same observations for model and baseline
comparisons. Version feature and model conventions, including any use of
[SMA20/RSI14](../docs/INDICATORS.md). Keep training offline and load artifacts
only from trusted sources.

## Reproducing the research

Research branches preserve complete source/history:

- research/ml-round2: c983860, five-session and confidence follow-up.
- research/next-session-direction: 8dbae2a, original next-session pipeline.
- research/next-session-market-models: 531db99, market/model round.
- research/next-session-targets: a67e642, continuous round and paired review.

Main carries OPEN_SOURCE_MODEL_AUDIT.md, NEXT_SESSION_ROUND2_RESULTS.md,
NEXT_SESSION_TARGET_ROUND.md, NEXT_SESSION_TARGET_ROUND_RESULTS.md,
NEXT_SESSION_TARGET_ROUND_REVIEW.md and three corresponding JSON reports under
ml/reports. These reports are frozen evidence; old source worktree locations
remain historical. Do not merge research branches wholesale: they contain old
application files. Port needed research modules later through a focused PR.

Git intentionally excludes data, checkpoints, environments and secrets. Another
machine needs an authorized transfer of clean/prices_clean.parquet,
features/features.parquet, the complete next-session frame/manifest/prepared
metadata and six HGB parquet/JSON predictions. Transfer target checkpoints,
manifests and attempts for saved-result auditing. Verify hashes; do not silently
download/rebuild and call it the same snapshot. The launcher assumes Noah's
sibling/worktree layout. A different layout must explicitly configure
STOCKSIGHT_DATA_DIR, STOCKSIGHT_PRIOR_NEXT_DIR and STOCKSIGHT_TARGET_DIR and use
the pinned research environment. Frozen manifests reject source/package drift.

## Next research checkpoint

Audit saved rankings for stock/day concentration, turnover and realistic
publication/next-available entry timing. Audit OHLC adjustment/alignment first.
No broad model sweep or confidence-cutoff tuning. If this survives, predeclare
candidate/comparator/metrics before protected scoring. Otherwise emphasize
descriptive risk/education. Qlib motivated continuous/ranking targets; MASTER
motivated market context, not copied weights or a reproduced transformer.
