# Machine learning foundation

No ML features/training/inference, predictions or model artifacts are implemented.
The application already imports historical data and exposes tested close-based
SMA20/RSI14. Read [INDICATORS.md](../docs/INDICATORS.md) before reusing those
calculations: it defines a fixed history anchor/cap, null warm-up and flat-price
behavior. A shared/versioned feature implementation is still required; do not
silently use different training and inference conventions.

[CURRENT_HANDOFF.md](../docs/CURRENT_HANDOFF.md) records current scope. The snapshot's
adjustment/calendar/universe limitations remain unresolved, so chart acceptance
is not ML suitability approval. Frontend redesign is a separately deferred task.

Planned pipeline:

```text
Historical Data
      ↓
Feature Engineering
      ↓
Time-Aware Train/Validation/Test Split
      ↓
Model Training
      ↓
Evaluation
      ↓
Saved Model
      ↓
Backend Inference
```

First define a measurable target, potentially next-trading-day up/down direction, including prediction cutoff, exchange calendar, price adjustment policy, and treatment of unchanged prices. Candidate features include recent returns, moving averages, RSI, MACD, Bollinger position, volatility, and volume changes. Candidate models include Logistic Regression and Random Forest.

Split chronologically rather than carelessly at random: random stock/time-series splits can leak future information. Construct each feature only from information available at the prediction cutoff. Fit scalers, imputers, and feature selection only on training folds. Account for label horizons at split boundaries; keep overlapping future labels out of training/validation boundaries and synchronize dates across symbols. Reserve an untouched later test period and consider walk-forward validation.

Compare models to a simple baseline with agreed metrics such as balanced accuracy and a confusion matrix; evaluate probabilities if provided. Record provider/data version, date ranges, feature definitions, seeds, model version, and limitations. Do not imply classification accuracy guarantees trading profitability.

Keep training offline, separate from request handling. Define a versioned feature/model contract before adding backend inference. Downloaded datasets and generated artifacts belong in ignored storage, never in Git; artifact loading must use trusted sources.
