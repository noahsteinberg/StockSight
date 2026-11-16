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
- [x] SMA20 and Wilder RSI14 backend API, numerical/date/range/database tests
- [x] Current contracts and agent handoff

## Next proposed increment — indicator UI, when assigned

- [ ] Render API SMA20 overlay and RSI14 with functional toggles in existing UI
- [ ] Preserve null warm-up, units, provenance, dates and bounded-history meaning
- [ ] Handle independent indicator loading/error/retry and stale request cancellation
- [ ] Add real-API browser acceptance for toggles, ranges and date alignment
- [ ] Recheck chart/watchlist/session flows, mobile layout and keyboard access

Frontend redesign is explicitly deferred to a separate later phase. Do not bundle
it into the indicator increment. M3 is incomplete until indicator UI acceptance passes.

## Data and account follow-up

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

The latest backend run passed 95 tests with one expected SQLite-only skip;
PostgreSQL counterpart passed. Earlier browser/session evidence is dated in the
handoff. No new test run or publication is implied by this documentation update.
