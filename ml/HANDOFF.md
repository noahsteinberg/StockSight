# ML handoff (branch `feature/ml-sp500-dataset`, 2026-11-14)

Status: data pipeline, labels, baselines, frozen promotion gates and **59 point-in-time features** are done and tested. **No models exist yet.** Nothing on this branch is merged; decisions in ADR-0003 to ADR-0006 are still *proposed* and need team review.

## Read first
1. [docs/prediction-contract.md](docs/prediction-contract.md): the target, label rules, leakage rules, splits, baselines and gates.
2. [../docs/adr/](../docs/adr/): five decisions with the alternatives that were rejected.
3. [README.md](README.md): commands.

## What exists
| Piece | Where | Notes |
|---|---|---|
| Download (Yahoo, S&P 500, 2000 onward) | `stocksight_data/universe.py`, `download.py` | resumable; `manifest.json` records failures |
| Data checks (report only) | `stocksight_data/check.py` | |
| Cleaning → `prices_clean.parquet` | `stocksight_data/clean.py` | asserted invariants; `bad_bar` contract (ADR-0002) |
| Target: beat the equal-weight mean over 5 sessions | `stocksight_data/labels.py` | `label_frame`, `build_labels`, `trailing_excess`, `assign_split`, `check_feature_columns` |
| Baselines, block bootstrap, gates | `stocksight_data/baselines.py` | `gate_model(frame, p_model, load_frozen_gates(...))` judges a model |
| Features (59) and the default model set (54) | `stocksight_data/features.py` | registry with hypotheses; `model_features()`; catalog in [docs/features.md](docs/features.md) |
| Train-only feature report | `stocksight_data/feature_report.py` | per-date rank IC, block-bootstrap CIs, BH-adjusted; never computes validation outcomes |
| Purged walk-forward folds | `stocksight_data/folds.py` | six 2-year evaluation blocks inside train, for model selection |
| Tests | `tests/` | 400 unit tests plus 3 real-data tests; `pytest -m "not data"` runs without the dataset |
| Frozen gates, baseline and feature reports | `reports/` | tracked copies of `data/reports/` and `data/features/features.meta.json` (which are gitignored) |

Key numbers (validation, 2019–2021): beat-rate 0.4921. Best baseline is reversal 5d, with balanced accuracy 0.5048, which is not significant. A model must reach balanced accuracy above 0.50476 with a block-bootstrap CI lower bound above 0 against reversal 5d, accuracy of at least 0.5079, Brier below 0.24996, and no validation year below 0.50.

## Reproducing
```powershell
cd ml
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock      # exact versions used
.\.venv\Scripts\python.exe -m pytest -m "not data"                  # should pass without data
```

**The dataset is not in git** (78 MB). Get it one of two ways:
- **Same snapshot:** copy `data/clean/prices_clean.parquet` from the author. The reports match it only if its SHA-256 starts with `ee0b2ed66c8a`. Then copy `ml/reports/gates_frozen.json` to `data/reports/` and run `pytest`. The data-marked tests check the hash.
- **Rebuild:** run `universe`, then `download`, then `clean --end-date 2026-11-12`, then `baselines`. A rebuild gets newer Yahoo data: the constituent list changes, and back-adjusted prices are revised after every dividend. The hash will therefore differ, and `load_frozen_gates` will **refuse** the old gates. That refusal is intentional. If you rebuild, re-freeze deliberately with `baselines --freeze-gates` after deleting the old file, and record why in the observation ledger.

Features are rebuilt from the cleaned data with `python -m stocksight_data.features` (about 1 minute, 535 MB, not in git). The train-only report is rebuilt with `python -m stocksight_data.feature_report`.

## Next steps
1. **Team review of ADR-0003 to ADR-0006** (price basis, target, splits and gates, feature design), plus the open questions in contract section 6.
2. **Logistic regression** on `model_features()`:
   - Use train-fitted winsorisation or ranks, and a missing-value strategy (see "Recommendations" in docs/features.md).
   - Choose hyperparameters on `purged_walk_forward` folds inside train.
3. **One validation run** through `gate_model`. Record it in an observation ledger, with the number of finalists judged on validation. Add per-date AUC or rank IC as a secondary report.
4. **Random forest**, regularised for overlapping labels. Then error analysis by year, sector (as a slice only) and volatility.
5. **The test split, once**, for the final model only: `baselines --include-test` writes `baselines_test.json` and logs the access.

## Gotchas
- `label_frame` returns forward-looking columns (`r5`, `excess_ret`, `status`, `n_valid`, …) next to the feature-safe `ret`. Never join it into features without `check_feature_columns`.
- Sector, date added and other `tickers.csv` fields are today's membership: evaluation slices only, never features (survivorship, ADR-0001).
- The size and liquidity ranks (`rank_dollar_vol_63d`, `rank_amihud_21d`) show strong train IC, but that partly reflects survivorship (today's small members are past winners). Their importance in a model is not evidence of skill.
- The short-term reversal signal roughly halves between 2000–09 and 2010–18, and the best naive baseline is not significant in validation. "No model passes the gates" is a realistic and acceptable outcome.
- Adjacent labels share 4 of their 5 return days. Training metrics look better than they are, and confidence intervals must use the block bootstrap.
- The raw 2026-11-13 bar was provisional when downloaded. Cleaning cuts at 2026-11-12, so it is not used.
- The frozen gates record `code.dirty: true`, because they were produced before this commit. The code that produced them is this commit.
