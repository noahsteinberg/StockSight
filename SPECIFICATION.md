# StockSight specification

## Goal and users

Build an educational full-stack stock analysis and prediction platform for students and people learning about financial data and machine learning. The team should be able to explain every part of the implementation and evaluate claims with evidence.

## Current deliverable

Phase 0 provides an honest informational React landing page, a database-free FastAPI health endpoint, development tooling, CI configuration, and team documentation. It does not provide investment functionality.

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

Phase 0 excludes authentication, stock provider requests, database connections, indicators, watchlists, model training/inference, and a dashboard. The MVP excludes brokerage execution, paper trading, news/sentiment, high-frequency trading, and guaranteed-return recommendations. Redis, Celery, Kubernetes, GraphQL, and microservices have no current justification.

## Unresolved decisions

- Market-data provider, license, rate limits, coverage, and caching policy
- Authentication mechanism and account recovery approach
- Schema, migration plan, and hosting choice
- Exact prediction definition: close-to-close or another horizon, cutoff time, timezone, neutral/unchanged prices, and adjusted-price policy
- Baseline, model comparison metrics, probability calibration, and retraining cadence
- Prediction-history visibility and data retention
- Deployment services, budget, and demo acceptance criteria

Candidate models include Logistic Regression and Random Forest; neither is selected or implemented.
