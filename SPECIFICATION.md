# StockSight specification

## Goal and users

Build an educational full-stack stock analysis and prediction platform for students and people learning about financial data and machine learning. The team should be able to explain every part of the implementation and evaluate claims with evidence.

## Current deliverable

The current main app supports PostgreSQL-backed historical search and charts,
repeatable imports and scheduled completed-session updates, SMA20 and Wilder
RSI14, chart inspection and replay, Auth0 accounts, restored sessions, private
watchlists, Explore, Compare, Settings and private research preferences.
PR #28 adds descriptive research ideas and Analysis historical patterns; it
awaits release approval. Offline ML evaluation exists, but no serving model
qualifies. Inference, stored forecasts/outcomes and product model-performance
reporting remain planned. See the
[current handoff](docs/CURRENT_HANDOFF.md) for delivery and verification status.

The [final-stage plan](docs/FINAL_STAGE_HANDOFF.md) distinguishes the original
predictive MVP below from a smaller discovery-plus-offline-research deliverable.
The latter requires explicit scope agreement; passing app CI does not complete
the predictive requirements.

## Planned MVP

| Area | Intended behavior |
| --- | --- |
| Accounts and watchlists | Users can sign in and manage persistent lists they own. |
| Stock analysis | Search supported symbols; inspect historical price/volume charts and tested indicators. |
| Direction predictions | Estimate a precisely defined next-trading-day up/down target from information available at prediction time. |
| History and evaluation | Retain model version, prediction timestamp, horizon, and eventual outcome; report performance against baselines. |

## High-level requirements

- Clearly distinguish observed data, technical indicators, and model predictions.
- Validate API inputs; provide useful loading, empty, stale-data, and error states.
- Keep provider credentials and database access on the backend.
- Define timestamps, trading calendars, adjusted prices, indicator warm-up periods, and supported intervals before analysis implementation.
- Authorize ownership of private watchlists and prediction history when accounts exist.
- Use chronological train/validation/test splits and fit preprocessing only on training data.
- Record prediction provenance and evaluate unseen data against a simple baseline.
- Keep documentation, API contracts, automated checks, and accessible responsive UI aligned with actual functionality.
- Show an educational/not-financial-advice disclaimer and communicate uncertainty.

## Non-goals

The original Phase 0 was a scaffold; its exclusions are not the current implementation status. The MVP excludes brokerage execution, paper trading, news/sentiment, high-frequency trading, and guaranteed-return recommendations. Redis, Celery, Kubernetes, GraphQL, and microservices have no current justification.

## Unresolved decisions

- Provider usage rights and historical adjustment/universe limitations; existing
  cleaning/calendar and incremental refresh procedures are documented, not a new ingestion task
- Production password-reset acceptance and provider-driven session revocation (Auth0 and app sessions are implemented)
- Operational recovery and backup policy for the Vercel and Supabase deployment
- Exact prediction definition: close-to-close or another horizon, cutoff time, timezone, neutral/unchanged prices, and adjusted-price policy
- Baseline, model comparison metrics, probability calibration, and retraining cadence
- Prediction-history visibility and data retention
- Final demo scope and acceptance evidence; Vercel hosting and scheduled data
  refresh are implemented, with procedures in the current handoff

See [ML research](ml/README.md) for experiment results and promotion criteria.
