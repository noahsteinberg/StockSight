# Next-session checkpoint — November 16, 2026

## Decision

The bounded batch is complete. None of the four configurations passes the
predeclared research screen. Do not promote a model, begin serving, or access
validation/test automatically. The application was not changed.

This does not establish that next-session prediction is impossible. It establishes
that these four fixed configurations on these features did not demonstrate a
dependable improvement over the strongest simple comparison.

## What ran

The original cleaned snapshot and 54 past-only features were reused. New
next-session adjusted-close labels were computed only from prices through 2018.
Preparation produced 1,955,893 eligible examples; the six 2007–2018 outer folds
contain 1,312,210 evaluation cases. The source-period audit separately counts
22,023 unchanged and 835 invalid forward outcomes. Each configuration answers
100% of the common eligible evaluation sample, not 100% of raw source rows.

Two shared base fits per fold produced ordinary and sigmoid-calibrated versions:
12 completed base fits, representing four configurations across six folds.
Model fitting took about 459 seconds in total, excluding preparation, tests and
reporting. The pilot's two fits were reused, not repeated in the full batch.

| Method | Accuracy | Balanced accuracy | Brier, lower better |
| --- | --- | --- | --- |
| Always up / training-majority | 52.074% | 50.000% | Compare probability baseline below |
| Previous-session reversal | 51.139% | 51.210% | Hard direction rule |
| Logistic regression | 51.802% | 51.002% | 0.249621 |
| Logistic + sigmoid | 51.694% | 50.519% | 0.249674 |
| Gradient boosting | 52.239% | 51.275% | 0.249274 |
| Boosting + sigmoid | 52.079% | 50.983% | 0.249588 |
| Training-rate probability | 52.074% | 50.000% | 0.249663 |

The best boosting result improves accuracy over always-up by approximately
0.165 percentage points. Its balanced-accuracy gain over reversal is only
0.065 percentage points; the primary paired 95% date-block interval is
[-0.384, +0.470] percentage points. The multiple-comparison-adjusted lower
bound is also negative. It beats that baseline in only 3/6 folds, short of the
4/6 stability requirement. It is a useful reference, not a selected candidate.

## Error and probability findings

Boosting recognizes 74.52% of actual up outcomes but only 28.03% of actual down
outcomes. Its ordinary accuracy conceals a strong tendency to call up. Balanced
accuracy and same-sample reversal comparisons are therefore essential.

Boosting's fold balanced accuracies are approximately 51.99%, 51.84%, 51.37%,
50.86%, 50.48%, and 50.63%; its stronger early-period performance did not persist
uniformly. Sigmoid calibration did not improve overall Brier for either family.

Among boosting predictions in the 55–60% P(up) bin, the average estimate was
56.40%, versus an observed 54.90% up rate. The >=60% bin had an observed 60.65%
up rate, but contains only 6,627 cases, approximately 0.51% of evaluation cases.
This pooled descriptive bin is not a validated selective operating policy or
evidence that the model is 60% accurate generally. We did not tune a threshold.

Volatility groups do not show a broad advantage over reversal: boosting trails
reversal in the low and high groups, and is slightly ahead in the middle group.
Per-ticker and trend diagnostics are included in the JSON. They are not a list
of best stocks to recommend; selecting winners from them needs later evaluation.

## Verification and limits

- 482 unit tests passed; three dataset-marked tests were deselected in this run.
  The unchanged dataset tests had passed during the prior research round.
- Numerical lint and Git whitespace checks passed. Four existing pandas
  timezone deprecation warnings remain.
- All checkpoint hashes, labels, target dates, sample alignment and independent
  accuracy/balanced-accuracy calculations passed. Original protected reports
  and validation-access history match their preparation hashes.
- Independent Brier checking initially found a ~2e-8 LR difference: sklearn
  reduces float32 probabilities while the independent formula uses float64.
  The checker now records double-precision values and an explicit 1e-7 tolerance
  for float32, retaining 1e-12 otherwise. No fits or conclusions were changed.
- Current-constituent survivorship, adjustment provenance and retrospective
  feature availability limitations remain. There was no new validation/final-test
  scoring and no model export.

## Recommended next decision

Stop this batch. Review the failure with Noah and Vlad before another round:
the useful research question is whether a specific earlier-defined market-state
rule can identify a stable advantage, not which ticker had the nicest score.
Any follow-up needs one concrete hypothesis, a fixed small budget and a later
development-period check. Do not pursue 60% by repeatedly filtering these same
results. A clean no-improvement finding is a valid project result.

Reproduction commands are in NEXT_SESSION_RESEARCH.md. Detailed results,
independent checks, manifest, preparation audit and attempts are retained under
ml/reports/next_session*. Predictions/features remain ignored under
data/next-session. Five-day work was preserved at c983860; this track is separate.
