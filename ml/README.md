# Machine learning foundation

The pipeline covers download, cleaning, labels, baselines, features and model selection (below). No model artifact is saved and nothing is served yet: the trained models are judged against frozen gates, but none is wired to the backend.

The prediction target, label rules, split policy, baselines and promotion gates are drafted in [docs/prediction-contract.md](docs/prediction-contract.md), pending team review.

**Picking this up?** Start with [HANDOFF.md](HANDOFF.md). It covers status, reproduction, next steps and gotchas.

## S&P 500 daily price dataset

`stocksight_data/` downloads daily bars (2000 onward) for the current S&P 500 constituents from Yahoo Finance via yfinance. It uses its own `requirements.txt`, separate from the backend.

```powershell
cd ml
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m stocksight_data.universe   # tickers + GICS sectors from Wikipedia
.\.venv\Scripts\python.exe -m stocksight_data.download   # prices (resumable; --force, --tickers AAPL MSFT)
.\.venv\Scripts\python.exe -m stocksight_data.check      # data-quality report (never modifies data)
```

Output goes to `data/sp500/` at the repo root (git-ignored; override with `STOCKSIGHT_DATA_DIR`):

- `tickers.csv`: Wikipedia symbol, Yahoo symbol (`BRK.B` → `BRK-B`), name, sector, sub-industry, date added, CIK.
- `prices/<TICKER>.parquet`: `date, ticker, open, high, low, close, adj_close, volume, dividends, stock_splits`.
- `manifest.json`: run time, request parameters, yfinance version, per-ticker status/rows/date range/fetch time, failures.
- `check_report.json`: per-ticker issues and thresholds.

Behaviour:

- Downloads run through the last *completed* NYSE session (`exchange_calendars`, which handles holidays and early closes). Bars for unfinished sessions are dropped.
- Downloads are batched (50 tickers), and failed tickers are retried in smaller batches with backoff. Remaining failures are recorded rather than raised.
- Reruns skip tickers whose file reaches the target date. Stale files are re-downloaded in full, not appended, because Yahoo recomputes historical `adj_close` after each dividend.
- Yahoo revises the latest bar for hours after the close. A bar fetched less than 12 h after its close is marked `last_bar_provisional` and re-fetched on the next run.

### Cleaning step

```powershell
.\.venv\Scripts\python.exe -m stocksight_data.clean --end-date 2026-11-12
```

This step combines the raw files into `data/clean/prices_clean.parquet`: one long table, sorted by ticker and date, with the raw columns plus `bad_bar`. It also writes `data/clean/clean_log.json` with per-rule counts. Raw files are never modified. Rules, applied per ticker in order:

1. Drop bars after `--end-date`.
2. Trim stale pre-listing history. This applies only when more than half of a ticker's first 252 rows have zero volume. The stale block then ends at the first run of 252 consecutive rows with no zero-volume rows, and the ticker starts there. Zero-volume rows later in a history never trigger a trim.
   - Only SW, FERG and AMCR qualify. Their new start dates are 2024-07-08, 2021-03-08 and 2019-06-11.
   - SW then has fewer than 756 rows, so step 6 drops it.
   - If a ticker outside `config.STALE_REVIEWED_TICKERS` triggers this rule, the run fails before writing, so the trim can be reviewed first.
3. Drop leading rows with `adj_close < 0.10`. Tiny-price rows in the middle of a history are kept, and their count is logged.
4. Set prices to NaN for the bars listed in `config.EXCLUSIONS`.
5. Handle the remaining zero- or missing-volume rows:
   - A flat bar (open = high = low = close) gets NaN prices.
   - A bar whose prices vary keeps its prices and gets NaN volume.
6. Drop tickers with fewer than 756 rows.

Sanity checks are enforced:
- no duplicate (ticker, date) pairs;
- dates strictly increasing within each ticker;
- no date after the cutoff;
- every row with real prices has volume > 0 or NaN;
- prices are NaN exactly on `bad_bar` rows;
- no ticker below 756 rows;
- no unreviewed ticker trimmed by rule 2.

If a check fails, only the log is written and the command exits with an error.

**`bad_bar` contract.** `bad_bar` is True exactly where cleaning set the prices to NaN: excluded bars and flat no-trade bars. The rows are kept so date gaps stay visible.
- Treat any return or feature window that touches a `bad_bar` row as invalid.
- Never forward-fill across one. For excluded bars, the bad price level sits on both sides of the bar.
- `volume` can also be NaN on rows whose prices are fine (HWM, late 2016).

