# Roadmap

The scaffold, historical chart/API slice, and PostgreSQL persistence foundation are implemented locally. This legacy phase list differs from the milestone numbering in [the team roadmap](docs/ROADMAP.md); use that roadmap and [database evidence](docs/DATABASE.md) for current gates and remaining provider work.

## Phase 0: Repository foundation

- [x] Initialize repository and configure origin
- [x] Build responsive informational React landing page
- [x] Add FastAPI health endpoint and contract test
- [x] Configure frontend lint/build, pytest, Ruff, and CI
- [x] Document scope, architecture, collaboration, security, database, and ML
- [x] Verify local install, lint, build, server startup, and health response

Team review, second-machine verification, and pending pushes remain explicit handoff steps.

## Phase 1: Full-stack/database foundation

- [x] Agree on initial history API conventions and add a real frontend/API integration
- [x] Design initial market-data schema and implement SQLAlchemy/Alembic
- [x] Add migrations, isolated database tests, and local configuration
- [ ] Select provider and implement reliable incremental ingestion for broader symbols

## Phase 2: Accounts and watchlists

- [x] Implement Auth0 SDK/token-validation foundation and private identity storage
- [x] Implement authorized persistent watchlist CRUD and UI
- [x] Test ownership boundaries, concurrency, persistence and error states
- [x] Configure Auth0 and verify real hosted sign-in and watchlist save/retrieval
- [ ] Finish real hosted logout/recovery, invalid/duplicate signup and second-user acceptance

## Phase 3: Stock data and analysis

- [ ] Select provider and document licensing, limits, and provenance
- [ ] Define symbol validation, timestamps, adjustments, and caching
- [ ] Add stock search, historical charts, and tested RSI/MACD/Bollinger calculations

## Phase 4: ML prediction pipeline

- [ ] Define horizon, target, market calendar, and information cutoff
- [ ] Create reproducible data/feature pipeline with chronological splits
- [ ] Compare a naive baseline, Logistic Regression, and Random Forest
- [ ] Record evaluation and model provenance; add versioned inference only after validation

## Phase 5: Prediction history/evaluation

- [ ] Persist predictions and match outcomes after the horizon expires
- [ ] Show history, baseline comparisons, and out-of-sample metrics
- [ ] Test timestamp alignment and model-version traceability

## Phase 6: Testing, deployment, and demo

- [ ] Add end-to-end coverage and accessibility checks for implemented features
- [ ] Prepare deployment, secrets, HTTPS, backup, and migration procedures
- [ ] Run security/data-quality review and rehearse a reproducible team demo
