# Observation ledger: modelling (MLE-05)

Every experiment is recorded here, including the ones that did not work, and the number of
configurations tried is kept with every validation result (contract 3.5: more trials make a
passing CI less convincing). Machine-readable results: `data/reports/model_selection.json`
(train folds) and `data/reports/model_validation.json` (validation), with tracked copies in
`ml/reports/`. Validation accesses are logged in `data/reports/validation_access_log.jsonl`.

Shared setup for every iteration below:

- Data: dataset SHA-256 `ee0b2ed66c8a…`, features from `python -m stocksight_data.features`, 54 features (`model_features()`).
- Train frame: 1,976,068 labelled rows on 4,774 dates (2000-01-03 → 2018-12-24). Labels come from prices cut at 2018-12-31, so validation outcomes are never computed during selection.
- Folds: `purged_walk_forward`. There are six 2-year evaluation blocks (2007–2018) with an expanding fit window and a 5-session purge.
- Overlap: models fit on every 5th date unless stated otherwise. Metrics use every date of the evaluation fold.
- Per fold:
  - Balanced accuracy and accuracy at p ≥ 0.5.
  - Accuracy of the fit-fold majority class.
  - Brier, plus the Brier of the fit-fold beat rate as a constant.
  - Log-loss, per-date AUC and per-date rank IC.
  - reversal_5d balanced accuracy on the same rows.
- Gate proxies per fold: beats reversal on balanced accuracy, accuracy ≥ majority, and Brier < constant. These are the three point gates without the bootstrap CI and the yearly rule.

The numbers in iterations 1–4 are means over all 6 folds, as first computed. From iteration 4b on, eligibility and ranking use folds 1–5 (see H1).

---

## Iteration 1: grid of 22 configs (10 LR, 8 HGB, 4 RF)

- **Change:** first models.
  - L2 logistic regression: per-date ranks or train-fold winsorising; C from 1e-4 to 1; with and without class weighting.
  - HistGradientBoosting: two shallow shapes; per-date ranks or raw values; early stopping on a purged, later holdout.
  - Random forest: depth 6 or 10; min leaf 2000 or 500; 300 trees with `max_samples=0.2`.
  - An RF on every date (stride 1) as an overlap experiment.
- **Why it mattered:** this is the first evidence of whether a model adds anything to the reversal baseline inside train.
- **Metric movement (mean over 6 folds; reversal ≈ 0.5065 on the same rows):**
  - Best balanced accuracy: `rf_d10_l500_bal_stride1` 0.5094 (+0.0029 vs reversal, better in 5/6 folds), `hgb_raw_wide_bal` 0.5093, `hgb_raw_small_bal` 0.5092.
  - Best LR: `lr_rank_c1e-02_bal`, 0.5083 (+0.0018, 3/6 folds).
  - Per-date AUC: 0.511–0.515. Rank IC: +0.021 to +0.028. HGB on raw values ranks best.
- **Unexpected:**
  - **The gates conflict at this signal strength.**
    - Class-weighted models make balanced calls (42–49% "beat") and beat reversal. Their accuracy (0.5085–0.5112) is at or below majority accuracy (0.5112), and their Brier is worse than the constant.
    - Unweighted models are better calibrated, but they call "beat" for only 15–27% of rows and lose to reversal on balanced accuracy.
    - No config passes all three gate proxies in more than 3 of 6 folds.
  - **Overlap did not hurt the RF.**
    - Stride 1 had a slightly smaller fit-minus-eval gap than stride 5 (+0.0247 vs +0.0254) and better fold metrics.
    - `min_samples_leaf=500` with `max_samples=0.2` was enough regularisation. The expected near-duplicate overfit did not appear at this depth.
  - **Fit-minus-eval gaps (in-sample balanced accuracy on fit rows minus fold balanced accuracy):** LR +0.006 to +0.017, HGB +0.015 to +0.035, RF +0.008 to +0.025.
- **Decision:** diagnose the Brier gap before choosing finalists.
- **Lesson:** a 0.5 threshold, calibrated probabilities and balanced accuracy pull in different directions when the beat-rate is 0.487 and AUC is about 0.513.

