# StockSight prediction contract (draft v0.2)

Status: **draft for team review**. Items marked **PROPOSED** need team sign-off; each one links to an ADR in [`docs/adr/`](../../docs/adr/). Items marked **DECIDED** reflect choices already made during data cleaning.

This document answers the open questions in [`SPECIFICATION.md`](../../SPECIFICATION.md) ("Exact prediction definition…", "Baseline, model comparison metrics, probability calibration…") using `data/clean/prices_clean.parquet`. It defines *what* is predicted and *how it will be judged*, not features or models.

v0.2 replaces the next-day up/down target with **"does this stock beat the market over the next 5 trading days"**.

## 1. Iteration compact

| Field | Value |
|---|---|
| Goal | Estimate whether each S&P 500 stock outperforms the equal-weight universe over the next 5 NYSE sessions, with an honest probability. |
| Who cares | Students using the app (want an interpretable, relative signal, not false confidence); course reviewers (want leakage-free, reproducible evaluation); the team (must explain every part). |
| Decision owner | The ML team. Final sign-off on PROPOSED items in a reviewed PR. |
| Action changed by the model | What the app displays: a beat/lag call plus `p_beat` per stock. No trades, no advice. |
| Success metric | Validation **balanced accuracy** above the best naive baseline, with a block-bootstrap 95% CI lower bound of the difference above 0 (section 5). |
| Guardrail metrics | Accuracy ≥ always-majority accuracy; Brier below the constant-probability Brier; no validation year below 0.50 balanced accuracy without explanation. |
| Mistake budget | Wrong individual calls are expected; ~50.5–52% balanced accuracy is still a success if it passes the gates and is reported truthfully. |
| Unacceptable mistakes | Leakage (any input after the cutoff); tuning on the test set; presenting `p_beat` as certainty or advice; a prediction computed over a `bad_bar`. |
| Acceptable mistakes | False beats and false lags are equally costly, so neither class is favoured. |
| Assumptions | Yahoo adjusted closes are accurate apart from known, excluded bars; current constituents are a fair universe for an educational demo. |
| Constraints | Daily bars only; offline training; Logistic Regression and Random Forest are the candidate models (TODO Phase 4); CPU only. |
| Labels and data snapshot | Labels derived from `prices_clean.parquet` (end date 2026-11-12, 494 tickers); each run records the file's SHA-256 and `clean_log.json` `created_at`. |
| Baseline | Always-majority, 5-day momentum, 5-day reversal, constant probability (section 4). |
| Candidate signals | Next document. Constraint: ratio/return features only (section 3.4). |
| Threshold or config plan | Predict beat when `p_beat ≥ 0.5`; no threshold tuning on test. |
| Eval slices | Year, GICS sector, volatility tercile, years since joining the index. Slices only; sector and membership are never model inputs (3.4 rule 7). |
| Known risks | Survivorship bias; weak signal; **overlapping labels** (section 3.6); regime shift (2008, 2020). |
| Next experiment | Features (section 8). |
| Rollback or fallback | No prediction shown when any input is missing, stale, or touches a `bad_bar`; never a placeholder. |

## 2. Prediction contract

| Item | Definition | Status |
|---|---|---|
| Entity | One prediction per `(ticker, as_of_date)`, where `as_of_date` (t) is a completed NYSE session. | PROPOSED ([ADR-0004](../../docs/adr/0004-prediction-target.md)) |
| Cutoff | After the official close of t (16:00 America/New_York; 13:00 on early-close days). Inputs may use only data dated ≤ t. | PROPOSED (ADR-0004) |
| Target date | t+5: the 5th XNYS session after t (`exchange_calendars`); weekends and holidays are skipped. | PROPOSED (ADR-0004) |
| Target | `y = 1` if the stock's 5-session return beats the equal-weight mean of all valid tickers' 5-session returns on t, `y = 0` if it lags. Exactly equal is a **tie** (`<NA>`), excluded from training and scoring. | PROPOSED (ADR-0004) |
| Price basis | `adj_close` (split- and dividend-adjusted). | PROPOSED ([ADR-0003](../../docs/adr/0003-price-basis-adj-close.md)) |
| Output schema | `ticker, as_of_date, target_date, p_beat (0–1), call ("beat"/"lag"), model_version, data_snapshot`. | PROPOSED |
| Serving mode | Batch, once per session after close. Latency is not a constraint. | PROPOSED |
| Fallback | Return "unavailable" when any input row is missing or `bad_bar`, the ticker has too little history, or the input data is older than t. | PROPOSED |
| Human review | None per prediction; the UI carries the educational disclaimer. | DECIDED (README) |
| Privacy | Market data has no PII. Predictions are linked to users only through watchlists (backend concern). | DECIDED |

