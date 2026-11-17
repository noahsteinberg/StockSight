# ML product integration plan

Status: proposed for team review; ML integration not implemented

Date: 2026-11-16

## Purpose

This plan connects StockSight's offline ML research to an honest educational
application without choosing a product target before the evidence is ready.
The same application boundary can support:

- absolute next-session direction;
- relative outperformance over a fixed horizon;
- a continuous-return or ranking signal;
- a market component plus a stock-specific component; and
- risk and model-reliability context.

Latest `main` was reviewed at `ae3a80e` on 2026-11-16. It already contains the
UConn-styled React research workspace, PostgreSQL/Supabase-backed historical
analysis, SMA20/RSI14, Auth0-backed app sessions, private watchlists, and honest
Predictions/Model Performance unavailable pages. It has no ML inference,
persisted forecasts/outcomes, or automated market-data refresh. This document
lives on the isolated research branch and must be reconciled through a focused
branch from latest `main`; do not merge the research branch wholesale.

The existing application patterns are binding for integration: thin typed
FastAPI routes, repository-owned bounded reads, Alembic migrations, sanitized
errors, hash navigation, `authorizedFetch` for private calls, explicit
loading/error/unavailable states, request cancellation, and accessible mobile
behavior. Training remains outside the web runtime.

## Product principle

StockSight should answer:

> Given the information available at the stated cutoff, what does the selected
> model say about this stock over a stated horizon, how strong and risky is that
> signal, and how has this version performed on comparable unseen observations?

It should not promise an exact future price or present a model score as
certainty. "Signal strength" and "verified probability" are separate fields.
Probability remains absent until out-of-fold and protected-period evidence shows
that it is calibrated.

## Decisions intentionally deferred

The following remain open until the active research round and any recorded
target-comparison round are reviewed:

- primary target: absolute direction, relative performance, continuous return,
  or market-plus-stock decomposition;
- primary horizon: one session, five sessions, or another separately validated
  horizon;
- model family and parameterization;
- whether any prediction model has earned public serving;
- retraining frequency after the first artifact; and
- whether protected validation access is justified for a selected finalist.

Frontend implementation should not begin by hard-coding any of these choices.

## System boundary

```text
Market-data provider
        |
        v
Backend provider adapter --> cached daily bars / quotes
        |                         |
        |                         v
        |                 offline feature batch
        |                         |
        |                         v
        |                 trusted model artifact
        |                         |
        |                         v
        +----------------> stored predictions
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
             FastAPI endpoints          outcome resolver
                    |                           |
                    v                           v
              React interface          performance records
```

Training stays offline. An HTTP request must never rebuild features across the
universe, fit a model, access protected outcomes, or download a full dataset.

## Data and prediction cadence

### Prices and charts

Quotes and charts are observational data, not model output. The backend may
refresh and cache them more frequently than predictions if the selected
provider's license, delays, and rate limits permit. The UI must show the source,
timestamp, adjustment basis, and whether a value is delayed or provisional.

### Daily ML signals

The current feature pipelines use completed daily bars. Their predictions
therefore update once per completed NYSE session, not on every price tick.

Yahoo may revise the latest daily bar for hours after the close. Existing ML
code marks bars fetched less than 12 hours after close as provisional. A safe
initial schedule is:

1. after 06:30 America/New_York on an exchange session, fetch or refresh the
   preceding completed session;
2. validate the bar and mark it settled only if the provider data satisfies the
   existing cutoff and quality rules;
3. compute features for that `as_of_session`;
4. run inference with the approved artifact;
5. insert predictions atomically; and
6. resolve older predictions whose target session has completed.

An optional post-close preview would have to be labelled provisional and
replaced through an explicit versioned operation. The first MVP should avoid it.

### Retraining

Daily inference reuses a saved model and should be fast. Model training is a
separate, manual research and promotion process. Initially, do not retrain on a
timer. A later monthly or quarterly cadence requires drift monitoring,
reproducible snapshots, protected evaluation rules, and a rollback plan.

## Market-data provider boundary

The offline ML code currently obtains Yahoo Finance data through `yfinance`.
For an educational demo, the first backend adapter can reuse that source after
the team reviews provider terms, delays, rate limits, and attribution. It is not
a reason to couple application code directly to `yfinance`.