## Iteration 2: diagnosis of the Brier gap (train only, no new model)

- **Measured** (`model_selection.json` out-of-fold predictions; script not kept):
  - The beat-rate varies by date: SD 0.047 across train dates.
  - Knowing each date's beat-rate would lower Brier from 0.24983 to 0.24771 (−0.00212).
  - The stock-level signal lowers Brier *within* a date by at most about 0.00005.
  - `lr_rank_c1e-02_bal`:
    - Date-mean error 0.00173.
    - Within-date error 0.24838, compared with 0.24825 for the labels alone: the model is over-confident within a date.
    - Shrinking it halfway towards 0.5 gives Brier 0.24988, which is still not below the constant on all rows.
  - Predicting 0.5 everywhere scores 0.25000, so centring calls at 0.5 costs about 0.00017 against the 0.487 constant. That is more than the stock-level signal can repay.
- **Cause:** per-date ranks remove all date-level information by construction, so the Brier gate is decided almost entirely by how well a model tracks the date-level beat-rate. HGB on raw values sees some date-level information (raw volatility and return levels), which explains why it calibrates better.
- **Next:** test whether the excluded market-state features (`mkt_ret_21d`, `mkt_vol_21d`, `xs_dispersion_21d`) predict the date-level beat-rate.

## Iteration 3: market-state experiment (6 configs)

- **Change:**
  - The three market features were added (opt-in `market=True`).
  - They are winsorised and standardised on the fit fold, never ranked.
  - Two LR settings and the small rank-HGB, with and without class weighting.
  - ADR-0006 excludes these features by default, so this is a separate, recorded experiment.
- **Metric movement:**
  - LR: no change (`lr_rank_c1e-02_bal` Brier 0.25010 → 0.25012 with market features).
  - HGB: a small gain (`hgb_rank_small_bal` Brier 0.24996 → 0.24990), and it beat reversal in 6/6 folds.
- **Decision:** the hypothesis is mostly falsified. Three linear market terms do not recover the date-level beat-rate. No market config is eligible, and the default stays without market features.
- **Possible follow-up:** a feature aimed directly at the date-level beat-rate, e.g. the cross-sectional skew of trailing returns. It needs the feature registry and the leakage tests.

## Iteration 4: calibration and averaging (candidates)

- **Change:**
  - Nested Platt scaling: fold k is calibrated on out-of-fold predictions from folds < k, so fold 0 is not scored.
  - It was applied to the best LR, the best HGB and the best RF.
  - An average of the best LR and the best HGB.
- **Metric movement (folds 1–5):**
  - Platt scaling always fixes Brier (0.24975–0.24981 vs constant 0.24991). It costs balanced accuracy: LR 0.5038, HGB 0.5036, RF 0.5065.
  - For the RF, calibration keeps it ahead of reversal (+0.0012, 3/5 folds), because the RF probabilities are spread more widely.
  - The LR+HGB average has the highest balanced accuracy (0.5097, 6 folds). Its Brier equals the constant, and its accuracy is below majority.

## Finalist rule (decided on train folds, before any validation access)

- **First rule (planned):** the best config per family by mean fold balanced accuracy, with Brier as a guardrail.
- **Problem:** it would have picked the LR+HGB average and the uncalibrated stride-1 RF, and both fail the accuracy proxy on average.
- **Refined rule (`choose_finalists`; validation had not been touched when it was written):**
  - Eligible only if the mean-over-folds analogue of all three point gates holds: beats reversal, accuracy ≥ majority, Brier < constant.
  - Ranked by the share of folds passing all three proxies, then by mean balanced accuracy.
  - One finalist per family, at most 3.
- **First result:** this rule first gave 2 finalists, `rf_d10_l500_bal_stride1+platt` and `hgb_raw_small_bal`. That was before the reviewer's fold-set fix below.

## Iteration 4b: `mle-reviewer` findings before validation, and fixes

The `ecc:mle-reviewer` agent reviewed the harness and the fold results before the validation access. Its verdict was APPROVE WITH WARNINGS: no leakage, no critical issue.