## 3. Data and label contract

### 3.1 Source and grain
- Source: `data/clean/prices_clean.parquet`. Grain: `(ticker, date)`, unique and strictly increasing per ticker (asserted by `clean.py`).
- Universe: current S&P 500 constituents with ≥ 756 cleaned rows (494 tickers). **DECIDED** ([ADR-0001](../../docs/adr/0001-universe-current-constituents.md)).
- Cleaning rules, `bad_bar` semantics and exclusions: **DECIDED** ([ADR-0002](../../docs/adr/0002-cleaning-and-bad-bar.md)).

### 3.2 Label construction (`stocksight_data.labels`)
```
r5[t]         = adj_close[t+5] / adj_close[t] - 1
market_r5[t]  = mean of r5[t] over valid tickers on t      (config MARKET_BENCHMARK = "mean" | "median")
excess_ret[t] = r5[t] - market_r5[t]
label[t]      = 1 if excess_ret > 0, 0 if < 0, <NA> if exactly 0
```
- A row is valid only if the ticker has a row on **every** session t..t+5, `bad_bar` is False on all 6 rows, and `adj_close` is present at t and t+5. Nothing is filled; no gap is bridged.
- A date needs ≥ `MIN_TICKERS_PER_DATE` (150) valid tickers, otherwise it gets no label.
- **Benchmark: equal-weight mean of the universe.** It is self-contained (no extra index download), it is the return of a basket you could hold, and the excess averages to exactly zero on every date. A cap-weighted index would need market caps we do not have. Because 5-day returns are right-skewed (a few big winners pull the mean up), fewer than half of stocks beat the mean: train beat-rate 48.7%. The median would give ~50/50 classes but is not a portfolio return.
- `ret` (trailing 1-day return) is kept in the label table for features.

### 3.3 Measured on the cleaned data (2026-11-12 snapshot)

Counts by `as_of_date` range (from `data/reports/baselines.json`):

| Split | Labelled | Tie | Invalid window | Sparse date | Purged at end |
|---|---|---|---|---|---|
| Train | 1,976,068 | 0 | 888 | 0 | 2,370 (2018-12-24 → 12-31) |
| Validation | 363,613 | 0 | 76 | 0 | 2,455 (2021-12-27 → 12-31) |
| Test | 600,013 | 0 | 2,470 | 0 | 0 (data end; last 5 sessions are invalid windows) |

- Valid tickers per date: minimum **340** (January 2000), median 347 (2000), 421 (2010), 480 (2019), 494 (2024 onward). **No date falls below 150, so the threshold currently drops nothing**; it is a guard for subsets or future universe changes.
- Beat-rate (scorable rows): train **0.4870**, validation **0.4921**. The test beat-rate is not computed.

