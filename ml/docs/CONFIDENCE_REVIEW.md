# Saved-prediction review — November 14, 2026

## Decision

Do not promote a confidence-filtered model. Larger margins identify cases with higher historical accuracy, but this diagnostic does not establish a reliable additional advantage over the simple reversal rule. Keep the original acceptance gates and the application's prediction-unavailable state. No validation or final-test evaluation was performed.

The user ran the diagnostic in 7 seconds. Follow-up checks reused the same saved training-fold predictions; no training or downloads were needed.

## Results

These are pooled, out-of-fold training-period results over folds 1–5. Balanced accuracy gives equal weight to beat and lag outcomes. Each reversal comparison uses exactly the model's selected stock/date observations.

| Intended answer rate | Actual answer rate | Accuracy | Balanced accuracy | Reversal balanced accuracy | Model gain over reversal, percentage points (10-session block 95% interval) |
| --- | --- | --- | --- | --- | --- |
| 100% | 100.00% | 51.110% | 50.960% | 50.520% | +0.441 [+0.029, +0.773] |
| 50% | 36.90% | 51.937% | 51.645% | 51.202% | +0.443 [+0.002, +0.787] |
| 25% | 14.51% | 52.403% | 52.066% | 51.883% | +0.183 [-0.279, +0.540] |
| 10% | 4.57% | 53.763% | 53.449% | 53.007% | +0.442 [-0.049, +0.839] |

Answering fewer cases raises both the model's and reversal's scores. The model's extra advantage does not steadily increase with selectivity. The most selective policy abstains on approximately 95.4% of observations.

## Coverage and probability concerns

Cutoffs were fixed from earlier folds' margins, without current-fold labels. Their intended coverage is not a promise: score distributions change between models and market periods. The strictest policy covered 9.02%, 9.31%, 0.31%, 3.53%, and 1.35% in the five successive folds. Ties are included, but changing score distributions explain the substantial coverage shortfall here. A deployed policy would need an explicit availability contract and monitoring; selecting a new threshold from these outcomes would be another research decision.

The raw probabilities also should not be presented as verified confidence. Among 22,150 predictions between 55% and 60% beat probability, the mean prediction was 56.25%, while only 51.62% beat the universe. These are descriptive pooled rates with overlapping outcomes, not independent trials or a calibration significance test. Only 52 observations were at or above 60%; strong-confidence claims have very little support. Every policy's Brier improvement interval against the constant-probability reference includes zero.

## Follow-up verification

`ml/scripts/review-confidence.py` verifies input hashes, reconstructs training-only labels, independently recalculates accuracy, balanced accuracy and Brier with scikit-learn, and checks reversal on the identical rows. Every pooled metric matched the original report within 1e-12; all original 10-session intervals were reproduced. The 10 focused diagnostic tests passed again.

Fixed sensitivity checks used 1,000 paired date-block draws for each of 5, 10, 21 and 63 sessions, stratified within folds and preserving zero-answer dates. These were checks of assumptions, not a search for a preferred interval:

- Full coverage: the exploratory gain interval stayed above zero for all four block lengths.
- Intended 50% coverage: the interval included zero with 21- and 63-session blocks, despite narrowly excluding it with 5 and 10.
- Intended 25% coverage: all four intervals included zero.
- Intended 10% coverage: 5-, 10- and 21-session intervals included zero; the 63-session interval did not. This does not provide consistent evidence across assumptions and is not grounds to choose that block length after seeing results.

The training-fold advantage at full coverage does not overturn the previously examined validation failure. All intervals are exploratory, reuse examined training folds and are unadjusted for multiple policy comparisons. No operating policy was selected. Original protected reports and validation history remain unchanged.

## Next work

Stop experimenting with this model's confidence cutoffs for now. The four-configuration round and this diagnostic are complete. The team should agree on the user-facing question before another model round: keep five-session relative beat/lag, or specify a different outcome/horizon and its evaluation protocol. A changed target requires new labels and evaluation planning; it is not evidence that the existing model improved. Reserve the final test period throughout.

Application teammates can continue historical charts, clear target descriptions and a prediction-unavailable state. Serving and artifact export remain separate decisions.

## Reproduce the review

From the research repository, using the prepared pinned environment:

```powershell
& "$env:TEMP\stocksight-ml-round2-env\Scripts\python.exe" ml/scripts/review-confidence.py
```

Inputs and detailed generated outputs remain ignored under `data/confidence-analysis/`: `summary.md`, `results.json`, `review.json` and `run.log`. This tracked review preserves the conclusion without committing generated datasets or predictions.