### Labels, baselines and tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # adds pytest, pytest-cov
.\.venv\Scripts\python.exe -m stocksight_data.baselines             # train + validation report
.\.venv\Scripts\python.exe -m pytest                                # unit tests (+ real-data test if built)
.\.venv\Scripts\python.exe -m pytest -m "not data"                  # unit tests only
```

- `stocksight_data/labels.py` builds the target: does the stock beat the equal-weight mean of the universe over the next 5 NYSE sessions? `label = 1` when `r5 - market_r5 > 0`.
  - A row is valid only with rows on all 6 sessions t..t+5, no `bad_bar` in them, and at least 150 valid tickers on the date. Exact ties are excluded.
  - Splits purge the last 5 sessions before each boundary, because t+5 must stay in the same split.
  - The benchmark switch (`MARKET_BENCHMARK`) and the thresholds live in `config.py`.
- `stocksight_data/baselines.py` evaluates four baselines: always-majority, 5-day momentum, 5-day reversal, and constant probability.
  - Confidence intervals use a moving-block bootstrap over dates (10 sessions), because adjacent labels share 4 of 5 return days.
  - It writes `data/reports/baselines.json` with the dataset's SHA-256 and the git state, and holds `check_gates`.
- Measured on validation: beat-rate 0.4921. The best baseline is reversal 5d (balanced accuracy 0.5048, not significant).
- Gates every model must pass: balanced accuracy > 0.50476 with a significant gain over reversal 5d, accuracy ≥ 0.5079, Brier < 0.24996.
  - The rules are frozen once in `data/reports/gates_frozen.json`, tied to the dataset's SHA-256.
  - Judge a model with `gate_model(frame, p_model, load_frozen_gates(...))`. It scores the model and the baselines on the same rows.
- `--include-test` writes `data/reports/baselines_test.json` and appends to `test_access_log.jsonl`. Use it once, for the final model.
- Feature code must call `labels.check_feature_columns` on its column list. It rejects forward-looking label columns and `tickers.csv` membership fields such as sector and date added.
- For exact reproduction, install from `requirements.lock`.
- The test split is only evaluated with `--include-test`. Use it once, for the final report.

Definitions and thresholds are in [docs/prediction-contract.md](docs/prediction-contract.md) and the ADRs in `docs/adr/`.

### Features

```powershell
.\.venv\Scripts\python.exe -m stocksight_data.features         # data/features/features.parquet + features.meta.json (~1 min)
.\.venv\Scripts\python.exe -m stocksight_data.feature_report   # train-only report -> data/reports/feature_report.json (~2 min)
```

- There are 59 point-in-time features: momentum and reversal, risk, candle and range, trend, volume, income, and market state.
- The default model set is `features.model_features()` (54 features).
- `folds.purged_walk_forward` gives six purged 2-year evaluation folds inside train, for model selection.
- The feature catalog, train-only signal and modelling recommendations are in [docs/features.md](docs/features.md).

### Models: selection and the validation judgment

```powershell
.\.venv\Scripts\python.exe -m stocksight_data.modeling select    # every config on train folds (~25 min) -> data/reports/model_selection.json
.\.venv\Scripts\python.exe -m stocksight_data.modeling rescore   # recompute fold metrics from stored out-of-fold predictions (no refit)
.\.venv\Scripts\python.exe -m stocksight_data.modeling judge     # finalists, ONCE, on validation -> data/reports/model_validation.json
```

- `stocksight_data/modeling.py` holds the harness. It fits logistic regression, HistGradientBoosting and random forests on `model_features()`.
- **Selection:**
  - Selection runs on `purged_walk_forward` folds and never computes a validation outcome. Labels are built from prices cut at the train end.
  - Per-date cross-sectional ranks are computed on every ticker before labels are joined.
  - Winsorising bounds, the missing-value indicator set and Platt maps are fitted on fit rows only.
  - Models fit on every 5th date, because adjacent labels share 4 of 5 return days.
- **Judging:**
  - `judge` scores at most 3 finalists through `baselines.gate_model`, and recomputes them with the finalist rule first.
  - Every access is logged to `data/reports/validation_access_log.jsonl`.
  - Re-judging, or judging more than 3 candidates in total, needs `--reason`.
  - The test split is refused everywhere in this module.
- Every experiment, the finalist rule and the validation result are in [docs/ledger.md](docs/ledger.md). Tracked copies of the reports are in `reports/`.

Data caveats to keep in mind when defining targets and features:

- `open/high/low/close/volume` are **split-adjusted** by Yahoo even with `auto_adjust=False`, so they are not the historical prints. `adj_close` is also dividend-adjusted.
- Spin-offs and special dividends appear as huge one-day drops in `close` (MO 2008, KDP 2018, WY 2010); `adj_close` mostly absorbs them. EXPE 2011-12-21 and JCI 2007-07-02 remain distorted even in `adj_close`.
- Some tickers carry long stale pre-listing histories (flat bars with zero volume: SW before 2024-07, FERG before 2021-04, AMCR before 2019-07).
- The universe is today's constituents, so history from 2000 has **survivorship bias**: delisted and removed companies are absent.

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
