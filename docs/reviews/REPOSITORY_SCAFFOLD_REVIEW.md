# StockSight adversarial repository review

Reviewed October 27, 2026. Head: 89fa1c8fa57aacef60cfd30e506ca0147226ea83.

## Scope and recommendation

Repository-wide review of the current initial scaffold, as requested; not a PR review. This repository has one commit, so there is no parent/base revision for regression comparison. Production source was not changed. Installation and probes ran in the separate stocksight-review checkout.

Recommendation: suitable as a Phase 0 foundation, with qualified confidence. No confirmed blocking defects were found in the implemented API or build checks. This is not approval of an investment application or a production deployment. Rendered UI behavior and hosted CI were not verified.

The previous C++/TimescaleDB/CSV demo and its local backup were removed. Their architecture and findings do not describe this repository.

## Current reality

- React/Vite informational landing page with anchor navigation, responsive CSS, and coming-soon feature descriptions.
- Python FastAPI application factory with typed settings and a health route.
- Optional backend/.env configuration, local loopback binding, and explicit separation of secrets from frontend configuration.
- GitHub Actions frontend lint/build and backend Ruff/pytest jobs.
- No database, stock API, charts, accounts, watchlists, indicator calculations, prediction model, or frontend/API integration exists. This matches the documented Phase 0 scope and is not a defect.

## Evidence and adversarial checks

| Check | Observed result |
| --- | --- |
| Clean frontend lockfile install | npm ci succeeded; audit reported zero vulnerabilities at review time |
| Frontend lint | Passed |
| Production frontend build | Passed with Vite 8.3.5 |
| Isolated backend dependency install | Succeeded with bundled Python 3.12.14 |
| Backend lint and format | Ruff passed; six files already formatted |
| Existing API test | One test passed |
| Settings override | Health response used injected review-service name |
| Unsupported HTTP method | POST /api/health returned 405 |
| Nonexistent feature route | GET /api/stocks returned 404 |
| API documentation contract | GET /openapi.json returned 200 |

An initial test began before installation completed and failed to import FastAPI; it was rerun after installation. A restricted-environment API test stalled; the isolated test and probes passed outside those restrictions. These were review execution issues, not confirmed repository bugs.

## Confirmed findings

None requiring a defect report. The small existing implementation and explicit scope do not justify manufacturing findings about unimplemented functionality.

## Gaps and concerns, not confirmed defects

1. Coverage is narrow: backend/tests/test_health.py checks one success contract. There are no committed browser tests. The extra route/configuration probes passed but are not committed tests. Add coverage with each real feature.
2. Frontend and backend are intentionally disconnected: frontend/vite.config.js has no API proxy and backend has no CORS setup. Define same-origin proxying or explicit allowed origins before introducing fetch requests. Do not report this as a currently broken user flow, because the page makes no API calls.
3. Python direct dependencies are pinned but transitive dependencies are not locked. Successful installation today does not guarantee the same resolved environment later. Consider a full dependency lock with a documented update process.
4. frontend/src/styles.css loads Google Fonts over the network. Offline typography and layout behavior have not been checked; a system-font fallback is present.
5. Local test coverage used Python 3.12 on Windows, while CI declares Python 3.13 on Linux. Hosted CI status was not inspected.
6. An isolated headless rendered UI environment was not established. The skill's Luna max UI reviewer workflow was therefore not run; no live user browser was substituted. Mobile layout, keyboard navigation, contrast, font-loading failure, and browser console behavior remain unverified.
7. No dependency security audit of the Python environment was performed. npm audit's zero result is point-in-time evidence, not a security guarantee.

## Recommended next steps

### 1. Agree on the first useful demo

Build a public stock-analysis slice before accounts or ML: enter a supported ticker, choose a range, retrieve historical bars from FastAPI, and render a chart with source and last-updated information. Prefer a deterministic small fixture for local development, clearly labeled as historical. Do not restore fabricated signals or predictions.

Acceptance: a teammate can install both services, start them using documented commands, search a known ticker, and see an actual API response rendered. Unknown symbols, no records, invalid ranges, network errors, and stale data each have understandable outcomes.

### 2. Define the data contract and provider boundary

Choose provider, license, supported symbols, adjusted-price convention, exchange calendar, timezone, and update frequency. Define prices endpoint schemas, bounded range/limit validation, error responses, and freshness metadata. Put provider access behind a backend adapter so local fixtures and provider responses share the same contract.

Acceptance: contract tests cover valid and invalid requests, ordered timestamps, duplicate handling, missing sessions, and provider failure. Frontend requests work through a documented routing arrangement.

### 3. Introduce persistence when the data flow is stable

Use PostgreSQL with SQLAlchemy/Alembic migrations, a symbol/time uniqueness rule, useful indexes, and idempotent imports. Add a reproducible local database and isolated database tests. Keep training outside HTTP handlers.

Acceptance: a fresh database migrates successfully; rerunning ingestion introduces no duplicates; partial failures can resume; an existing environment can upgrade without losing records.

### 4. Add tested indicators and browser coverage

Implement RSI, MACD, and Bollinger Bands using agreed numerical conventions. Fetch preceding history before trimming display ranges. Add numeric fixtures for flat/rising/falling/short series. Verify the rendered search-to-chart flow, mobile layout, keyboard access, loading states, and failure states.

Acceptance: known numerical outputs match within documented tolerances, and the latest displayed indicator refers to the latest displayed price bar.

### 5. Add accounts and owned watchlists

Choose maintained authentication/session tooling and define account recovery, session expiration, and authorization before adding private records. Test that one user cannot read or modify another user's watchlist.

Acceptance: persistent CRUD survives refresh, unauthorized requests fail, and ownership tests run in CI.

### 6. Start ML as a separate experiment

Resolve prediction horizon, information cutoff, unchanged-price policy, and baseline first. Use chronological splits, training-only preprocessing, versioned datasets/models, and an untouched test period. Compare simple baselines before exposing inference. Store predictions and evaluate outcomes only after their horizon expires.

Acceptance: the team can reproduce a baseline evaluation and trace every feature to information available at prediction time. No UI claims precede measured results.

## Immediate implementation order

First PR: frontend/API integration plus one fixture-backed historical-prices flow and tests.
Second PR: provider adapter and data provenance/freshness behavior.
Third PR: persistence and migrations.
Then indicators, accounts/watchlists, and finally evaluated ML.

Keep the existing React/FastAPI architecture. A rewrite or distributed-services setup has no demonstrated benefit at this stage.