Latest `main` documents a successful small Yahoo feasibility check but does not
implement recurring ingestion. Its hosted Supabase database contains only the
selected 506-bar historical AAPL fixture ending 2017-02-16; the larger local
snapshot is not automatically present in production. A public recommendation
service therefore requires a deliberate hosted dataset/refresh decision in
addition to model integration.

Define a backend-owned provider interface with operations such as:

```text
search_symbols(query, limit)
get_quote(symbol)
get_daily_bars(symbols, start, end)
```

Provider responsibilities:

- normalize display symbols and provider symbols such as `BRK.B` / `BRK-B`;
- expose source and fetch timestamps;
- distinguish raw, split-adjusted, and dividend-adjusted fields;
- retry bounded transient failures without hiding permanent failures;
- enforce request limits and cache policy; and
- return typed errors rather than provider exception text.

The browser calls StockSight's backend only. Provider credentials, libraries,
and rate-limit behavior never belong in frontend code.

## Trusted model artifact

Research output does not become a serving model merely because it has the best
point estimate. Promotion requires a recorded selection decision and the
project's leakage, baseline, stability, probability-quality, and protected-data
rules.

An exported artifact bundle should contain:

- immutable model file;
- model version and research Git commit;
- target kind, cutoff, price basis, and horizon;
- ordered feature schema and feature-code version;
- preprocessing parameters learned on training data only;
- training dates and dataset snapshot SHA-256;
- package versions and random seed policy;
- evaluation report and baseline comparison;
- approved availability rules; and
- hashes for every file in the bundle.

The backend loads only trusted, locally produced artifacts whose hashes and
schema match the manifest. It must not deserialize an uploaded or otherwise
untrusted pickle/joblib file.

## Prediction record

Keep the stored record general enough for the approved target while requiring
its meaning to be explicit.

| Field | Meaning |
| --- | --- |
| `prediction_id` | Stable identifier for the immutable published prediction. |
| `ticker` | Canonical StockSight symbol. |
| `created_at` | UTC timestamp when inference completed. |
| `as_of_session` | Completed NYSE session containing the newest input bar. |
| `target_session` | Session on which the defined outcome becomes observable. |
| `horizon_sessions` | Integer horizon; never inferred from text. |
| `target_kind` | For example `absolute_return`, `relative_return`, or a reviewed enum. |
| `direction` | Optional reviewed call such as `up/down` or `outperform/underperform`. |
| `raw_score` | Model-native continuous score for auditing. |
| `probability` | Nullable; populated only when verified as calibrated for this target. |
| `signal_strength` | Nullable display band or normalized value with a versioned definition. |
| `universe_percentile` | Nullable same-date rank among eligible predictions. |
| `market_component` | Nullable market-wide contribution from a reviewed two-component model. |
| `stock_component` | Nullable stock-specific contribution from a reviewed two-component model. |
| `risk_level` | Nullable versioned risk output with its basis recorded. |
| `model_version` | Exact artifact version. |
| `data_snapshot` | Exact input snapshot or batch identifier. |
| `status` | `available` or `unavailable`; never a fabricated fallback. |
| `unavailable_reason` | Typed reason when status is unavailable. |

Unavailability reasons should include insufficient history, missing input,
bad bar, unsettled source bar, stale batch, unsupported symbol, and artifact
schema mismatch.

Published prediction rows are immutable. A later corrected batch creates a new
version and retains the prior record for audit; it does not overwrite history.

## Candidate database entities

Latest `main` already uses PostgreSQL, SQLAlchemy and Alembic through migration
`0005_backend_only_access`. ML persistence should be added in a reviewed next
migration without replacing the existing stock/bar/account/watchlist schema.
New tables inherit the backend-only/RLS posture: no direct browser-role access.
The design needs these responsibilities:

1. **Stock**: canonical symbol, provider symbols, exchange, active support
   status, and display metadata.
2. **DailyBar**: stock, session, OHLCV, adjustment basis, provider, fetch time,
   settled/provisional status, and quality status. Unique on stock, session,
   interval, provider, and adjustment policy.
3. **ModelVersion**: artifact manifest, hashes, target, horizon, feature schema,
   research decision, lifecycle state, and evaluation summary.
4. **PredictionBatch**: batch identifier, as-of session, artifact, dataset
   version, start/end times, counts, and failure state.
