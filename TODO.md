# Roadmap

Only Phase 0 is complete. Later phases describe work to scope and review, not functionality currently available.

## Phase 0: Repository foundation

- [x] Initialize repository and configure origin
- [x] Build responsive informational React landing page
- [x] Add FastAPI health endpoint and contract test
- [x] Configure frontend lint/build, pytest, Ruff, and CI
- [x] Document scope, architecture, collaboration, security, database, and ML
- [x] Verify local install, lint, build, server startup, and health response

Initial human review, commit, and first push remain owner actions; no commit or push is part of this scaffold task.

## Phase 1: Full-stack/database foundation

- [ ] Agree on API conventions and add a real frontend/API integration
- [ ] Design PostgreSQL schema and choose SQLAlchemy/Alembic setup
- [ ] Add migrations, isolated database tests, and local configuration

## Phase 2: Accounts and watchlists

- [ ] Choose and implement secure authentication and account lifecycle
- [ ] Implement authorized persistent watchlist CRUD and UI
- [ ] Test ownership boundaries and error states

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
