# Next-session direction research

Completed evidence and recommendation: [NEXT_SESSION_REVIEW.md](NEXT_SESSION_REVIEW.md).

This isolated track reuses the cleaned snapshot and default 54 audited features.
It never changes LABEL_HORIZON or the existing five-day gates/reports. Source
prices and features are filtered to December 31, 2018 before joining new labels.
No validation/test scoring, data downloads, serving artifacts or app changes.

## Frozen design

Predict next NYSE-session adjusted-close direction, after observation-session
data is complete. Zero return is unchanged, excluded from binary modeling but
counted in the audit. Invalid endpoints, bad bars and missing sessions are not
filled. Predict up for p>=0.5. Raw price charts and adjusted outcomes differ.
Survivorship and historical adjustment limitations remain.

Four configurations: logistic regression (C=1, max_iter=2000) and HGB (200
iterations, learning rate .05, 15 leaves, min leaf 100, L2=1, no early stopping),
each with/without sigmoid calibration. No class balancing. Two base fits per fold
are shared between calibrated/uncalibrated outputs, not four redundant fits.
LR uses existing training-fitted winsorization/scaling/missing indicators; HGB
retains NaNs. All eligible dates are used, seed 0, two numerical threads.

Six existing two-year outer blocks cover 2007–2018. The final 252 training
sessions are excluded from base fitting and used only for sigmoid calibration.
Base-fit target dates strictly precede calibration observation dates. Outer
training targets end before evaluation observation dates. No early stopping
holdout is needed because the final approved plan fixes 200 HGB iterations.

The report compares always-up, training-majority, training-rate probability,
one-session momentum and reversal on identical observations. A neutral previous
return receives the training-majority call. The reference up-rate uses only the
base-fit rows. Volatility thirds come from base-fit data; missing volatility is
its own group. Trend splits use distance from the 200-session moving average.
Per-ticker/group tables are descriptive, not stock-selection recommendations.

Primary uncertainty uses 5000 paired 10-session date-block draws within folds,
retaining all stocks on a sampled date. Fixed 5/21-session checks are sensitivity
analyses. The conservative promising screen corrects for four configurations
AND four direction baseline contrasts (16 comparisons), rather than pretending
the strongest observed baseline was fixed in advance. It also requires accuracy
above majority, Brier no worse than the constant rate, and improvement against
the pooled strongest baseline in at least four of six folds. At most one candidate
is ranked for later review by Brier, then balanced accuracy, then simplicity.
Passing is not promotion or authorization to access validation.

## Reproduce from repository root

Use the prepared pinned Python; no virtual-environment activation is required:

```powershell
$researchPython = "$env:TEMP\stocksight-ml-round2-env\Scripts\python.exe"
& $researchPython ml/scripts/next-session.py prepare
& $researchPython ml/scripts/next-session.py run --pilot
& $researchPython ml/scripts/next-session.py run
& $researchPython ml/scripts/next-session.py report
& $researchPython ml/scripts/check-next-session.py
```

Run one copy only. Source/data/environment hashes freeze at preparation. Completed
family/fold checkpoints resume only with matching hashes. Attempts include failures.
If a process is killed, confirm it has ended before removing its run.lock; never
erase the experiment directory or old reports to hide a retry. A changed design
needs separately versioned output, not a silently refreshed manifest.

Ignored data/next-session contains manifest, audit, labels/features frame,
12 checkpoint pairs (two families x six folds) and attempts. Each checkpoint
contains both raw and calibrated probabilities: four configurations x six folds.
The report writes tracked ml/reports/next_session.json and
ml/docs/NEXT_SESSION_RESULTS.md. No fitted estimator is exported.

## Tests and handoff

Focused tests cover holiday/tie labels, stock separation, missing/bad bars,
future mutation, strict calibration boundaries and neutral-baseline handling.
Preparation independently traces endpoint returns on real training examples,
including late-2018 boundaries. All access remains development-only.

Daily inference and daily price refresh are separate from retraining. No automatic
refit or recommendation score is implemented. Coordinate with Vlad before any
later holdout access; the old validation period is already examined, even for a
new target. Leave the 2022–2026 reserved test untouched.
