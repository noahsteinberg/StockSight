# Next-session direction: Noah's proposed research track

Prepared November 16, 2026 from Noah's meeting excerpt and explanation. This is a
planning checkpoint, not a trained model, approved new gate, or serving decision.
The pasted transcript skips approximately 1:00–9:38; no claim is made about the
missing discussion. Noah and Vlad agreed to investigate targets independently
and compare their findings. Team ownership in ROADMAP.md is unchanged.

Noah clarified the current scope: planning only, focused on what the existing
data can predict and which errors/limitations require changes. Do not implement
frontend changes, prediction APIs, model serving or integration in this phase.
The UI mapping below is context for a possible later decision, not authorized
implementation. Model execution is a subsequent research step; this document
does not claim new experiments have run.

## Immediate questions answered

- A new question does not require a new raw dataset. Existing daily adjusted
  prices can produce next-session up/down labels. New derived label/report files
  are needed; the source snapshot should remain unchanged.
- Preserve five-day results means retain the old experiments as evidence and
  avoid overwriting them. It does not mean continue optimizing the old target.
- The old saved predictions cannot be converted to next-day predictions. Refit
  models against the new labels; past-only feature values may be reusable.
- A different question is a separate experiment, not a way to reinterpret the
  old validation result as success. Compare against baselines appropriate to
  each question and keep unseen periods protected across both researchers.
- Start with the same data. Consider new inputs only after documenting a concrete
  failure or hypothesis; daily OHLCV may simply have weak next-day signal.

The first report should answer: does either model beat appropriate simple rules;
does it hold across chronological folds; are up and down errors asymmetric; are
probabilities reliable; do missing data/corporate actions explain errors; and
is an apparent stock-specific advantage stable in later development folds?
Predefined diagnostics explain failure; they do not justify unlimited tuning.

## Product question

After a completed trading session, estimate whether a supported stock's next
session adjusted close will be higher or lower. Users can search historical
charts, save stocks, inspect estimates and historical volatility, and review
resolved predictions against simple baselines. No future price curve is needed.

This is simpler to explain and settle than a long price path. It is not known to
be easier to predict accurately than the five-session relative target. A correct
direction also says nothing about return size or trading profitability.

Train on years of stock/date examples; predict one session ahead. Do not train
on one day alone. Start with a pooled model across the 494 supported stocks,
rather than 494 independently tuned models. The universe is today's constituents,
not a historically reconstructed S&P 500. Survivorship bias remains disclosed.

## Repository checkpoint

- App main fetched November 16: `efc6534`, including Gavin's merged
  `feature/auth0-watchlists` work. Analysis, indicators, dashboard, navigation and
  explicit unavailable prediction/performance pages exist.
- Remote ML branch remains `589d6c5`; its implementation is not merged into app
  main. The app's ml README does not represent the existing research branch.
- Noah's local `StockSight-ml-research`, branch `research/ml-round2`, contains the
  four-configuration follow-up, reproducibility report and confidence diagnostic.
  These changes were still uncommitted at this checkpoint. Preserve them before
  creating a separate implementation branch; do not merge app main blindly into
  that working directory or overwrite the old label configuration.
- No five-day model passed the existing validation gates. The confidence review
  did not justify promoting one. Neither conclusion is changed by proposing a
  different target. Old reports, acceptance gates and final-test reservation stay.

## Target contract to freeze before fitting

Proposed ID: `next_session_adjusted_direction_v1`.

1. Observation session t is complete, and all required daily bars have been
   ingested and validated before issuance. Record issuance timestamp and source
   freshness; no intraday prediction from today's final close.
2. Target is the next NYSE trading session, not the next calendar day. Features
   use information available through t only.
3. Return = adjusted_close[t+1] / adjusted_close[t] - 1. Positive = up, negative
   = down. Exactly zero = unchanged: exclude from binary fitting/scoring, report
   its count separately, and resolve live records as unchanged rather than hiding
   or calling them missing. Publish all issued predictions and their statuses.
4. Missing next-session rows, bad bars, invalid/nonpositive prices, and unresolved
   source data are unavailable/pending-data cases, never filled or bridged. Count
   every exclusion. A valid one-day outcome needs valid consecutive endpoints.
