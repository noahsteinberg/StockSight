# Next-session round 2: market context and advanced tree ensembles

**Completed:** no candidate qualified. See
[`NEXT_SESSION_ROUND2_RESULTS.md`](NEXT_SESSION_ROUND2_RESULTS.md).

This is a bounded training-period follow-up. It preserves the first next-session
round and its 52.239% HGB reference. It does not modify the app, download data,
access validation/final test, export a model, or tune a confidence threshold.

## Six comparisons

The existing HGB is reused from its verified checkpoints rather than fitted a
second time. Five new configurations are trained on identical evaluation rows:

1. HGB + market context, expanding history.
2. HGB + market context, trailing 10-year history.
3. Deeper regularized HGB + market context, trailing 10-year history.
4. Random forest + market context, trailing 10-year history.
5. Extra Trees + market context, trailing 10-year history.

The market pack is frozen before fitting: equal-weight 1/5/21-session market
returns, 21-session market volatility, 1/5-session breadth, and 21-session
cross-sectional dispersion. It is calculated across feature-eligible stocks
before next-session label eligibility is joined, requiring at least 150 valid
stocks. This uses today's constituent universe historically and retains the
existing survivorship limitation.

The sequence answers three questions: whether absolute direction was missing
market-wide information; whether old history hurts later folds; and whether
boosting, deeper boosting, bagged forests, or extremely randomized forests
generalize better. No XGBoost/LightGBM/CatBoost dependency is introduced. HGB is
already a large-data boosted-tree method; RF/Extra Trees provide distinct model
families without changing the pinned environment.

All configurations preserve the six 2007–2018 chronological folds, the prior
252-session internal holdout boundary, common observations, seed 0 and two
threads. The 10-year window is measured from the end of base-fit data. Raw
features and native missing-value handling are used. No class weighting or
post-hoc calibration is included because sigmoid calibration worsened round 1.

## Selection and diagnostics

Accuracy, balanced accuracy, Brier, log loss, pooled AUC, mean daily AUC and
fold results are compared with always-up, majority, momentum, reversal, the
constant probability and the original HGB. Primary uncertainty is 5,000 paired
10-session date-block draws, with 5/21-session sensitivity checks.

A candidate advances only for later review if it improves balanced accuracy by
at least 0.5 percentage points over reversal; multiplicity-adjusted lower bounds
against reversal and the original HGB are positive; it beats always-up accuracy
and constant-probability Brier; and it beats reversal in at least 4/6 folds.
Advancement is not promotion and does not authorize validation access.

The fixed `p<=0.4 or p>=0.6` diagnostic records accuracy and coverage because the
first round observed about 60.6% accuracy on less than 1% of cases. It cannot
select a model and is explicitly recognized as motivated by already-seen data.

## Commands

From this worktree:

```powershell
.\Run-Next-Session-Round2.ps1 -Stage Prepare
.\Run-Next-Session-Round2.ps1 -Stage Pilot
.\Run-Next-Session-Round2.ps1 -Stage Full
```

`Full` resumes completed checkpoints and writes the report after all 30 new
configuration/fold fits finish. Run one copy and keep the computer awake. Progress
prints once per completed fit. Inputs, configurations, context, attempts and
prediction hashes are frozen. A stale `run.lock` should be removed only after
confirming its owner process ended.

## Pilot evidence

Fold 0 completed for all five new configurations. Standard market HGB fits took
about 24 seconds each, deeper HGB 58 seconds, random forest 302 seconds, and
Extra Trees 95 seconds. Extra Trees was the only pilot challenger above the
reference balanced accuracy (52.227% versus 51.988%); this is one already-seen
fold, not model selection. Random forest was below the reference on fold 0, but
remains included because the reference's known weakness is later-period decay.

Preparation initially found a 1.16e-10 float32 reduction-order difference in an
independent market-return trace. The attempt remains logged; the audit tolerance
is explicitly 1e-8 for float32 returns, while breadth remains checked at 1e-12.
Preparation then completed and re-verification passed. The 16 focused round-1/
round-2 tests passed. The complete ML unit suite passed 489 tests with three
data-marked tests deselected and four existing pandas timezone warnings, using a
worktree-local pytest base temp because the managed Windows temp root was denied.