### 3.4 Leakage rules for features (binding for the next step)
1. A feature for `as_of_date = t` may use only rows with `date ≤ t` for that ticker, and cross-sectional data only from dates `≤ t`.
2. **Ratios only, never price or volume levels.** `adj_close` is back-adjusted: its level on a past date changes whenever a *later* dividend or split occurs, so a level-based feature secretly encodes future events. Returns and ratios (`adj_close[t] / adj_close[t-k]`, `volume[t] / mean(volume[t-20..t-1])`) are unaffected. Volume is split-adjusted too.
3. Any feature window that touches a `bad_bar` row is invalid for that `as_of_date`; do not forward-fill.
4. Scalers, imputers and feature selection are fitted on the training split only.
5. Indicator warm-up: a feature is invalid until its window is full; such rows are dropped, not zero-filled.
6. Features may use only data at or before t, including any cross-sectional statistics (market means, ranks) computed on date t.
7. **No survivorship or membership inputs.** Fields from `tickers.csv` (current GICS sector, `date_added`, founded, …) describe today's index and are partly future knowledge (e.g. sectors were reclassified in 2018). They may define evaluation slices, never features. All results are conditional on today's survivors (ADR-0001).
8. `labels.check_feature_columns` enforces rules 6–7 mechanically: it rejects every forward-looking column produced by `label_frame` (`r5`, `market_r5`, `excess_ret`, `label`, `status`, `n_valid`, `target_date`, `split`) and every membership column. Feature code must call it on its final column list.
9. **Clarification of rule 2.** Dollar volume (close × volume) may be used as a cross-sectional rank. Close and volume are both split-adjusted, so their product is split-invariant, and close is not dividend-adjusted, so the product is point-in-time. Size and liquidity ranks are survivorship-suspect under rule 7 and are excluded from the default model set (ADR-0006).

### 3.5 Split policy (PROPOSED, [ADR-0005](../../docs/adr/0005-chronological-split-and-gates.md))

Splits are by `as_of_date`, identical for all tickers:

| Split | as_of_date range | Scorable rows (label + baseline input) |
|---|---|---|
| Train | 2000-01-03 → 2018-12-31 | 1,973,199 |
| Validation | 2019-01-02 → 2021-12-31 | 363,472 |
| Test (untouched) | 2022-01-03 → 2026-11-12 (pinned in `config.SPLITS`, independent of data refreshes) | not evaluated |

- **5-session purge:** a row belongs to a split only if both t and t+5 fall inside it, so the last 5 as_of_dates before each boundary are dropped (counts in 3.3).
- **Model selection protocol:** features, hyperparameters and model families are chosen with purged walk-forward folds **inside train**. Validation is used once per finalist, and the number of finalists judged on validation is recorded with the result (more trials make a passing CI less convincing).
- The test split is evaluated **once**, for the final reported numbers, only with `--include-test`. Its output goes to `data/reports/baselines_test.json` (never `baselines.json`), it defines no gates, and every evaluation appends a line to `data/reports/test_access_log.jsonl`.

### 3.6 Overlapping labels
Labels on adjacent dates share 4 of their 5 return days, so they are strongly autocorrelated. Validation's 363k rows cover 752 dates, roughly 150 non-overlapping 5-day periods. Consequences: confidence intervals use a **moving-block bootstrap** over dates (block 10 sessions, tickers of a date kept together); training metrics are optimistic because neighbouring rows are near-duplicates; flexible models (Random Forest) can overfit them.

## 4. Baselines (measured; `python -m stocksight_data.baselines`)

| Baseline | Rule | Train acc / bal. acc / Brier | Validation acc / bal. acc / Brier |
|---|---|---|---|
| Always majority | predict the training majority class (0 = lag; train beat-rate 0.4870) | 0.5130 / 0.5000 / 0.4870 | 0.5079 / 0.5000 / 0.4921 |
| Momentum 5d | beat if the trailing 5-day excess return > 0 | 0.4928 / 0.4924 / 0.5072 | 0.4954 / 0.4952 / 0.5046 |
| Reversal 5d | beat if the trailing 5-day excess return < 0 | 0.5072 / 0.5076 / 0.4928 | 0.5046 / 0.5048 / 0.4954 |
| Constant probability | `p_beat` = 0.4870 | 0.5130 / 0.5000 / 0.2498 | 0.5079 / 0.5000 / 0.2500 |

Trailing excess = trailing 5-session return minus the equal-weight mean over the same window, with the same validity rules applied backward (2,869 train and 141 validation labelled rows lack it and are not scored).

Reversal minus always-majority, balanced accuracy, block-bootstrap 95% CI: train **+0.0076 [+0.0049, +0.0106]**; validation **+0.0048 [−0.0067, +0.0156]**. Short-term reversal is real over 2000–2018 but **not significant in validation**. With single-date resampling the validation CI would have been [−0.0016, +0.0107], 1.8× narrower.