5. **Prediction**: the immutable prediction record defined above. Unique on
   batch, stock, target kind, and horizon.
6. **PredictionOutcome**: realized target, resolution time, source data version,
   correctness where defined, and evaluation eligibility.
7. **JobRun**: provider refresh, inference, outcome-resolution, and monitoring
   attempts with sanitized errors.
8. **Existing user/watchlist records** remain unchanged. Prediction reads can
   initially be public research data; watchlist composition stays private and
   continues through the existing account/session boundary.

## Proposed API surface

These are contract candidates, not implemented endpoints.

```text
GET /api/stocks?query=AAPL&limit=10
GET /api/stocks/{ticker}
GET /api/stocks/{ticker}/quote
GET /api/stocks/{ticker}/bars?range=1y&interval=1d
GET /api/stocks/{ticker}/signals?horizon_sessions=1
GET /api/recommendations?horizon_sessions=1&limit=25
GET /api/models/current
GET /api/models/{model_version}/performance
GET /api/predictions/{prediction_id}
```

Accounts later add authorized watchlist routes. All list endpoints need bounded
limits, stable pagination, typed error envelopes, and explicit timestamps.

Example signal response:

```json
{
  "ticker": "AAPL",
  "as_of_session": "2026-11-16",
  "target_session": "2026-11-17",
  "horizon_sessions": 1,
  "target_kind": "absolute_return",
  "direction": "up",
  "signal_strength": 61,
  "probability": null,
  "universe_percentile": 78,
  "market_component": null,
  "stock_component": null,
  "risk_level": "moderate",
  "status": "available",
  "unavailable_reason": null,
  "model_version": "next-session-v1",
  "data_snapshot": "daily-2026-11-16-settled"
}
```

`probability: null` is correct until calibration is established. The interface
must not relabel `signal_strength: 61` as "61% confidence."

## UX structure

### Stock detail

The page should separate three evidence types visually:

1. **Observed:** quote, timestamped price/volume history, and indicators.
2. **Model signal:** target, horizon, as-of date, call or rank, signal strength,
   risk, availability, and model version.
3. **Measured reliability:** historical performance on unseen periods and the
   relevant score band, with baseline comparison.

The signal card changes labels based on `target_kind` rather than pretending
every model predicts price direction. It always includes a clear unavailable
state and an educational/not-financial-advice explanation.

Latest `main` already preserves selected-stock context into
`#/predictions?symbol=...` and renders an explicit unavailable panel. Replace
that panel only after the real response schema and fixture contract exist. A new
public prediction hook should mirror the cancellation, timeout, retry and
stale-response protections in the existing indicator hook.

### Recommendations

Recommendations are "stocks to investigate," not buy/sell orders. Eligibility
must be predeclared and versioned. A reasonable first rule is:

- latest settled prediction is available;
- model version is currently approved;
- required risk and reliability fields are present;
- no stale or bad input is involved; and
- ordering uses the reviewed universe percentile or model score.

Filters can later include horizon, direction, relative rank, risk band, and
watchlist membership. Do not tune filters retrospectively to create an
impressive hit rate.

### Watchlist

Each saved stock can show current observed price separately from the frozen
daily model signal, along with as-of/target sessions and whether the prior
prediction has resolved.

### Model performance

Show model version, target, horizon, data period, coverage, accuracy, balanced
accuracy, probability error where applicable, rank metrics where applicable,
baseline comparisons, chronological fold results, and known limitations.
Current-constituent survivorship and adjusted-price revisions must remain
visible.

## How research selects the product emphasis

| Research outcome | Product emphasis |
| --- | --- |
| Stable absolute direction and probability quality | Up/down outlook with verified probability or reliability band. |
| Stable ranking/IC but weak absolute direction | Relative opportunity ranking and outperform/underperform language. |
| Stable market-plus-stock decomposition | Separate market outlook and stock-specific tilt, plus a combined signal. |
| Stable risk but weak return prediction | Risk monitoring, watchlists, and educational analysis without directional recommendations. |
| No stable signal beyond baselines | Prediction unavailable or explicitly experimental; do not publish a recommendation service. |

One continuous model may power several UI values: its sign gives direction,
its same-date percentile gives rank, and predeclared bands give signal strength.
Risk can initially be a transparent realized-volatility measure rather than a
second learned model. This keeps the MVP understandable.

## Promotion and release stages