5. This predicts adjusted-price direction, not relative outperformance or raw
   displayed chart-close direction. Verify source adjustment conventions and show
   this distinction in the UI. Corporate-action dates need manual tracing.
6. Probability means P(up). A down call's estimated probability is 1-P(up).
   Use a fixed 0.5 call threshold for the initial comparison; display 0.5 as
   neutral if encountered. No tuned confidence filter in this first batch.

The existing historical adjusted dataset is suitable for an exploratory replay,
subject to its known limitations; it is not proof of point-in-time vendor values.
The app importer quarantines 252 source rows, while research has its own cleaning
rules. Audit the differences and adjustment semantics before serving predictions
from app data. Do not equate the app chart table with the research dataset.

## Data and evaluation

Reuse the hashed cleaned research snapshot, calendar, missing-data rules and
audited past-only features. No new paid data, news, intraday feed or deep-learning
stack is needed for this first experiment. A fresh feed is needed later to issue
and resolve genuinely current predictions; the snapshot ends November 12, 2026.

For initial development, use only 2000–2018. Keep outer evaluation fold dates
aligned with the existing walk-forward study, but build new one-session labels
and training-only baselines. All stocks on a session remain in the same split.
Fit preprocessing only on earlier training rows. Exclude any training label whose
target reaches the next partition; use a conservative one-session boundary gap.
Do not change the old five-session purge or global LABEL_HORIZON in place.

2019–2021 has already informed earlier work; a different target does not make it
pristine. No automatic access is authorized by this plan. Any later validation
access needs a selected candidate, fixed protocol and recorded reason. Leave
2022–November 12, 2026 reserved; do not plot or score its new labels during
development. Genuinely prospective predictions after a frozen release can supply
additional evidence once data refresh and issuance logging exist.

## First bounded batch: four configurations

Use the same frozen input set and observations across all four. Start with the
existing default 54 past-only features; they already contain absolute returns,
volatility and market-relative context. Audit feature safety for the new target.
Do not add a feature search at the same time as changing the outcome.

| Configuration | Purpose |
| --- | --- |
| Regularized logistic regression, unweighted | Simple probability baseline model |
| Same logistic regression + sigmoid calibration | Test probability reliability |
| Small histogram gradient boosting, unweighted | Test nonlinear relationships |
| Same gradient boosting + sigmoid calibration | Test probability reliability |

Reuse documented numerical settings where appropriate, but record exact
hyperparameters, seed, thread limit, package/source hashes and feature list in a
new manifest before fitting. Fit on every eligible training session: the old
five-day stride is not automatically appropriate for the one-day target. Do not
silently carry over class balancing: it can alter the interpretation of raw
probabilities. No grid search, per-ticker tuning or extra model families here.

Within each outer training fold reserve the final 252 sessions for calibration.
Keep those labels out of base-model fitting for both calibrated and uncalibrated
versions, so calibration is the only difference in each pair. HGB early stopping
gets a separate earlier chronological holdout within the base-fit partition.
Apply boundary purges at both internal cutoffs; never use outer evaluation labels
for stopping or calibration. Freeze these partitions in the manifest.

Compare on identical observations with always-up, training-majority,
training-up-rate probability, previous-session momentum and previous-session
reversal. Neutral baseline inputs need a fixed documented handling rule. Select
the strongest comparison baseline using only development history; report all.

Report ordinary and balanced accuracy, Brier, log loss, calibration bins, coverage,
class balance, counts, runtime and results by fold/year. Resample complete date
blocks across stocks; one-day labels remove five-day overlap, not shared market
shocks or time dependence. Fix a primary 10-session block bootstrap and label
5/21-session results as sensitivity checks. No stock-row independent intervals.

Before fitting, record a separate proposed acceptance contract for this target:
accuracy above majority, balanced accuracy above the strongest development-chosen
direction baseline with paired uncertainty excluding zero, and probability error
no worse than the training-rate reference. Specify minimum practical gain and
stability criteria before viewing new outcomes. These do not replace or relax the
five-day gates. With no ratified contract, results remain exploratory and no
candidate advances. Select at most one candidate after this batch, then stop.

## Stock-specific claims

Produce per-stock diagnostic tables with sample counts and uncertainty, but do
not advertise the retrospectively best stocks. To test specialization later,
choose stocks or groups using earlier development folds only, freeze the rule,
then evaluate on a later untouched period. Compare the model and baselines on
identical selected stocks/dates. Account for multiple comparisons. A ticker can
have high raw accuracy simply because it usually rose in that period.

