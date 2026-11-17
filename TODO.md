# Incremental work and MVP status

Updated November 16, 2026. Read [AGENTS.md](AGENTS.md) and
[the current handoff](docs/CURRENT_HANDOFF.md) first. This checklist describes current
implementation, not hosted release approval. The team milestone numbering and
unchanged ownership are in [ROADMAP.md](docs/ROADMAP.md).

## Working foundation

- [x] React/FastAPI repository, pinned dependencies, lint/build/test and CI definitions
- [x] Search, bounded historical price/volume chart, keyboard inspection and table
- [x] PostgreSQL schema/migrations, canonical series and controlled storage errors
- [x] Validated repeatable team Parquet import; imported snapshot locally verified
- [x] Auth0 signup/login/logout and private persistent watchlists
- [x] HttpOnly app sessions, refresh restoration, CSRF and account-switch isolation
- [x] Username signup with optional recovery email; real two-account isolation
- [x] Local React login/signup/recovery forms with Auth0, Google PKCE and unchanged app sessions (EMBEDDED_LOGIN.md)
- [x] SMA20 and Wilder RSI14 backend API, numerical/date/range/database tests
- [x] Current contracts and agent handoff

## Frontend redesign and indicator integration

- [x] Render API SMA20 overlay and RSI14 with functional toggles
- [x] Preserve null warm-up, units, provenance, dates and bounded-history meaning
- [x] Handle independent indicator loading/error/retry and stale request cancellation
- [x] Add real-API browser acceptance for toggles, ranges and date alignment
- [x] Recheck chart/watchlist/session flows, mobile layout and keyboard access
- [x] UConn-inspired responsive workspace and concise shared UI states

Gavin authorized this phase after the backend handoff. See
[FRONTEND_REDESIGN.md](docs/FRONTEND_REDESIGN.md) for reference research and evidence.

## Data and account follow-up

- [x] Prepare Supabase connection support, backend-only table access and setup guide
- [x] Investigate Yahoo Finance daily-data access and document the API/ingestion plan
- [x] Create/connect the actual Supabase project and verify migrated hosted schema
- [x] Load the user-selected historical AAPL demo and verify hosted data integrity
- [x] Configure the private backend connection and verify public HTTP APIs against Supabase

App-view increment implemented; see [APP_VIEWS.md](docs/APP_VIEWS.md):

- [x] Dashboard with real private watchlist filtering, saved dates, open/remove
- [x] Shareable page navigation with refresh, history and keyboard focus
- [x] Selected-stock Predictions view and Model performance view, honestly unavailable
- [x] Data/methodology page and dashboard/session browser acceptance

These views do not mark the ML/prediction items below complete.

- [ ] Confirm upstream download/cleaning, usage rights, price adjustments and calendar
- [ ] Enrich missing company/exchange metadata from a verified source
- [ ] Implement reliable incremental refresh with correction/failure policy
- [ ] Complete password-reset acceptance and provider-driven app-session revocation policy before public release

## Remaining full MVP

- [ ] Finalize target, information cutoff, calendar, unchanged-price and adjustment rules
- [ ] Version features with chronological train/validation/test splits and no leakage
- [ ] Evaluate majority baseline and Logistic Regression; Random Forest optional
- [ ] Record held-out results, model/data versions and trusted artifact checksum
- [ ] Add bounded inference with an honest artifact-unavailable response
- [ ] Persist stable forecasts with cutoff, target session, version and retry semantics
- [ ] Resolve outcomes idempotently; distinguish replay from newly generated forecasts
- [ ] Show prediction history and evaluation against the same-sample baseline
- [ ] Verify hosted CI on published head and setup on a second machine
- [ ] Decide hosting requirements, HTTPS/secrets/origins, migrations and backups
- [ ] Rehearse the complete professor demo and graceful failure path

The prior backend run passed 95 tests with one expected SQLite-only skip;
PostgreSQL counterpart passed. The redesign passed frontend lint/build, 19 chart/
indicator browser tests and nine account/session browser tests, plus normal-app
PostgreSQL browser checks. No publication is implied. ML remains for Vlad per
Gavin's current direction; roadmap ownership tables are preserved.