1. **Research:** chronological folds and baselines; no serving artifact.
2. **Candidate selection:** one recorded candidate/target decision with trial
   count and justification.
3. **Protected evaluation:** validation access only under the recorded protocol;
   final test remains reserved until the final reporting decision.
4. **Artifact export:** create and independently verify the bundle manifest and
   inference parity against saved research predictions.
5. **Shadow batch:** generate predictions without displaying them; verify
   freshness, availability, persistence, and outcome matching.
6. **Limited UI:** display the signal with model/version/performance context and
   explicit unavailable states.
7. **Monitoring:** compare resolved predictions with the frozen baseline and
   suspend the model on data/schema failure or material drift.

No stage is skipped because the model looks promising on one fold.

## Implementation sequence

### A. Team contract

- Review the completed ML round and decide the next bounded research target.
- Approve target semantics, horizon, cutoff, price basis, and language.
- Approve provider and data licensing/caching assumptions.
- Freeze the initial API schemas before UI integration.

### B. Market data and persistence

- Preserve the existing PostgreSQL/SQLAlchemy/Alembic foundation and migrations.
- Decide whether the first deployed ML demo uses the historical hosted fixture,
  a deliberately imported larger snapshot, or a reviewed incremental refresh.
- Add the ML tables through the next Alembic migration with backend-only access.
- Implement provider refresh separately; do not put provider calls in chart or
  prediction HTTP requests.

### C. Model-serving boundary

- Export one approved artifact and manifest from the ML environment.
- Implement a separate batch inference command, not an HTTP training route.
- Verify feature parity and artifact hashes.
- Persist unavailable results and reasons as deliberately as successful output.

### D. Prediction and evaluation API

- Add signal, recommendation, model-performance, and prediction-detail schemas.
- Implement idempotent batch writes and outcome resolution.
- Recompute public metrics only from resolved, eligible predictions.
- Preserve baseline performance on exactly the same observations.
- Prefer scheduled immutable batches plus `GET` reads. Do not reuse the roadmap's
  old user-click "Generate prediction" concept unless historical replay is
  separately named, bounded and approved.

### E. Frontend

- Preserve the implemented stock search, chart, indicator, watchlist, navigation
  and selected-symbol flows.
- Populate the existing Predictions and Model Performance pages only after the
  API contract is real; retain unavailable/stale/error states.
- Add recommendations only after eligibility rules are approved.
- Add prediction history and model-performance context.
- Later add prediction summaries to existing watchlist/dashboard cards without
  bypassing `authorizedFetch` or owner-keyed UI state.

### F. Operations

- Schedule data refresh, inference, outcome resolution, and monitoring jobs.
- Add readiness checks for database, provider cache, and current prediction
  batch separately from process health.
- Record sanitized job failures and alert on missing daily batches.
- Document rollback to a prior artifact or prediction-unavailable state.

## Minimum verification

- Provider contract tests with recorded fixtures; CI does not require live
  Yahoo access.
- Trading-calendar tests for weekends, holidays, and early closes.
- Bar uniqueness, adjustment-basis, provisional/settled, and stale-data tests.
- Point-in-time feature parity between research and inference.
- Golden prediction parity between exported artifact and research output.
- Idempotent rerun tests: a repeated batch never duplicates predictions.
- Artifact hash/schema mismatch forces unavailable status.
- Outcome resolver cannot use a bar after the defined target session.
- API input, pagination, typed error, and unavailable-state tests.
- Frontend loading, empty, stale, unavailable, and error-state tests.
- Accessibility checks for signal color, labels, and keyboard navigation.
- End-to-end test proving a stored prediction remains unchanged after its
  outcome is recorded.

## Immediate next checkpoint

The next-session market/model round completed with no qualifying candidate; see
`ml/docs/NEXT_SESSION_ROUND2_RESULTS.md`. The immediate research action is the
bounded target-comparison round, after which the team chooses one of three
actions:

1. advance a qualifying candidate for the separately controlled evaluation
   process;
2. continue relative/ranking research under a newly recorded hypothesis; or
3. stop directional work and emphasize risk/educational analysis.

Only after that decision should implementation begin at section A.

Deployment of latest `main` can proceed independently with the ML pages still
unavailable. Deployment does not authorize a placeholder model or make the
historical hosted AAPL fixture a live feed.
