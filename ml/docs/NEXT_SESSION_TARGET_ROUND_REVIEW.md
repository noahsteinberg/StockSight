# Continuous-target round review

Reviewed November 17, 2026. All six folds completed. No validation/final-test
scoring, serving artifact, deployment or application change occurred.

## Decision

Stop this next-session absolute-direction/decomposition search: no new model
passes direction gates. Keep original binary HGB as the research reference.
There is enough ranking evidence to justify a narrow follow-up on relative
stock ranking, with excess-return HGB as a candidate to examine. No serving
approval, new model sweep, UI change or protected-period access follows.

## Direction

All methods use the same 1,312,210 evaluation observations across six chronological
folds covering 2007-2018. Absolute-return HGB's 52.242% accuracy is almost identical
to original HGB's 52.239%, but balanced accuracy falls from 51.275% to 50.769%.
It beats reversal in only 2/6 folds and has worse Brier than the reference.
Its primary paired balanced-accuracy difference vs reference is -0.506 percentage
points, with 95% interval [-0.712, -0.294]. Its 0.168-point accuracy advantage vs
always-up has an interval spanning zero.

Excess HGB reaches 50.664% balanced accuracy on its relative direction target,
which cannot be compared directly with absolute up/down accuracy. Its advantage
over relative reversal is only 0.044 percentage points, with primary 95% interval
[-0.213, +0.289]. It fails direction review.

Combined market/stock reaches 50.028% balanced accuracy and 0.49582 AUC for
absolute direction and beats reversal in 0/6 folds. Ridge decomposition did
not solve absolute direction.

## Ranking

Rank IC measures within-date ordering association, not accuracy or probability.
All candidates have positive mean IC in all six folds and positive adjusted
IC/spread lower bounds at 5/10/21-session block lengths. This passes the frozen
ranking-hypothesis review flag, not model promotion.

| Method | Mean daily rank IC | Gross top-minus-bottom decile spread |
| --- | ---: | ---: |
| Original binary HGB scores | 0.02620 | 0.1524 percentage points |
| Absolute-return HGB | 0.02321 | 0.1925 percentage points |
| Excess-return HGB | 0.02549 | 0.2046 percentage points |
| Previous-return reversal ranking | 0.01802 | 0.0698 percentage points |

Excess HGB does not improve the overall IC point estimate over original HGB.
Its more promising distinction is the extreme-group spread, which exceeds
original HGB in all six folds.

A post-round saved-prediction-only paired audit was run. It does not refit,
change frozen gates or access new dates. It uses identical keys, 5,000 within-fold
date-block draws, 10 sessions primary and 5/21 sensitivity. Diagnostic adjusted
lower bounds cover four paired comparisons per candidate, not all historical
research trials. These post-round diagnostics are not independent confirmation.

For excess HGB, primary paired differences:

- IC vs original HGB: -0.00071, 95% interval [-0.00571, +0.00381]. No broad
  ordering improvement is established.
- Decile spread vs original HGB: +0.05224 percentage points, 95% interval
  [+0.01711, +0.08716], diagnostic adjusted lower +0.00814 points.
- IC vs reversal: +0.00747, 95% interval [+0.00175, +0.01285].
- Decile spread vs reversal: +0.13487 percentage points, 95% interval
  [+0.08727, +0.17905].

The positive diagnostic spread contrast vs original HGB persists at all three
block lengths. Combined/excess rankings are identical by construction: adding
one market score to every stock on a date cannot change their order. They are
not independent successful ranking models.

## Limits and next checkpoint

Signal decays: excess IC falls from about 0.0407 in the first two folds to
0.0183 and 0.0109 in the last two. Its spread falls from about 0.44/0.36 percentage
points to 0.114/0.072 points. The current-constituent universe has survivorship
bias and excludes unchanged/invalid next-session returns under frozen eligibility.

Spreads are gross descriptive close-to-close differences. A signal computed
after the close cannot trade at that just-observed close. Costs, turnover,
borrowing, liquidity and next-available execution are not modeled. No profit
claim follows. Repeated development-fold reuse limits uncertainty interpretation.

Recommended sequence:

1. Freeze the round and retain original/excess HGB predictions.
2. Frame the prospective product as relative rankings of stocks to investigate;
   no supported accurate up/down or public-confidence claim exists.
3. Before another fit, audit saved predictions for extreme-day/stock concentration
   and turnover. Establish whether the signal survives actual publication/entry
   timing. Existing OHLC may support that diagnostic without downloads, but its
   adjustment basis and label alignment must first be audited. Record new metrics
   as exploratory and do not retune deciles on these same observations.
4. If those checks survive, record a candidate-selection/protected-evaluation
   protocol fixing target, original-HGB comparator, metrics and rules before any
   2019-2021 access. Final test remains reserved. Access is not automatic.
5. If ranking disappears, stop return-model search and emphasize descriptive
   risk/educational analysis. Predictive risk would need separate research.

No additional long run is needed from Noah now. Deployment can proceed
independently with ML unavailable. Future integration follows latest main and
the existing integration plan.

## Evidence

- Frozen design: `NEXT_SESSION_TARGET_ROUND.md`.
- Full output: `NEXT_SESSION_TARGET_ROUND_RESULTS.md` and
  `ml/reports/next_session_target_round.json`.
- Paired audit: `ml/scripts/review-next-session-target-round.py` and
  `ml/reports/next_session_target_round_ranking_review.json`.
- Hash-verified runtime inputs/checkpoints and attempts remain ignored in
  `data/next-session-target-round/`. Run lock absent; report completed.