No new stock-selection model or specialist model is included in the four runs.
Noah and Vlad should share manifests and compare identical targets on identical
samples where possible. Different targets need separate reports; a higher
accuracy on a different outcome is not a head-to-head win. Log all attempts and
coordinate holdout access so neither person's exploration becomes hidden tuning.

## Reruns and retraining

Rebuild one-session labels, label-dependent joins, sample eligibility, baseline
rates, split purges, model fits, calibration and evaluations. Old five-day saved
probabilities cannot answer this question. Reuse the frozen data and numerical
features after checking their hashes; do not rerun downloads or unrelated app tests.
Add focused tests for session/holiday targets, unchanged outcomes, bad/missing
bars, corporate-action examples, feature cutoffs, calibration partitions and
boundary purges. Run relevant regression checks once before handoff.

Provide prepare/run/report commands with cached folds and a clear failure log.
Measure a first-fold pilot and extrapolate before launching the bounded batch.
The prior 7-second diagnostic reused predictions; it does not estimate retraining
time. The assistant can run quick checks; longer runs can be launched by Noah
without an active chat and reviewed from compact reports.

At deployment, generating estimates from new bars is inference, not retraining.
First ship a fixed version. A later proposed monthly retraining schedule must be
backtested with only labels resolved before each refit, logged as a challenger,
and promoted explicitly. Do not refit after every wrong prediction or rewrite
historical predictions using the newest model. Daily refresh and monthly refitting
are separate tasks; automatic retraining is outside this first batch.

## App mapping after a model decision

| Existing view | Proposed addition |
| --- | --- |
| Analysis | Small next-session estimate card; retain historical chart and indicator plots |
| My dashboard | Watchlist columns for direction, P(up), historical volatility, as-of and availability; sort/filter independently |
| Predictions | Immutable issued estimates, target session, pending/resolved/unchanged/data-unavailable outcomes |
| Model performance | Resolved count, period, accuracy and balanced accuracy, baseline comparison, probability reliability and coverage |
| Methodology | Target/adjustment definition, data limitations, model/data versions, historical replay versus prospective results |

Keep three concepts separate: probability of direction, observed historical
volatility, and measured model performance. Initially show trailing 21-session
daily return standard deviation as historical volatility, not a trained risk
probability or probability of loss. Version any later low/medium/high boundaries
and fit them on development data only. Use text labels with arrows, not colors
alone. Avoid buy/sell labels or a single unexplained recommendation score.

Example layout only, with no fabricated numerical value: stock → target session
→ Up/Down estimate → estimated probability → historical volatility → as-of.
If model evidence is insufficient, retain an explicit unavailable or research
status rather than display a convincing-looking badge.

Persist stock, observation session, cutoff/issued timestamp, target session,
target definition/version, P(up), call, model version, dataset snapshot and
mode (historical replay/prospective). Deduplicate repeated requests for the same
model/stock/cutoff; a button must not manufacture a new independent forecast.
Resolve against the same adjusted target and retain source/outcome provenance.
Keep every original prediction immutable; corrections should be versioned.

Separate offline walk-forward results, retrospective replay and truly issued
prospective performance in the interface. Count only resolved binary cases in
binary accuracy, with pending/unchanged/unavailable counts alongside them and
baselines on identical rows. Do not show “we are X% accurate” without period,
sample count, model version and comparison. Inference/export, persistence/API
contracts and frontend wiring follow the research decision in separate work.

## Next implementation checkpoint

1. Preserve and commit the existing research work on its own branch.
2. Create a separate next-session research branch and target-specific outputs.
3. Freeze target, exact four configurations, partitions and acceptance proposal.
4. Implement/audit labels and tests, pilot one fold, run the bounded batch, report.
5. Review with Noah and Vlad before validation access or serving work.

No training, new label generation, database import, validation scoring or final
test scoring was performed while preparing this document.

## Technical references

- [scikit-learn time-series cross-validation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html): preserve temporal order. Stock-panel splits must be grouped by date rather than using its row gap naively.
- [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html): fit calibration separately from the classifier and inspect reliability; Brier alone does not isolate calibration quality.
