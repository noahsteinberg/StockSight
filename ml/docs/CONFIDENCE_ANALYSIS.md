# Run the saved-prediction diagnostic

The user completed the first full run in 7 seconds on November 14, 2026. Findings and follow-up checks are recorded in [CONFIDENCE_REVIEW.md](CONFIDENCE_REVIEW.md). The command below reruns the saved-prediction analysis without training.

## One action

Double-click `Run-Confidence-Analysis.cmd` in the `StockSight-ml-research` folder. Or, from a terminal in that folder:

```powershell
.\Run-Confidence-Analysis.cmd
```

The launcher uses the pinned environment already prepared in `%TEMP%\stocksight-ml-round2-env`. It falls back to `ml\.venv` if available. It does not install anything. If neither exists, it stops and asks for setup help. The window stays open so you can read completion or errors.

Keep the laptop awake until it finishes. No active chat session is needed. Run just one copy; this is a single lightweight analysis, not a parallel training batch. The first full run took 7 seconds; runtime can vary.

## What it does

- Reads only the existing `hgb_raw_wide_bal` predictions from six saved training folds and the matching cleaned dataset.
- Verifies dataset/prediction hashes before analysis. It never downloads data, rebuilds features, fits a model, or scores validation/final test.
- Evaluates folds 1-5. Fold 0 supplies initial cutoff information only.
- Uses four fixed intended answer rates: 100%, 50%, 25%, and 10%. The score is `abs(p - 0.5)`. For each later fold, cutoffs use only earlier folds' scores, never current/future outcomes. Exact cutoff ties remain included, so actual coverage can differ.
- Compares every policy with reversal, majority-class, and constant-probability baselines on the identical selected observations. Reports class balance, actual coverage, per-fold behavior, and reliability bins.
- Uses 1,000 paired 10-date moving-block bootstrap draws within each fold, preserving zero-answer dates. Undefined draws are reported instead of silently dropped. The intervals are exploratory and unadjusted for multiple comparisons.
- Never automatically chooses a winning cutoff, changes promotion gates, or starts another experiment.

This examines whether larger model margins correspond to better decisions. It does not assume the margins are calibrated confidence, and it does not make the already-examined training folds a fresh holdout.

## What to send back

The script writes these files under `data/confidence-analysis/`:

1. `summary.md`: small readable results table and paired uncertainty.
2. `results.json`: detailed metrics and provenance.
3. `run.log`: progress, elapsed time, and any error traceback.

Send `summary.md` and `results.json` after success. If it fails, send `run.log`; do not rerun training or regenerate data to try to fix it. Existing training checkpoints, reports, and validation history remain unchanged. These output files are ignored by Git.

For an input check without analysis, run the launcher with `--check`. A missing dataset or saved prediction is an error, never a reason to fall back to training.