| # | Finding | Verified? | Action |
|---|---|---|---|
| H1 | Calibrated candidates were summarised on folds 1–5 and everything else on folds 0–5. The finalist set depended on that choice, and 3/5 was compared with 3/6. | Yes: on common folds the HGB finalist changes from `hgb_raw_small_bal` to `hgb_raw_wide_bal`. | Eligibility and ranking now use folds 1–5 for every candidate (`common_summary`). Folds 0–5 are kept as `summary_all_folds`. |
| H2 | `judge` trusted the stored `finalists`; a stale list could judge ineligible configs. | The stored list was stale while a rescore was running; the risk is real. | `judge` recomputes the finalists. Names outside them need `--reason`. |
| M1 | No cumulative cap; a candidate built on an already-judged model counted as new. | Yes | Distinct judged candidates are capped at 3 overall. Every member model's id is logged and checked. |
| M2 | The Platt map was read without an alignment check, and the refit model's score distribution may differ from the out-of-fold scores. | Yes | Uses `_load_oof`, which checks date and ticker. Records raw-score mean/SD of out-of-fold vs final predictions (label-free). |
| M3 | Eligibility margins are noise-sized. Date-block bootstrap SE of the Brier gap is about 6e-5: `hgb_raw_*` margins are about 0.3 SE, RF+Platt about 2.5 SE. | Accepted | Not turned into another rule, which would be one more post-hoc choice. Recorded here as a caveat. |
| M4 | One p at a 0.5 threshold serves three conflicting gates; a validation fail is likely. | Accepted | See "Expected outcome" below. No retuning after the judgment. |
| L1 | The HGB constant used a slightly different base rate (early-stopping rows excluded). | Yes, about 1e-5, which matters at these margins. | All families use the beat rate of every strided fit row (`fit_base_rate`). |
| L2 | The access was logged before work started, so a crash would still consume it. | Kept by design | The log now has "started" and "completed" entries; aborted runs still count. |
| L3 | The HGB early-stopping holdout (about 1 year) is never trained on. | Accepted | Consistent across folds and the final fit; noted. |
| L4 | The repeat-guard id does not include the seed or data version. | Partly | The seed and dataset SHA-256 are written into each log entry. |

Tests: 47 in `tests/test_modeling.py`. All 23 planted bugs were caught, each in a fresh process. Two mutants survived at first ("eligibility ignores accuracy", "member ids ignored in the repeat check"); their tests were strengthened. One more ("prices not cut at the split end") is invisible in the outputs and is caught by a spy test on the inputs.

## Finalists after the fixes (rescored on folds 1–5)

- **Configurations tried:** 34. That is 28 specs (22 grid + 6 market-state) plus 6 calibrated or averaged candidates. Two candidates were evaluated and then superseded when the best LR changed under the common folds; they still count.
- **Eligible:** `hgb_raw_wide_bal`, `hgb_raw_small_bal`, `lr_winsor_c1e-02_bal+hgb_raw_wide_bal`, `rf_d10_l500_bal_stride1+platt`, `hgb_raw_wide_nowt`, `rf_d6_l2000_nowt`.
- **Finalists (3):**

| Finalist | Folds passing all proxies | Bal. acc. | vs reversal | Accuracy − majority | Brier − constant |
|---|---|---|---|---|---|
| `hgb_raw_wide_bal` | 3/5 | 0.5092 | +0.0038 | +0.00043 | −0.000020 |
| `rf_d10_l500_bal_stride1+platt` | 3/5 | 0.5065 | +0.0012 | +0.00314 | −0.000158 |
| `lr_winsor_c1e-02_bal+hgb_raw_wide_bal` (average) | 2/5 | 0.5093 | +0.0039 | +0.00027 | −0.000024 |

- **LR:** the course's baseline model enters only through the averaged candidate. On its own, every LR fails the Brier proxy or loses to reversal.
- **Expected outcome, written before the judgment:**
  - All three finalists most likely fail.
  - The validation significance gate needs a block-bootstrap CI lower bound above 0. The fold edges over reversal (+0.001 to +0.004) are smaller than the half-width of reversal's own validation CI (about ±0.011).
  - The HGB finalists' Brier margins are noise-sized.
  - A fail will be reported as is. Nothing will be retuned on validation.

