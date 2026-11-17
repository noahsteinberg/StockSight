# Open-source model and competitive-method audit

Date: 2026-11-16

## Decision summary

StockSight should not copy a trained stock model or replace its pipeline with a
large framework. The closest useful reference is Microsoft Qlib: borrow its
research discipline, feature families, continuous-return targets, and
cross-sectional evaluation ideas. The closest practical algorithmic follow-up
is one bounded LightGBM or XGBoost experiment on StockSight's own immutable
data and folds.

The most promising change is not simply a more complicated classifier. It is
to preserve the app's simple question while giving the model a richer target:

1. predict the next-session continuous return or cross-sectional excess return;
2. optionally model the market component and stock-specific component
   separately;
3. derive the displayed up/down call from the combined prediction; and
4. derive confidence only from out-of-fold calibration evidence.

This can be tested without changing the frontend. It also preserves the current
five-session and next-session results as completed research rather than
rewriting their history.

## StockSight's present evidence

- The verified next-session HGB reference reaches 52.239% accuracy and 51.275%
  balanced accuracy on six chronological training-period folds.
- Its balanced-accuracy improvement over previous-session reversal is only
  0.065 percentage points, with uncertainty spanning zero and wins on 3/6
  folds.
- Performance decays across later folds and the model strongly favors the up
  class. This means ordinary accuracy alone overstates usefulness.
- The current round is already comparing the reference with market-aware HGB,
  deeper HGB, Random Forest, and Extra Trees. Adding another package before
  that fixed round finishes would confound the evidence.
- The data is already large enough for tabular experiments: about 1.96 million
  eligible examples, 54 established past-only features, and six purged
  chronological folds. A new dataset is not required to test a new target or
  tree algorithm.
- Historical use of today's constituents remains a survivorship limitation.
  No open-source model removes that data limitation.

## Evaluation criteria for outside projects

Projects were judged on target fit, data fit, leakage controls, reproducibility,
engineering cost, licensing, and whether an experiment would answer a distinct
question. Popularity and published headline performance were not treated as
evidence for StockSight.

## Landscape

| Project or method | Fit for StockSight | What is worth borrowing | What not to copy | Near-term priority |
| --- | --- | --- | --- | --- |
| Microsoft Qlib / Alpha158 | High as a research reference | Point-in-time workflow, train/valid/test separation, continuous future-return labels, cross-sectional normalization/ranking, signal metrics, Alpha158 feature families, LightGBM/XGBoost baselines | Reported China-market scores, pretrained artifacts, trading rules, or split dates | Highest inspiration |
| LightGBM | High as one bounded challenger | Regularized leaf-wise boosted trees, histogram training, early stopping, regression/classification/ranking objectives | A broad hyperparameter sweep or Qlib's China-specific parameter values | Highest algorithm candidate |
| XGBoost | High as an alternative challenger | Mature histogram boosting, row/column subsampling, regularization, early stopping | Running both XGBoost and LightGBM merely to search for a winner | High, but choose one first |
| CatBoost | Medium | Strong boosted-tree implementation and ordered boosting | Treating ticker as a categorical shortcut; its main categorical advantage is not central to the current numeric feature table | Later only |
| Qlib DoubleEnsemble | Medium after a strong LightGBM baseline | Error-aware sample reweighting and feature-subset diversity | Six submodels now; it greatly expands compute and overfitting surface | Defer |
| MASTER stock transformer | High conceptual relevance, high implementation risk | Separate intra-stock, inter-stock, temporal, and market-guided components | Published checkpoints/data, direct result comparison, or immediate adoption | Advanced research only |
| TRA and other Qlib neural models | Medium conceptual relevance | Explicit handling of changing temporal patterns | Neural-model search before a stronger tabular baseline and target audit | Defer |
| Chronos / TimesFM | Low for the current question | A later benchmark for numeric time-series forecasting | Assuming generic zero-shot forecasts produce calibrated stock direction or useful confidence | Do not use now |
| NeuralForecast | Low to medium for a later sequence study | Reproducible LSTM/TCN/PatchTST implementations | Converting the current panel blindly into independent ticker series | Do not use now |
| FinRL | Low | Train/test/trade separation and transaction-cost awareness | Reinforcement learning for a supervised next-session prediction task | Wrong objective now |

## Detailed findings

### 1. Qlib is the closest useful reference, not a drop-in solution

