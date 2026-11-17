# Next-session continuous-target comparison

Prepared November 17, 2026. Research branch: `research/next-session-targets`.
This is a bounded target-discovery experiment, not model promotion or integration.
Latest application architecture was reviewed separately on main at `ae3a80e`.
The application files in this isolated research branch are older; do not merge
this branch wholesale into main.

## Hypothesis and sources

The completed binary market/model round found no qualifying candidate. Test
whether preserving return magnitude or separating the market from stock-specific
returns produces more stable direction or ranking evidence. Keep HGB fixed;
LightGBM and further feature/model searches are deferred.

The [open-source audit](OPEN_SOURCE_MODEL_AUDIT.md) supplies the motivation:

- [Microsoft Qlib](https://github.com/microsoft/qlib) motivates continuous-return
  targets, chronological experiments and cross-sectional signal evaluation.
- [MASTER](https://github.com/SJTU-DMTai/MASTER) motivates treating market context
  explicitly. Our simple additive Ridge/HGB decomposition is a StockSight-native
  hypothesis, not an implementation or reproduction of MASTER's transformer.

No external code, pretrained weights, dependencies or datasets were copied.
Qlib's label timing and market differ; its results are not StockSight benchmarks.

## Frozen experiment

Three outputs, two HGB regressors and one Ridge fit per fold:

1. `absolute_return_hgb`: predict stock next-session adjusted return.
2. `excess_return_hgb`: predict stock return minus same-date equal-weight return.
3. `combined_market_stock`: add the Ridge market forecast to the excess forecast.

Use the existing 54 stock features and seven audited trailing market features.
HGB squared-error settings mirror the reference classifier: learning rate 0.05,
200 iterations, 15 leaves, minimum leaf size 100, L2 1, no early stopping, seed 0.
Ridge alpha is 1; fit-only median imputation and standardization precede it.
Ridge gets exactly one training row per observation date, not one per stock.

Reuse the frozen cleaned snapshot and archived `next-session/frame.parquet`.
That frame retains continuous returns and the exact original eligibility rules,
including exclusion of unchanged/invalid next-session outcomes. The equal-weight
benchmark uses this fixed eligible universe, at least 150 stocks, grouped by both
observation and target date. It is not the S&P 500 index return. Current-constituent
survivorship and outcome-availability selection remain limitations.

Six identical purged expanding chronological folds cover 2007-2018. Every target
ends by 2018-12-31. Reserve the last 252 training observation sessions for
calibration and purge fit targets crossing its start. Calibration targets also
precede outer evaluation dates. Context is computed from past-only feature rows
before joining future targets. No download, rebuild, validation or final-test
scoring occurs.

Clip each training target at its own fit-row 0.5/99.5 percentiles, including the
date-level Ridge target. Calibration/evaluation outcomes remain unclipped.
Stock feature values are float32, with missing values retained for HGB as in
the reference. No ticker-identity feature or new feature family is added.

Each output gets a diagnostic probability mapping learned only on calibration:
score StandardScaler then logistic regression, C=1, seed 0. Absolute and combined
probabilities estimate up; excess probabilities estimate outperform. Raw score
sign determines the direction call. A calibrated mapping may have a different
decision boundary and must not silently replace that call. These probabilities
are research diagnostics, not deployable confidence claims.

## Reports and review rules

Report accuracy, balanced accuracy, raw-score AUC, diagnostic calibrated Brier,
coverage, positive-call share, each fold, mean daily Spearman rank IC, and the
mean daily realized-return spread between highest and lowest predicted deciles.
Spearman IC is already a rank statistic; no duplicate "rank IC" is advertised
as independent evidence. Deciles use floor(n/10) stocks with deterministic ticker
tie breaks. Constant-score dates contribute no rank evidence. Spreads are gross
descriptive diagnostics, with no execution/cost claim.

Adding a shared market forecast cannot change the within-date ordering of excess
scores. Excess and combined rank metrics are therefore identical by construction,
not independent confirmations of ranking evidence.

All archived HGB comparison keys must match exactly, including target date and
label. Absolute/combined compare against original absolute reversal, always-up,
training-rate probability and HGB. Excess direction compares against relative
reversal, always-outperform and fit-relative rate; comparing its direction
accuracy directly to absolute HGB would answer different questions. Ranking
baselines include archived HGB and stock previous-return reversal.

Within-fold moving-date-block bootstrap: 5,000 draws, seed 0, 10 sessions primary,
5/21 sensitivity. Daily sufficient statistics preserve same-date stock dependence.
Intervals include paired direction differences vs baselines, probability error,
rank IC and decile spread. Bootstrap allocations are chunked to limit memory.

Predeclared review flags (never serving approval):

- Absolute direction: at least 0.5 percentage point balanced-accuracy gain over
  reversal; adjusted positive lower contrasts against reversal and reference;
  beat always-up accuracy and fit-rate Brier; beat reversal in at least 4/6 folds.
- Ranking hypothesis: positive IC in at least 4/6 folds including the last two;
  adjusted lower IC and spread bounds above zero at all three block lengths.
  Also inspect the reported HGB/reversal ranking baselines before deciding whether
  any further ranking research is justified. This flag alone does not establish
  incremental value over those baselines or authorize a recommendation UI.
- Adjusted lower bound uses the 0.025/6 quantile for this bounded round, not all
  prior research trials. Repeated reuse of the development folds still requires
  a separately recorded protected evaluation before any model selection claim.
- If neither direction nor ranking is stable, stop this return-prediction search
  and recommend descriptive risk/educational analysis. A predictive risk model
  would require its own research; historical volatility can be shown honestly.

## Run and resume

From this worktree in PowerShell:

```powershell
.\Run-Next-Session-Target-Round.ps1 -Stage Full
```

`Full` verifies/prepares inputs, resumes verified fold checkpoints, then creates
the final report. `-Stage Pilot` runs only fold 0 and writes a pilot report;
`-Stage Report` regenerates the full report without fitting. The Python defaults
to `$env:TEMP\stocksight-ml-round2-env\Scripts\python.exe`; an explicit
`-PythonPath` can select that same existing environment at another location.

Run one copy, keep the laptop awake, and leave this source/environment unchanged.
Each fold checkpoint contains all three outputs; JSON is committed last after
an atomic prediction-file replacement. Interrupted incomplete folds refit on
resume. Completed folds are hash-verified and skipped. Source, helper modules,
data, environment and protocol are frozen in `manifest.json`; a mismatch aborts.
No model artifacts are exported. Never remove a live `run.lock`; if a process is
forcibly killed, confirm its PID has exited before removing the stale lock.

All runtime files are under `data/next-session-target-round/`:

- `run.log`: console output and errors.
- `attempts.jsonl`: timestamped stage and HGB fit starts/completions/failures.
- `fold-0.json` through `fold-5.json`: six completed fold checkpoints.
- `pilot.md` / `pilot.json`: one-fold diagnostics only.
- `results.md` / `results.json`: full-run results to return for review.
- `manifest.json` / `prepared.json`: protocol, hashes and preparation audit.

Full reports are also copied to `ml/reports/next_session_target_round.json` and
`ml/docs/NEXT_SESSION_TARGET_ROUND_RESULTS.md`. Pilot never writes those final
paths. No result is a claim of live performance or current predictions.

## Integration boundary

Follow [the integration plan](../../docs/ML_PRODUCT_INTEGRATION_PLAN.md) against
latest main. Gavin's current React/FastAPI/Auth0/session/watchlist contracts and
Parth's backend-only Supabase access remain in place. A selected signal requires
artifact/feature parity, deliberate hosted data coverage/refresh, immutable daily
batches, outcomes, bounded GET APIs and then existing-page integration. Research
does not write Supabase, alter Vercel or change the unavailable frontend pages.

## Preparation and pilot evidence

- 36 focused tests passed, including calendar/fold regressions, target reconstruction,
  clipping boundaries, calibration isolation, checkpoint tamper detection, frozen
  protocol rejection, and synthetic pilot/full report generation. Four existing
  pandas timezone deprecation warnings remain in the earlier label tests.
- Managed Windows temp access required a worktree-local pytest base directory.
- Preparation verified 1,955,893 archived eligible rows across 4,777 dates, with at
  least 318 eligible stocks per date. Market/residual reconstruction error was
  at most 2.78e-17. All target dates end within the development period.
- Fold 0 trained on 542,673 rows / 1,504 fit dates, reserved 252 calibration
  sessions, and evaluated 202,903 rows. Fit targets ended 2005-12-28; calibration
  began 2005-12-29 and its targets ended 2006-12-29; evaluation began 2007-01-03.
- Final-source pilot HGB fits took 12.5 and 10.9 seconds; the fold including Ridge,
  calibration and checkpoint writing took 24.6 seconds. Pilot report completed.
- A synthetic constant-baseline test found an undefined-rank JSON edge case;
  it now records null rather than NaN. The initial pilot is preserved separately
  at `data/next-session-target-round-initial-pilot/`; source was frozen again and
  the same fold rerun without changing model parameters or scientific criteria.
- Pilot is engineering verification only. It does not select a target or imply
  later-fold performance. Five folds (ten HGB fits) remain for Noah's full run.
- Estimated remaining full-run time: 5-15 minutes, including verification,
  reporting and bootstrap uncertainty; laptop load can change this.

Verification command, from `ml/`, using the prepared ML Python environment:

```powershell
python -m pytest tests/test_next_session_target_round.py tests/test_next_session_round2.py tests/test_next_session.py tests/test_folds.py -q -p no:cacheprovider --basetemp '.pytest_cache\target-round-check-20261117d'
```

The `.pytest_cache` parent must exist; choose a fresh base-temp child on a rerun.
No full six-fold training batch has been launched by the agent.
