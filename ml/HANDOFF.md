# ML handoff (branch `feature/ml-sp500-dataset`, 2026-11-14)

Status: data pipeline, labels, baselines, frozen promotion gates, **59 point-in-time features** and **model selection plus one validation judgment** are done and tested. **No model passes the frozen gates.** All three finalists beat reversal 5d on the point estimate, but none is significant. The test split is untouched. Nothing on this branch is merged; decisions in ADR-0003 to ADR-0006 are still *proposed* and need team review.

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
| Models: selection and the validation judgment | `stocksight_data/modeling.py` | LR, HGB and RF; `select`, `rescore`, `judge`; validation-access guard; every experiment in [docs/ledger.md](docs/ledger.md) |
| Tests | `tests/` | 447 unit tests plus 3 real-data tests; `pytest -m "not data"` runs without the dataset |
| Frozen gates, baseline and feature reports | `reports/` | tracked copies of `data/reports/` and `data/features/features.meta.json` (which are gitignored) |

Key numbers (validation, 2019–2021): beat-rate 0.4921. Best baseline is reversal 5d, with balanced accuracy 0.5048, which is not significant. A model must reach balanced accuracy above 0.50476 with a block-bootstrap CI lower bound above 0 against reversal 5d, accuracy of at least 0.5079, Brier below 0.24996, and no validation year below 0.50.

Models (validation access #1, 3 finalists, 34 configs tried): the best was an average of LR and HGB. Balanced accuracy 0.5103, +0.0055 vs reversal 5d with CI [−0.0036, +0.0145]; accuracy 0.5104; Brier 0.24978. That passes 4 of 5 gates and fails significance. HGB alone scored 0.5100 and RF+Platt 0.5085, with the same pattern.

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
1. **Team review** of ADR-0003 to ADR-0006 and of contract section 6. The gate design needs particular attention:
   - A single `p_beat` with a 0.5 threshold has to pass balanced accuracy, accuracy and Brier at once.
   - At this signal strength those three conflict (see [docs/ledger.md](docs/ledger.md), iterations 1–2).
2. **Decide the outcome of MLE-05.** Two options:
   - Report "no model passes" and pick one model for the single test run (`baselines --include-test`, plus a test scorer for that model, which does not exist yet).
   - Run the next recorded experiment first: a feature for the date-level beat-rate (cross-sectional skew of trailing returns), added to the feature registry with its leakage tests. It counts as a success if fold Brier improves by more than about 6e-5 without losing balanced accuracy.
3. **Re-judging validation:**
   - Validation access #1 used 3 of the 3 allowed candidates.
   - Any further `judge` run needs `--reason`. Record it in the ledger, and count it with the 34 configurations already tried.
4. **Model artifact and serving.** Not started:
   - Save a versioned bundle (estimator, preprocessor, spec, data SHA).
   - Batch-score after each close.
   - Follow the output schema in contract section 2.

## Gotchas
- `modeling.select` takes about 25 minutes (the stride-1 RF alone about 8). `rescore` recomputes metrics from `data/models/oof/*.parquet` without refitting.
- Eligibility and ranking use **folds 1–5**: fold 0 cannot be calibrated. All-fold summaries are kept as `summary_all_folds`.
- The fold margins behind the finalists are noise-sized (the Brier gap for HGB is about 0.3 bootstrap SE). Treat the finalist order as weak evidence.
- `label_frame` returns forward-looking columns (`r5`, `excess_ret`, `status`, `n_valid`, …) next to the feature-safe `ret`. Never join it into features without `check_feature_columns`.
- Sector, date added and other `tickers.csv` fields are today's membership: evaluation slices only, never features (survivorship, ADR-0001).
- The size and liquidity ranks (`rank_dollar_vol_63d`, `rank_amihud_21d`) show strong train IC, but that partly reflects survivorship (today's small members are past winners). Their importance in a model is not evidence of skill.
- The short-term reversal signal roughly halves between 2000–09 and 2010–18, and the best naive baseline is not significant in validation. "No model passes the gates" is a realistic and acceptable outcome.
- Adjacent labels share 4 of their 5 return days. Training metrics look better than they are, and confidence intervals must use the block bootstrap.
- The raw 2026-11-13 bar was provisional when downloaded. Cleaning cuts at 2026-11-12, so it is not used.
- The frozen gates record `code.dirty: true`, because they were produced before this commit. The code that produced them is this commit.