## 5. Promotion gates (frozen before any model is trained)

The rules are frozen in `data/reports/gates_frozen.json` (written once with `--freeze-gates`; a second freeze is refused). It records the dataset SHA-256, the best baseline (**reversal 5d**), the majority class (0), the constant probability (0.48703), the bootstrap settings, and reference thresholds on the 363,472 validation rows. `load_frozen_gates` refuses to run on a dataset with a different SHA-256.

A candidate model "beats baseline" only if **all** hold on validation, judged by `baselines.gate_model`:

| Gate | Rule (reference value on all validation rows) |
|---|---|
| Balanced accuracy | > reversal 5d balanced accuracy (0.50476) |
| Significance | Block-bootstrap (10 sessions, dates clustered) 95% CI lower bound of **model − reversal 5d** balanced accuracy > 0. A CI against any other baseline does not count (`check_gates` checks `ci_vs`). |
| Accuracy | ≥ always-majority accuracy (0.5079) |
| Calibration | Brier < constant-probability Brier (0.24996) |
| Slices | Every validation year ≥ 0.50 balanced accuracy (kept as a hard rule; note the best baseline itself scores 0.5009 in 2019 and 0.5003 in 2021) |

`gate_model` scores the model and every baseline on the **same rows** (label, trailing baseline input and model prediction all present) and recomputes the thresholds on those rows with the frozen rules, so a model with longer warm-up periods is not compared against numbers from a different row set. It reports the coverage of the frozen row set. If no model passes, "no evidence of skill beyond baselines" is an acceptable, reportable outcome.

## 6. Open questions for the team
1. Accept the equal-weight mean as the benchmark (vs median, or a downloaded cap-weighted index)? ADR-0004.
2. Accept the 2019–2021 validation window? It includes the 2020 crash and rebound.
3. Is 5 sessions the right horizon for the app, or should 10/20 be compared later as separate experiments?
4. Retraining cadence and prediction-history retention (SPECIFICATION open decisions; backend phase).

## 7. Labels and baselines (MLE-03): done
- `stocksight_data.labels`: `label_frame` / `build_labels` (5-session market-relative labels with statuses), `trailing_excess`, `assign_split` (purge).
- `stocksight_data.baselines`: baselines, metrics, moving-block bootstrap (raises on undefined draws), `check_gates`, `gate_model`, frozen gates, label diagnostics; writes `data/reports/baselines.json`. Reports record the dataset SHA-256, git state, and Python/library versions; exact versions are pinned in `ml/requirements.lock`.
- `ml/tests/`: 87 tests. Mutation checks (each in a fresh process): label at t+1 → 10 failures; skip the `bad_bar` window check → 5; drop the purge → 3; trailing excess using the future → 3; significance CI accepted against any baseline → 1; `gate_model` scoring all rows → 1; undefined bootstrap draws dropped → 1.
- Reviewed by the `mle-reviewer` agent (APPROVE WITH WARNINGS); its HIGH findings (significance baseline, test-split guard and frozen gates, survivorship inputs) are fixed above. Deferred to the features step: purged walk-forward folds and per-date ranking metrics (AUC / rank IC) as a secondary report.

## 8. Features (MLE-04): done
- There are 59 point-in-time features in `stocksight_data.features` (catalog and train-only signal in [features.md](features.md); design in ADR-0006).
- The default model set is `model_features()`: 54 features, excluding market-state and survivorship-suspect ones.
- Purged walk-forward folds inside train are in `stocksight_data.folds`.
- Train-only screening: the dominant signal is short-term reversal (best per-date IC about −0.027), and it roughly halves between 2000–09 and 2010–18. 12-1 momentum is not significant after Benjamini-Hochberg adjustment.

## 9. Next experiment (MLE-05: first model)
1. **Logistic regression** on `model_features()`, with train-fitted winsorisation or ranks and a missing-value strategy. Hyperparameters are chosen on purged walk-forward folds inside train.
2. **One validation run** through `gate_model`, recorded in the observation ledger with the number of finalists.
3. **Random forest** next, regularised for overlapping labels, then error analysis by year, sector (as a slice only) and volatility.
