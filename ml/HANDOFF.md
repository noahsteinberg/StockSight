# ML handoff (branch `feature/ml-sp500-dataset`, 2026-11-14)

Status: data pipeline, labels, baselines and frozen promotion gates are done and tested. **No features or models exist yet.** Nothing on this branch is merged; decisions in ADR-0003 to ADR-0005 are still *proposed* and need team review.

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
| Tests | `tests/` | 87 tests; `pytest -m "not data"` runs without the dataset |
| Frozen gates and baseline report | `reports/gates_frozen.json`, `reports/baselines.json` | tracked copies of `data/reports/` (which is gitignored) |

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

## Next steps
1. **Team review of ADR-0003 to ADR-0005** (price basis, target, splits and gates), plus the open questions in contract section 6.
2. **`features.py`**: ratio-only features, each with a hypothesis and a leakage test (changing a price after t must not change the feature). Call `check_feature_columns` on the final column list.
3. **Purged walk-forward folds inside train** for model selection. Use validation once per finalist, and record how many finalists were judged on it.
4. **Logistic regression**, then random forest. Judge each with `gate_model`. Add per-date AUC or rank IC as a secondary report.
5. **The test split, once**, for the final model only: `baselines --include-test` writes `baselines_test.json` and logs the access.

## Gotchas
- `label_frame` returns forward-looking columns (`r5`, `excess_ret`, `status`, `n_valid`, …) next to the feature-safe `ret`. Never join it into features without `check_feature_columns`.
- Sector, date added and other `tickers.csv` fields are today's membership: evaluation slices only, never features (survivorship, ADR-0001).
- Adjacent labels share 4 of their 5 return days. Training metrics look better than they are, and confidence intervals must use the block bootstrap.
- The raw 2026-11-13 bar was provisional when downloaded. Cleaning cuts at 2026-11-12, so it is not used.
- The frozen gates record `code.dirty: true`, because they were produced before this commit. The code that produced them is this commit.
