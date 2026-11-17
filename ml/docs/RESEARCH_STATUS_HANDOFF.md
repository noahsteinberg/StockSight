# ML research handoff — paused November 17, 2026

Noah requested a pause and handoff. Do not launch training, downloads, protected
evaluation, artifact export or additional diagnostics until he resumes ML work.

## Research history and conclusion

Noah reproduced the five-session relative classifier, tested compact features,
recent training windows and market skew, then audited confidence filtering.
None qualified. Next-session research compared logistic regression/HGB,
calibration, market features, recency, deeper HGB, Random Forest and ExtraTrees.
No direction candidate qualified. See the preserved reports and open-source audit.

The final round tested continuous absolute-return HGB, excess-return HGB and a
Ridge market forecast added to excess HGB. Two HGB fits per fold produce three
outputs. No new dataset or feature families were introduced: 54 stock features
and seven audited past-only market features, six purged chronological folds.

| Method | Direction target | Accuracy | Balanced accuracy | Rank IC |
| --- | --- | ---: | ---: | ---: |
| Original binary HGB | Absolute | 52.239% | 51.275% | 0.02620 |
| Absolute-return HGB | Absolute | 52.242% | 50.769% | 0.02321 |
| Excess-return HGB | Relative | 50.844% | 50.664% | 0.02549 |
| Combined market/stock | Absolute | 51.601% | 50.028% | 0.02549 |

Always-up absolute accuracy is 52.074%. Absolute direction did not improve.
Relative outperform accuracy cannot be compared directly to price-up accuracy.
Excess ranking is weak but positive in six folds; its gross top/bottom-decile
spread is 0.2046 percentage points versus original HGB's 0.1524. The paired
10-session diagnostic spread advantage is +0.05224 points, 95% interval
[+0.01711,+0.08716]. Overall rank IC is similar to original HGB, not established
as better. Combined/excess rankings are identical by construction.

Later-period decay, survivorship, repeated development-fold exploration,
eligibility exclusions, unmodeled turnover/costs and publication timing remain.
After-close information cannot trade at that observed close. No approved model,
public confidence percentage or profit claim follows.

## Reproducibility and protected data

Clean snapshot SHA-256:
`ee0b2ed66c8abb87e0cf36798a32258bc902c0e1687ddee2a485c80b44216e89`.
The local snapshot contains 494 cleaned current-constituent stocks through
2026-11-12. The target frame has 1,955,893 development rows; the six 2007-2018
evaluation folds contain 1,312,210 observations. Development targets end
2018-12-31, with a 252-session internal calibration block and purged boundaries.
Targets are clipped at fit-only 0.5/99.5 percentiles; outcomes remain unclipped.

36 focused tests passed; all six fold checkpoints completed. The paired ranking
audit used saved predictions and added no fits. The latest rounds did not score
validation/final test. Older five-session validation was already examined;
preserve its access history. Next-session 2019-2021 access needs a recorded
candidate-selection protocol. Final 2022-01-03 through 2026-11-12 remains reserved.

## Code, evidence and local files

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

Local course root: C:\Users\noahs\OneDrive - University of Connecticut\Fall26\CSE4095.
Inputs/previous predictions: StockSight-ml-research/data.
Completed target outputs: StockSight/.worktrees/next-session-targets/data/next-session-target-round.
Existing Python: %TEMP%/stocksight-ml-round2-env/Scripts/python.exe.

Git intentionally excludes data, checkpoints, environments and secrets. Another
machine needs an authorized transfer of clean/prices_clean.parquet,
features/features.parquet, the complete next-session frame/manifest/prepared
metadata and six HGB parquet/JSON predictions. Transfer target checkpoints,
manifests and attempts for saved-result auditing. Verify hashes; do not silently
download/rebuild and call it the same snapshot. The launcher assumes Noah's
sibling/worktree layout. A different layout must explicitly configure
STOCKSIGHT_DATA_DIR, STOCKSIGHT_PRIOR_NEXT_DIR and STOCKSIGHT_TARGET_DIR and use
the pinned research environment. Frozen manifests reject source/package drift.

## When Noah resumes

Audit saved rankings for stock/day concentration, turnover and realistic
publication/next-available entry timing. Audit OHLC adjustment/alignment first.
No broad model sweep or confidence-cutoff tuning. If this survives, predeclare
candidate/comparator/metrics before protected scoring. Otherwise emphasize
descriptive risk/education. Qlib motivated continuous/ranking targets; MASTER
motivated market context, not copied weights or a reproduced transformer.

Long runs: prepare and test a bounded resumable command, then let Noah execute
it locally and return results. No run is needed now. The integration foundation
can proceed later with an honest unavailable response and no selected model.
