# Research round 2: controlled follow-up

## Scope frozen before fitting

Base: `589d6c53197e33664f8fa00a801a6117a974192c`, on the separate `research/ml-round2` branch. The five-session, equal-weight market-relative label, original promotion gates, previous reports, validation log, and final test reservation remain unchanged.

This round repeats `hgb_raw_wide_bal` and fits exactly four new configurations. It does not run the old search grid, recalibrate candidates, judge validation, evaluate test performance, or save an inference artifact.

| Configuration | Single change from the repeated baseline |
| --- | --- |
| `hgb_raw_wide_bal` | None: reproduce the existing uncalibrated gradient booster |
| `compact_12` | Use the twelve features agreed in the implementation plan |
| `trailing_5_years` | Limit each fold's fit data to the preceding five calendar years |
| `trailing_10_years` | Limit each fold's fit data to the preceding ten calendar years |
| `context_skew_21d` | Add cross-sectional skew of clean trailing 21-session returns |

The compact inputs are `ex_ret_1d`, `ex_ret_5d`, `ex_ret_21d`, `mom_12_1`, `vol_21d`, `vol_ratio_21_63`, `close_loc_1d`, `gap_1d`, `dist_ma_10`, `dist_ma_200`, `rsi_14`, and `volu_ratio_1_21`.

The additional market feature is registered separately in `research_round2.EXPERIMENT_FEATURES`; it does not change the original feature registry or default model inputs. It uses unbiased sample skew across at least 150 finite, clean trailing returns on the current date, before joining future labels. A constant or sparse cross section gives a missing value. A bad individual window cannot contribute to the cross-sectional statistic.

The first baseline loader was interrupted under laptop memory pressure before completing a fold. Its original manifest is preserved locally as `pre-memory-fix-manifest.json`. The runner now reads only needed columns and skips rank arrays that the raw HGB never uses. `fit_model` accepts an optional explicit input-column list, preserving its original default behavior. A regression test requires identical predictions through the old and memory-saving paths. This changes memory use, not model settings or evaluation criteria.

## Comparison protocol

Baseline data: the frozen 2026-11-12 cleaned snapshot has 494 current S&P 500 constituents and 2,947,953 price rows. The rebuilt registry has 59 features, with 54 default model inputs. The target is one when the stock's adjusted-close return over the next five NYSE sessions exceeds the equal-weight mean return of all valid stocks; ties and invalid windows are excluded.

Only 2000-2018 prices reach this round's label construction, producing 1,976,068 training examples. The six evaluation folds cover 2007-2018. The already-examined 2019-2021 validation period and reserved 2022-2026 test period are not model-scored by this runner. The previous validation study found no candidate passing all frozen gates; this training-only follow-up does not reset that result.

- Use the existing six purged walk-forward folds, with gradient-boosting settings, seed, stride, and early-stopping procedure unchanged. Report all six folds; use folds 1-5 for selection, matching the existing common-fold rule.
- A rolling fit window is `(fit_end - N calendar years, fit_end]`, still requiring each fit label's target to end by `fit_end`. The five-session boundary purge remains intact.
- All configurations use the same evaluation stock/date rows: valid labels, a trailing reversal-baseline input, and available cross-sectional context. Report the coverage loss explicitly. Per-stock feature NaNs remain supported by the original raw HGB preprocessor.
- The majority and constant-probability references use the original expanding fit fold's strided base rate for every configuration. Their thresholds do not change to favor the short-window models.
- Keep every attempt, including failed/interrupted attempts. Store predictions and metrics for every completed fold; verify their hashes when resuming.
- Check the repeated baseline against the archived baseline on its original evaluation rows as well as scoring it on the round's common rows. Stop if accuracy, balanced accuracy, or Brier differ by more than 1e-6.
- Report accuracy, balanced accuracy, Brier, coverage, original baseline scores, and per-fold results. Compute 1,000 paired date-block bootstrap draws (10-session blocks, seed 0) against reversal and the repeated model. Brier differences below zero favor the new model. These comparisons are exploratory and are not new promotion judgments.
- Apply the original `common_summary`, eligibility, and one-finalist-per-family ranking functions. All configurations in this round are HGB. Preserve the original 34-configuration history and count the four new attempts separately.
- Never automatically run validation or final test. Further validation access needs a separately documented decision and reason under the existing guard.

## Reproduce and resume

Use Python 3.12 and install `ml/requirements.lock` into a separate environment. The original run used 3.12.5; this machine uses 3.12.14 with the same package pins. Record that patch-version difference rather than claiming bit-for-bit environment identity.

Place the matching snapshot at `data/clean/prices_clean.parquet`:

```text
ee0b2ed66c8abb87e0cf36798a32258bc902c0e1687ddee2a485c80b44216e89
```

Copy the tracked `gates_frozen.json`, `model_selection.json`, and `validation_access_log.jsonl` from `ml/reports/` to `data/reports/`, as described in HANDOFF. Do not replace or regenerate them.

From `ml/`, with the environment's Python:

```powershell
python -m pytest -m "not data" -q
python -m stocksight_data.research_round2 prepare
python -m stocksight_data.research_round2 audit
python -m pytest -m data -q
python -u -m stocksight_data.research_round2 run --only hgb_raw_wide_bal --threads 4
# Review baseline reproducibility before starting the four new configurations.
python -u -m stocksight_data.research_round2 run --threads 4
python -m stocksight_data.research_round2 report
```

