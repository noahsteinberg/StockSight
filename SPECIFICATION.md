# StockSight specification

## Goal and users

Build an educational full-stack stock analysis and prediction platform for students and people learning about financial data and machine learning. The team should be able to explain every part of the implementation and evaluate claims with evidence.

## Current deliverable

The current implementation provides PostgreSQL-backed historical search/charts,
repeatable snapshot import, and an Auth0/private-watchlist integration foundation.
Real hosted sign-in, persistent sessions, username signup with optional recovery
email and two-user private watchlists are locally verified. SMA20/Wilder RSI14
are implemented in the backend; indicator frontend integration is next when
assigned. The redesign is explicitly deferred. Inference, prediction history and
evaluation remain unimplemented. Read [the current handoff](docs/CURRENT_HANDOFF.md)
and [indicator contract](docs/INDICATORS.md) for the working boundary and evidence.

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

- Provider usage rights, reproducible cleaning, adjustments/calendar and incremental refresh
- Production password-reset acceptance and provider-driven session revocation (Auth0 and app sessions are implemented)
- Hosting choice and operational recovery (SQLAlchemy/Alembic schema is implemented through 0004)
- Exact prediction definition: close-to-close or another horizon, cutoff time, timezone, neutral/unchanged prices, and adjusted-price policy
- Baseline, model comparison metrics, probability calibration, and retraining cadence
- Prediction-history visibility and data retention
- Deployment services, budget, and demo acceptance criteria

Candidate models include Logistic Regression and Random Forest; neither is selected or implemented.
