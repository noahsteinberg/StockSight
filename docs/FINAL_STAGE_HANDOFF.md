# StockSight final-stage plan

Updated November 27, 2026 (America/New_York). Coordinator: Noah.
Execution tracker: [issue #29](https://github.com/noahsteinberg/StockSight/issues/29).
This is the active forward plan; CURRENT_HANDOFF.md remains the delivery record.

## Decision and boundaries

Finish the existing discovery experience before adding another product area.
Explore already suggests stocks using observed momentum and variability;
Analysis explains prices, indicators and historical patterns; Compare and
watchlists support further investigation. This is a useful coherent product.
It does not establish that a suggested stock will outperform.

Do not expand into portfolio management, a financial suitability questionnaire,
intraday ingestion or a large model search to fill the Predictions page.
The original specification includes persisted forecasts and held-out evaluation.
An educational discovery app plus the offline research report is a smaller
deliverable: explicitly agree that scope with the professor if choosing it.
Do not silently mark the original predictive MVP complete.

Before code, contracts, schema, UX or training, the implementing agent must
present one bounded increment and obtain its supervising human's approval.
Ask concise multiple-choice questions about genuinely unresolved decisions,
such as whether the required deliverable includes a served model and which
horizon it predicts. Reuse prior approvals. Plan, implement, test and return
the result for review; merge/deployment require the applicable authorization.

## What exists and what does not

| Area | Verified implementation / release boundary | Remaining work |
| --- | --- | --- |
| Daily history | Existing Parquet history plus validated Yahoo completed-session updates in PostgreSQL; scheduled updater | Verify latest scheduled result/freshness and retain recovery procedures |
| Core app on main | Dashboard, 494-stock Explore, sectors, Compare, Analysis, private watchlists, Settings and preferences | Record real two-account hosted acceptance |
| PR #28 | Five-row Explore pages; six ranked research ideas per page, both metric methods, saved-sector mode; expandable Analysis patterns; search/navigation fixes | Human release approval, merge, production verification |
| CI for #28 | Six latest checks passed on fc508f0 before this documentation update | Check latest head again after publication; CI is not hosted account acceptance |
| Research | Frozen classifier/regression rounds plus the completed 21-session pattern diagnostic | No approved serving model; only a newly approved protocol can resume work |
| Predictions | Selected-stock unavailable status and future-history states | Approved artifact, inference, forecast/outcome persistence and real responses |
| Model performance | Unavailable state and evaluation destination | Exact model's held-out results, baseline, dates, counts and limitations |

PR #28 requires no migration, new provider key or environment variable.
Hosted schema is recorded at 0007_user_preferences. Recheck live revision
before any later migration; never rerun old setup because a page is empty.
Main does not contain #28 until it merges. This document does not perform it.

## 1. Release and accept the existing work

Suggested owners: Noah with Gavin for accounts/API and Parth for data.

1. Review #28, confirm latest-head checks and obtain Noah's release approval.
   Merge only the reviewed feature PR and verify its Vercel production build.
2. On production, search by ticker/company, filter sectors, sort, paginate both
   the stock list and ideas, switch both research methods and open candidates.
   Confirm date/source/revision wording and loading, empty and retry states.
3. Inspect AAPL and a non-AAPL chart, ranges, SMA/RSI, CSV, replay and Refresh.
   Inspect 5/21-session patterns and missing-history/event states. Confirm
   old horizon links open Analysis correctly and mismatches require refresh.
4. Add/remove up to four comparisons; verify common-date alignment. Check the
   search dropdown at phone width and by keyboard. Confirm unavailable model
   pages do not display historical outcomes as forecasts.
5. Use two authorized real accounts. Save/reload/remove a watchlist; save,
   reload and reset preferences; verify sector matching and default chart
   range. Log out, switch account and verify private data isolation. Record
   dated results, not credentials or identifiers, in CURRENT_HANDOFF.md.
6. Inspect the latest scheduled updater run and app readiness. A market holiday
   is not a missing update. An open page reads committed updates on refresh or
   its existing refetch paths; the database does not push data into the browser.
   Keep failure notifications and the documented retry/restore procedure.

## 2. Keep recommendations useful and preferences honest

Suggested owners: Vlad (@Londarh) and Noah; Gavin (@Hab1yer) for contracts.

The existing flow is Dashboard -> Explore -> Analysis -> Compare/watchlist.
Research ideas explain why a candidate appears, follow filters and link into
that flow. A rank is its position by the selected historical metric, not a
probability of profit. Historical patterns remain in Analysis, not a new page.
Predictions is reached for the selected stock's future approved signal;
Model performance explains the evidence behind that exact model.

| Saved setting | Current effect | Final-stage decision |
| --- | --- | --- |
| Sectors | Used when the user applies saved preferences to discovery/ideas | Keep; verify ownership, reset and no-match state |
| Default range | Initializes Analysis/Compare chart range | Keep; confirm explicit selections still work |
| Research purpose | Stored only; no current ranking/forecast effect | Retain clearly labeled future setting or separately approve a small visible use |
| Horizon preference | Stored only; does not choose or train a model | Do not imply a months/years forecast exists |
| Indicator defaults | Browser-saved SMA/RSI defaults | Preserve existing Settings behavior |

No additional profile fields are required to finish discovery. If the team
wants more personalization, first approve one demonstrable behavior with the
existing sectors, such as a clearer saved-sector entry point. Any new ranking
preference needs explicit semantics, reset behavior, API validation, owner
isolation and a reviewed migration if persisted. Do not collect risk/income/
holdings information without a product behavior that actually uses it.

## 3. Decide what ML must deliver before another run

Suggested owners: Noah and Vlad; Parth reviews data, Gavin reviews serving.

The latest pattern diagnostic has rank IC 0.02286 and gross decile spread
0.25494 percentage points, below the historical-median baseline's 0.29450.
Illustrative costs erase that spread. These are reused 2014-2018 development
dates, not held-out proof. They do not justify promoting pattern matching.
See the [report](../ml/docs/PATTERN_RANKING_DEVELOPMENT.md).

Choose and record one of these paths before fitting anything:

- **Discovery finish:** ship the useful descriptive tools and present the
  completed offline ML experiments, including negative results. Keep model
  unavailable and obtain agreement on the smaller course deliverable.
- **Predictive finish:** approve one bounded experiment and its stop rule,
  then build serving only for an output that meets the existing promotion
  requirements. If it fails, report failure and revisit scope rather than
  repeatedly changing the evaluation to obtain an attractive number.

Recommended research question for consideration: can a fixed 21-session
relative-return score rank eligible stocks better than simple baselines?
This is a proposal, not a trained model or a claim that longer horizons solve
predictability. It changes the original next-day direction target and needs
explicit target approval. A relative ranking is not an absolute up forecast.

If that question is approved, the next protocol must define:

1. Price adjustment, splits, missing sessions, calendar, dividends excluded or
   included, universe survivorship and the exact target. Existing current-
   constituent data cannot establish results for delisted stocks.
2. What information exists at publication time and the first executable entry
   price after it. A signal using a close cannot assume a trade at that close.
3. A fixed development budget: reuse existing past-only features first,
   compare a regularized linear baseline and one HGB candidate with a small
   predeclared configuration set. No large new feature/provider project.
4. Chronological folds by shared date across all stocks; fit preprocessing
   on training data only, purge labels crossing boundaries and account for
   overlapping horizons. Use identical eligible rows for all comparators.
5. Baselines including momentum and prior historical median; rank IC,
   coverage, per-block stability, concentration, turnover, feasible entry/cost
   assumptions and uncertainty. Direction accuracy alone is insufficient.
6. Existing promotion rules, compute/attempt limits and a written stop rule.
   Resolve data/timing blockers before fitting. Freeze the finalist before
   authorized 2019-2021 scoring; preserve earlier validation-access records.
   Final 2022 through November 12, 2026 remains reserved.

Scikit-learn's [time-series example](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html)
illustrates lagged features and why shuffled evaluation can look too optimistic.
Its example is not evidence of stock predictability. Our multi-stock panel also
needs date-grouped splits and label purging; a row-wise split is insufficient.

## 4. Wire an approved model through the existing architecture

This pipeline is **planned, not implemented**:

successful daily refresh -> validated latest features -> trusted approved
artifact -> persisted dated forecast -> existing API adapter -> Predictions;
later completed sessions -> realized outcome -> Model performance/history.

Build one vertical slice for one supported stock first, then the eligible
universe. Do not launch training from browser requests. Keep fitted feature
conventions identical offline and online; reject unsupported/insufficient data.

- Review the artifact registry, feature/data versions and trusted-load policy.
- Review an additive migration for forecast/outcome storage separately from
  #28. Store stable identifier, symbol, cutoff, generation timestamp, target
  session, horizon, artifact/feature/data versions and defined output semantics.
- Reconcile the proposed 21-session horizon with the existing signal contract;
  do not put a different horizon into a next-session field. Extend contracts
  and adapter together with meaningful unavailable/stale/failed states.
- Run idempotent inference after successful data refresh. Repeated runs must
  not duplicate forecasts; define how provider corrections affect provenance
  and preserve earlier published forecasts rather than silently rewriting them.
- Settle outcomes only when the target session's data exists. Never fill a
  future outcome or treat a historical analogue percentile as confidence.
- Predictions shows stored output, horizon, dates, model version, availability
  and history. Model performance shows the matching evaluated model's actual
  baseline, period, count, metrics and limitations, distinct from live outcomes.
- Test the full path, retry/failure, dates, numerical parity, stale artifacts,
  duplicate jobs, corrections, rollback and authorization where applicable.

Use the existing [ML integration plan](ML_PRODUCT_INTEGRATION_PLAN.md),
[frontend contract](FRONTEND_ML_INTEGRATION_SPEC.md), [API](API.md),
[architecture](ARCHITECTURE.md) and [accounts](ACCOUNTS.md). Reconcile old
proposed fields with code before implementing; those plans are not evidence
that forecast tables, approved artifacts or nightly inference already exist.

## 5. Completion and handoff

The project is ready to wrap up when the agreed scope is recorded, the release
is on main with green checks, public and two-account hosted acceptance is
recorded, and the team can demonstrate a five-to-seven-minute stock discovery
journey plus the actual ML evidence. Document remaining limitations and a
reproducible local fallback. For the full predictive MVP, forecasts, outcomes
and held-out baseline evaluation must work too; they cannot be waived silently.

Update CURRENT_HANDOFF.md, SPECIFICATION.md and issue #29 to the final state.
Close #29 only when its required gates are met or explicit scope reductions
are recorded. Closing #27 means its tasks moved here, not that they passed.

Procedures: [daily refresh](DAILY_REFRESH.md), [local startup](LOCAL_START.md),
[deployment](VERCEL.md), [ML research](../ml/README.md).
