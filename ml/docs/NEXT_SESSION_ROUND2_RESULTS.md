# Next-session round 2 results

Date: 2026-11-16

## Decision

The bounded round is complete. No new candidate qualifies for later review.
Do not promote, export, serve, or access validation/final test based on this
round. The original HGB remains the research reference, not an approved model.

This result ends the current search over market-aware HGB, deeper HGB, Random
Forest, and Extra Trees on the same binary next-session target. A follow-up
should test target representation and market/stock decomposition rather than
adding more tree families or tuning these configurations.

## Results

All methods were evaluated on the same 1,312,210 training-period walk-forward
observations. Validation and final test were not scored.

| Configuration | Accuracy | Balanced accuracy | AUC | Mean daily AUC | Brier | Predicted up | Beats reversal folds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HGB reference | 52.239% | **51.275%** | 52.062% | 51.826% | 0.249274 | 73.30% | 3/6 previously recorded |
| HGB + market, expanding | 51.036% | 50.518% | 50.736% | 51.488% | 0.255429 | 62.51% | 0/6 |
| HGB + market, 10 years | 51.240% | 50.676% | 50.816% | 51.413% | 0.255721 | 63.62% | 1/6 |
| Deeper HGB + market, 10 years | 51.561% | 51.117% | 51.378% | 51.563% | 0.257162 | 60.76% | 3/6 |
| Random Forest + market, 10 years | 51.973% | 51.046% | 51.475% | **51.905%** | 0.249743 | 72.40% | 2/6 |
| Extra Trees + market, 10 years | **52.406%** | 51.017% | 52.043% | 51.857% | **0.249251** | 83.53% | 3/6 |

Ordinary accuracy does not select Extra Trees. It calls up on 83.53% of all
rows and increasingly calls up across folds: 80.38%, 69.69%, 75.70%, 86.55%,
91.86%, and 94.65%. Its balanced accuracy is 0.258 percentage points below the
reference; the primary paired 10-session block interval is
[-0.528, -0.002] percentage points. Its tiny Brier improvement over the
reference has an interval spanning zero. It produces no predictions at the
fixed `p<=0.4 or p>=0.6` diagnostic threshold.

Random Forest required roughly 40 minutes across the six folds, has lower
accuracy, balanced accuracy and worse Brier than the reference, and beats
reversal in only 2/6 folds. Its 58.89% selective accuracy covers only 1.76% of
rows and cannot select a model.

Adding the shared market-context pack directly to HGB materially worsens Brier
and accuracy. Expanding-window market HGB is 0.757 percentage points below the
reference in balanced accuracy, with a paired 10-session interval entirely
below zero. A 10-year window does not repair the result. The deeper market HGB
recovers some balanced accuracy but has the worst Brier of the round and no
stable advantage.

## What was learned

1. **The original reference remains the strongest balanced classifier.** Its
   signal is still weak and decays across later folds, so it remains research
   evidence rather than a serving candidate.
2. **Extra Trees' accuracy gain is majority-class behavior.** Balanced accuracy
   and the up-call share expose this; ordinary accuracy alone would select the
   wrong model.
3. **Shared date-level market features are not enough.** Treating the same
   context as columns on every stock row can let trees overfit dates without
   separating the market move from stock-specific movement.
4. **A trailing 10-year window is not a solution by itself.** It does not turn
   the market-aware models into stable improvements.
5. **More compute is not the next answer.** Random Forest is expensive and does
   not improve the evidence. Another broad forest/boosting search is stopped.
6. **High-confidence filtering is still unsupported.** The fixed diagnostic is
   descriptive, has low or unstable coverage, and was not a candidate-selection
   mechanism.

## Next research question

Keep the app-facing concept general while testing whether a richer target is
more learnable than a hard binary label. The next bounded round should isolate
three questions on the same folds and common observations:

1. **Algorithm-only:** does one fixed, conservative LightGBM binary classifier
   improve the current absolute next-session target?
2. **Target-only:** does LightGBM regression on continuous next-session return
   preserve useful magnitude/ranking information that binary training discards?
3. **Decomposition:** does separately modeling the equal-weight market return
   and stock-specific residual produce a better combined absolute signal?

Do not add Alpha158 features, ticker identity, sentiment, fundamentals, a neural
model, and a new target in this same round. A later feature-family ablation is
justified only after the target comparison.

Direction metrics remain required for any up/down UI. Continuous candidates
also report mean daily Spearman IC, rank IC and top-minus-bottom quantile spread.
Probability and Brier comparisons require a predeclared train-only mapping from
continuous score to probability; otherwise the UI uses signal strength and does
not claim confidence.

## Provenance

- Machine-readable report: `ml/reports/next_session_round2.json`
- Prepared inputs and ignored checkpoints: `data/next-session-round2/`
- Experiment design and commands: `NEXT_SESSION_ROUND2.md`
- Open-source audit: `OPEN_SOURCE_MODEL_AUDIT.md`
- Preparation attempt log retained one float32 tolerance failure followed by
  successful preparation; pilot, full run, and report all completed.