[Qlib](https://github.com/microsoft/qlib) is an MIT-licensed quantitative
research platform supporting supervised models, market modeling, and trading
workflows. Its standard
[LightGBM Alpha158 configuration](https://github.com/microsoft/qlib/blob/main/examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml)
separates train, validation, and test periods and predicts a continuous return.
The official
[data documentation](https://github.com/microsoft/qlib/blob/main/docs/component/data.rst)
explains that Alpha158 uses a future close return and offers robust z-score,
cross-sectional z-score, and cross-sectional rank processors. The
[feature loader](https://github.com/microsoft/qlib/blob/main/qlib/contrib/data/loader.py)
contains price, volume, candlestick, and rolling-statistic feature families.

This is close to StockSight's panel-data problem, but the benchmark is not
comparable. Qlib's published
[benchmark table](https://github.com/microsoft/qlib/blob/main/examples/benchmarks/README.md)
uses China A-share universes, continuous signal and portfolio metrics, different
dates, and different execution assumptions. Those results justify testing
methods, not claiming expected StockSight accuracy.

Most useful Qlib ideas for StockSight:

- retain a continuous next-session return before reducing it to a direction;
- report daily Spearman information coefficient and rank IC alongside direction
  metrics;
- consider cross-sectional target normalization as a separate, fixed target;
- add rolling slope, regression R-squared/residual, and price-volume correlation
  families only in a later feature ablation; and
- keep all learned preprocessing inside each chronological training fold.

Qlib's label timing also exposes an important product decision. Its default
label delays entry because a signal produced after today's close cannot trade at
that same close. StockSight must state whether "next day" means movement from
today's close to the next close for an informational forecast, or an executable
return after the next available entry. These are not the same target.

### 2. LightGBM is the best next algorithm candidate

[LightGBM](https://github.com/lightgbm-org/LightGBM) is MIT-licensed. Its
[official feature description](https://github.com/lightgbm-org/LightGBM/blob/main/docs/Features.rst)
documents histogram binning, leaf-wise growth, bagging, column sampling, L1/L2
regularization, ranking objectives, and early stopping. Leaf-wise growth can
overfit, so a StockSight test must fix conservative leaf count, depth, minimum
leaf size, row/column sampling, and regularization before results are viewed.

It is a genuine algorithmic step beyond the current scikit-learn HGB
implementation, but not a wholly different scientific theory. A small gain is
plausible; a leap from roughly 52% to reliably near 60% is not a responsible
expectation from changing the tree package alone.

Recommended use: one fixed LightGBM setup with an internal chronological early-
stopping block, run on the same outer folds and observations as the reference.

### 3. XGBoost is a credible alternative, not an additional fishing license

[XGBoost](https://github.com/dmlc/xgboost) is Apache-2.0 licensed and provides
classification, regression, and ranking through optimized boosted trees. Its
[tree-method documentation](https://github.com/dmlc/xgboost/blob/master/doc/treemethod.rst)
describes `hist` as its fastest general tree method, while its
[parameter reference](https://github.com/dmlc/xgboost/blob/master/doc/parameter.rst)
documents row/column sampling and L1/L2 controls.

XGBoost answers almost the same research question as LightGBM. The next round
should choose one, not run both and select whichever happened to win on the six
already-visible folds. LightGBM is recommended first because Qlib's closest
tabular stock workflow uses it and its leaf-wise structure differs more clearly
from the current HGB setup.

### 4. CatBoost's signature advantage is not central here

[CatBoost](https://github.com/catboost/catboost) is Apache-2.0 licensed and
supports regression, classification, ranking, numerical features, and native
categorical processing. StockSight's vetted inputs are numeric. Adding ticker
identity as a categorical feature would invite memorization of historically
easy tickers, amplify survivorship bias, and weaken generalization to changing
constituents. CatBoost remains a legitimate later numeric-tree comparison, but
it is not the first gap to fill.

### 5. DoubleEnsemble has an interesting mechanism but is premature

Qlib's MIT-licensed
[DoubleEnsemble implementation](https://github.com/microsoft/qlib/blob/main/qlib/contrib/model/double_ensemble.py)
trains multiple LightGBM submodels, reweights samples using prior loss behavior,
and changes feature subsets using permutation-based importance. This targets
non-stationarity and heterogeneous examples more directly than a simple model
swap.

It also trains multiple submodels and makes feature/sample selection depend on
training behavior. That creates a much larger audit and overfitting surface.
It becomes reasonable only if a single fixed LightGBM model first shows stable
signal on StockSight's folds.

### 6. MASTER is the most relevant advanced neural inspiration

The MIT-licensed official
[MASTER repository](https://github.com/SJTU-DMTai/MASTER) accompanies the
[AAAI 2024 paper](https://ojs.aaai.org/index.php/AAAI/article/download/27767/27575).
It alternates within-stock temporal aggregation with across-stock aggregation
and uses market information to gate features. This directly addresses a
weakness in treating each ticker/date as an independent tabular row.

It is not ready to copy into StockSight:

- the official repository documents inconsistencies in its released validation
  processing and replacement data;
- it uses China-market data and a different continuous target;
- its tensor layout groups all stocks by date with lookback sequences, requiring
  a new sequence dataset, batching, masks, and extensive leakage tests; and
- its published dependencies and checkpoints should not be mixed into the
  pinned production environment.

The safe lesson is architectural: if tabular evidence justifies a neural round,
build a small StockSight-native model that explicitly separates time, stock,
and market axes. Do not import a checkpoint.

### 7. General forecasting foundation models solve a different problem

[Amazon Chronos](https://github.com/amazon-science/chronos-forecasting) and
[Google TimesFM](https://github.com/google-research/timesfm) forecast numerical
time-series trajectories. Chronos is Apache-2.0; TimesFM source is Apache-2.0,
but its repository states that current 3.0 weights use a separate
non-commercial/non-production license. [NeuralForecast](https://github.com/Nixtla/neuralforecast)
offers Apache-2.0 implementations of LSTM, TCN, N-BEATS, TFT, PatchTST and other
forecasting models.

These tools can produce a benchmark for future prices or returns, but they do
not automatically solve cross-sectional stock ranking, changing constituents,
market-relative features, direction calibration, or leakage-safe financial
evaluation. They would reopen the graph-extension idea that StockSight
intentionally moved away from. They are not the next experiment.

### 8. FinRL is for decisions, not this prediction checkpoint

[FinRL](https://github.com/AI4Finance-Foundation/FinRL) and its
[documented train-test-trade pipeline](https://github.com/AI4Finance-Foundation/FinRL/blob/master/docs/source/finrl_meta/overview.rst)
train agents to choose actions under a reward function and market environment.
That is useful for portfolio allocation or execution after a credible signal
exists. It would add reward design, transaction costs, action constraints, and
policy evaluation before StockSight has established a dependable supervised
signal. It is a target mismatch for the current checkpoint.

## Recommended bounded follow-up after round 2

Do not start this automatically. First freeze and review the active round-2
report. If no current candidate qualifies, the next round should test the
target representation and algorithm separately, with no frontend work.

### Fixed candidate budget

1. **LightGBM binary reference:** current absolute next-session up/down label,
   current 54 features, fixed conservative LightGBM settings. This isolates the
   library/algorithm change.
2. **LightGBM continuous-return model:** predict the actual next-session adjusted
   return; convert predictions above zero to up and at/below zero to down. This
   isolates the benefit of retaining return magnitude.
3. **Two-component LightGBM model:** predict the equal-weight universe return
   and the stock's residual/excess return separately, then add them for an
   absolute-return prediction. This tests whether the current shared market
   features should be modeled as a component rather than mixed into every row.

Use the same six outer folds, common eligible observations, protected-period
rules, purge, seed policy, and block uncertainty. Use an internal chronological
holdout only for early stopping. Predeclare one small parameter set for each
configuration; no Optuna or broad grid search.

### Metrics and gates

Continue reporting accuracy, balanced accuracy, Brier score, coverage,
per-fold results, and date-block uncertainty against always-up, reversal, and
the current HGB. Add:

- mean daily Spearman IC between predicted and realized continuous return;
- mean daily rank IC;
- top-minus-bottom prediction-quantile realized return, as a descriptive signal
  diagnostic rather than a trading claim; and
- direction accuracy by predicted-confidence bin and calendar regime.

A continuous model must still pass the same direction and probability-quality
standards before it can drive app arrows. A good rank IC alone does not justify
claiming accurate absolute direction.

### What to avoid

- Do not access the reserved validation or final test merely to select among
  these ideas.
- Do not tune a confidence cutoff on the same folds used to choose the model.
- Do not add ticker identity, current constituent metadata, news sentiment, and
  a new algorithm in the same experiment.
- Do not compare StockSight accuracy directly with Qlib portfolio returns or
  information coefficients.
- Do not copy external checkpoints or datasets into the app.
- Do not promise 60% accuracy. The current evidence supports seeking a stable,
  statistically defensible incremental gain.

## License and provenance note

No external source code, model weight, dataset, or parameter file was copied in
this audit. The cited projects use permissive open-source licenses except where
the TimesFM repository explicitly distinguishes the license of newer model
weights. If code is later incorporated, preserve its required copyright,
license, and notice files and record the exact source commit. This summary is a
research provenance note, not legal advice.