## Iteration 5: validation judgment (access #1, 2026-11-14)

- **Change:** `python -m stocksight_data.modeling judge` refit each finalist on all train rows (same stride) and scored validation through `gate_model` with the frozen gates.
- **Rows:** 363,472 validation rows, 100% of the frozen row set. 3 finalists, 34 configurations tried.

| Finalist | Bal. acc. | Accuracy | Brier | − reversal_5d (95% block CI) | 2019 / 2020 / 2021 bal. acc. | Gates passed |
|---|---|---|---|---|---|---|
| Gate threshold | > 0.50476 | ≥ 0.50790 | < 0.24996 | CI low > 0 | each ≥ 0.50 | all 5 |
| `lr_winsor_c1e-02_bal+hgb_raw_wide_bal` | 0.51027 | 0.51038 | 0.24978 | +0.0055 [−0.0036, +0.0145] | 0.5089 / 0.5230 / 0.5007 | 4/5 (fails significance) |
| `hgb_raw_wide_bal` | 0.50996 | 0.50982 | 0.24980 | +0.0052 [−0.0035, +0.0135] | 0.5102 / 0.5204 / 0.5006 | 4/5 (fails significance) |
| `rf_d10_l500_bal_stride1+platt` | 0.50849 | 0.51366 | 0.24975 | +0.0037 [−0.0047, +0.0117] | 0.5092 / 0.5156 / 0.5006 | 4/5 (fails significance) |

- **Secondary metrics (not gates):**
  - Per-date AUC: 0.5159, 0.5162 and 0.5143.
  - Per-date rank IC: +0.033, +0.032 and +0.029. That is higher than the fold means (+0.026 to +0.028), and 2020 is the strongest year.
  - Share of rows called "beat": 49%, 51% and 17% (the RF calls few).
- **Raw-score distribution, refit vs out-of-fold (label-free check):**
  - HGB: SD 0.0233 vs 0.0247. RF: 0.0155 vs 0.0183. Means within 0.003.
  - The refit models are slightly less spread, so the RF's Platt map, fitted on out-of-fold scores, is if anything conservative.
- **Slices (bal. acc.):**
  - By volatility tercile, every finalist is at or above 0.505 in every tercile.
  - By sector (today's GICS, a slice only): Energy is below 0.50 for the RF and the average (0.491). Real Estate is the best sector (0.516–0.527).
- **Decision: no model passes the frozen gates.**
  - Every finalist beats reversal_5d on the point estimate (+0.004 to +0.006), and accuracy, Brier and the yearly rule pass.
  - No 95% block-bootstrap CI excludes zero.
  - "No evidence of skill beyond the baselines" is the reportable result. Nothing was retuned after this run.
- **Tradeoffs accepted:**
  - The Brier gate passes partly by luck of drift. The validation beat-rate (0.4921) is closer to 0.5 than train's (0.4870), which favours the balanced models (mean p ≈ 0.50). The reviewer flagged this effect on the train folds before the run.
  - 2021 is at the margin for every model (0.5006–0.5007).
- **Lessons:**
  - With per-date AUC about 0.515, three validation years are too few to make a +0.005 balanced-accuracy edge significant. The CI half-width is about 0.009.
  - The point estimates agree with the fold estimates in sign and size, so selection did not obviously overfit the folds.
- **Not done:**
  - The test split was not touched (`--include-test` was never run).
  - No model artifact was saved.
  - The final HGB fits' iteration counts were not recorded. On the folds, early stopping ended at 30–107 iterations.
- **Next iteration (falsifiable):**
  - Option 1: a feature aimed at the date-level beat-rate (cross-sectional skew of trailing returns). It passes if fold Brier improves by more than 1 bootstrap SE (about 6e-5) without a loss on balanced accuracy.
  - Option 2: decide as a team whether the 0.5-threshold, single-p gate design is the right contract for the app (contract section 6). Changing the gates now would need a new, recorded freeze; it must not be fitted to this result.