`prepare` rebuilds the original features once. Its manifest freezes input/source hashes, package versions, the five configurations, and hashes of protected prior reports. `audit` independently traces five real stock/date cases using training-period prices only. Existing data tests also check the already-frozen baseline invariants; they do not judge a candidate or report test-period model performance.

Repeating `run` resumes completed folds. It writes `data/research_round2/<configuration>/fold-N.parquet` and `.json`, then prints a single completion line per fold. `ml/reports/research_round2_attempts.jsonl` records attempts, and `ml/reports/research_round2.json` is the shareable comparison report. Predictions, features, and raw run logs remain ignored by Git. No browser or chat session is required while Python runs.

On Windows, `scripts/run-round2.ps1 -Python <interpreter> -Stage baseline` performs prepare, audit, and baseline reproduction. `-Stage experiments` resumes the bounded run; `-Stage report` rebuilds the summary without training. A `run.lock` stores the owner PID; if a process was forcibly terminated, verify that PID is no longer running before removing the stale lock. Do not run two copies concurrently.

If a source/input changes, the manifest refuses to mix results. Preserve the old output before explicitly starting a revised run. Never erase the tracked attempts or prior validation history to hide retries.

## Known limits and application handoff

The universe is today's index constituents, so survivorship bias remains. Historical adjusted-price data is not a fully point-in-time vendor archive. Short-term relationships may decay, and a training-fold improvement does not establish unseen-period skill. Feature-file bytes can differ across platforms even with matching numerical values; the baseline reproduction and real-data tests check behavior directly.

The proposed application fields remain `ticker`, `as_of_date`, `target_date`, `p_beat`, `call`, `model_version`, and `data_snapshot`. This round adds no serving endpoint. The application should retain its prediction-unavailable state until the separate model-selection and serving decisions are made.

## Verification

On the pinned environment, 463 unit tests and all 3 dataset tests passed (466 total). This includes the new feature/window/input-cutoff/locking controls and a regression test proving that explicit raw feature columns give the same predictions as the original rank-discovery path. Existing pandas timezone deprecation warnings remain; they did not cause test failures. Dependency consistency, focused Python lint, and Git whitespace checks passed.

Exactly 30 unique model/fold completions were recorded: six for the repeated reference and six for each of four new configurations. The original memory-heavy loader's interruption remains in the attempt log. Original research reports and validation history were checked against both the pre-run hashes and the branch base. No test-access log was created.

## Results

Completed 2026-11-14T21:11:10+00:00. The baseline and all four new configurations completed six folds. Selection summaries use folds 1-5, matching the original rule. **No validation or final-test model evaluation was run.**

### Baseline and data audit

- The cleaned dataset SHA-256 matches the original frozen snapshot.
- All six baseline folds reproduced archived accuracy, balanced accuracy, and Brier within 1e-6. Maximum absolute difference: 0.
- Five independent stock/date traces checked labels, calendar targets, bad bars, per-stock historical returns, and the late-2018 boundary.
- Coverage ranges from 99.9509% to 99.9713% of each original evaluation fold. All configurations use identical common observations.
- Existing gates, original experiment reports, and validation-access history remain protected by their pre-run hashes.

### Comparison

The first three metrics are unweighted means over the five common folds. The final column pools their observations for a paired date-block bootstrap difference against reversal. These two summaries have different weighting and should not be subtracted from one another.

| Configuration | Mean balanced accuracy | Mean accuracy | Mean Brier (lower better) | Folds passing proxies | Pooled gain over reversal [95% CI] |
| --- | --- | --- | --- | --- | --- |
| `hgb_raw_wide_bal` | 0.509163 | 0.511207 | 0.249888 | 3/5 | +0.004406 [+0.000821, +0.008178] |
| `compact_12` | 0.509030 | 0.510125 | 0.250014 | 0/5 | +0.003815 [+0.000335, +0.007683] |
| `trailing_5_years` | 0.507757 | 0.506973 | 0.250020 | 1/5 | +0.002281 [-0.001392, +0.006305] |
| `trailing_10_years` | 0.508093 | 0.509722 | 0.249923 | 1/5 | +0.003156 [-0.000581, +0.007302] |
| `context_skew_21d` | 0.509591 | 0.511543 | 0.249919 | 2/5 | +0.004949 [+0.000955, +0.009021] |

New configurations eligible under existing rules: none.

### Recommendation

None of the four new configurations meets the existing training-fold eligibility rules. Stop this round; retain the prior approach as the comparison reference. This does not overturn the earlier finding that no model passed validation.

Four configurations are new, in addition to the previous 34. The repeated baseline is a reproduction attempt, not another novel configuration. Confidence intervals are exploratory and unadjusted for choosing among configurations. Passing training proxies does not mean passing the frozen validation gates. The previous validation results have already been seen, so they cannot be described as a fresh holdout.

The machine-readable report contains all six folds, simple-baseline scores, coverage, runtime, and paired balanced-accuracy/Brier differences against both reversal and the reproduced model. Per-fold predictions remain in ignored local storage. Attempt logs retain failures and interruptions.

### Application handoff

The prediction remains a five-session relative beat/lag research task. No inference artifact or API endpoint was added. Continue frontend/API work against the agreed fields and an explicit prediction-unavailable state. A serving decision needs separate review.
