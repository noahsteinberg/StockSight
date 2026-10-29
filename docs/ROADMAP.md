# Proposed StockSight team roadmap

Prepared October 29, 2026. Status: proposal for team agreement, not an approved schedule. Owners below follow the team proposal and may be reassigned by agreement. No GitHub issues are created by this document.

## 1. Outcome and current starting point

The goal is a working application the four team members can start, explain, and demonstrate to the professor. The final demonstration should connect real user actions to API requests, persisted data, and reproducible analysis. A model that fails to beat a simple baseline is an acceptable research result; broken integration or unsupported accuracy claims are not.

Today the repository contains an informational React/Vite page, a Python/FastAPI health endpoint, and lint/build/test configuration. The frontend redesign is local and not yet merged. Stock data, persistence, authentication, charts, indicators, predictions, and evaluation remain to be implemented. Do not confuse the removed repository's demo with current functionality.

Keep React, FastAPI, PostgreSQL, and a separate offline Python ML pipeline. Use one frontend, one API, and one database. Add infrastructure only for a demonstrated requirement.

## 2. Define the final demo before dividing tasks

The intended professor demo is a five-to-seven-minute scenario, adjusted to the actual presentation time:

1. Open the app and sign in with a prepared demo account. Show that private watchlists belong to the signed-in user.
2. Search one supported ticker and select a historical range. Display a price/volume chart, source, observation date, and freshness status.
3. Enable a technical indicator and briefly explain what it measures. Change the range without changing the meaning of the latest calculation.
4. Add the ticker to a watchlist, refresh the page, and show it is still present.
5. Open a recorded model prediction. Show its stock, information cutoff, target session, model version, and output. Distinguish an unresolved prediction from one whose outcome is known.
6. Show completed historical predictions and compare the model's held-out results to a baseline, including the evaluation period and sample count.
7. Demonstrate one graceful failure, such as an unsupported ticker, then explain the frontend/API/database/ML boundaries.

Use a prepared historical dataset so this scenario remains possible without a live provider connection. Label replay mode and its data date clearly. A forecast generated from a historical cutoff is a historical replay, never a live prediction. Keep a local runnable copy even if the primary demonstration is hosted.

## 3. Scope and boundaries

### Target release

- One exchange/calendar and a small agreed set of supported stocks; daily bars only.
- Historical price and volume chart with a few useful range options.
- Tested indicators, implemented one at a time: moving average first, then RSI, MACD, and Bollinger Bands as capacity permits.
- Accounts, sign-in/out, and one persistent watchlist per account.
- One precisely defined next-session direction target and one validated model exposed through the API.
- Stored predictions, eventual outcomes, and a baseline comparison on held-out data.
- Reproducible setup, a seeded demo, automated checks, and a rehearsed presentation.

### Defer until the target release passes

Intraday streaming, all-market search, multiple exchanges, news, sentiment, notifications, paper trading, brokerage integration, multiple watchlists, elaborate profiles, deep learning, automated retraining, and sophisticated cloud infrastructure.

### Scope ladder if time is short

A. Protect the integrated stock-search/chart flow, reproducible data, persistence, and a reliable launch procedure first.
B. Deliver one working indicator and a simple honest ML baseline before adding more indicators or model families.
C. Keep basic account/watchlist functionality; defer email verification, self-service recovery, and profile editing for a controlled classroom demo, subject to professor requirements. Do not expose public registration without an appropriate account lifecycle.
D. If model integration is not ready, demonstrate the offline experiment separately and explicitly mark the prediction UI unavailable. This is a reduced release and does not fulfill the complete proposed MVP; agree on the reduction with the professor rather than silently presenting it as complete.
E. Prefer a stable local demonstration over an unstable deployment. Hosting requirements must be confirmed early.

## 4. Team responsibilities and collaboration

| Person | Primary ownership | Secondary responsibility | Evidence to bring to milestone review |
| --- | --- | --- | --- |
| Noah | Frontend, charts, forms, loading/error states | User-flow integration and accessibility | Browser walkthrough against the actual API |
| Gavin | API contracts, validation, authentication integration, inference endpoint | Cross-layer integration and error handling | Contract tests and request/response examples |
| Parth | Data-provider adapter, data quality, features, model research | Indicator reference fixtures and model/data documentation | Reproducible data/model commands and held-out results |
| Vladislav | Schema, migrations, database tests, deployment/demo setup | Watchlist persistence and integration test environment | Fresh-database setup, restart persistence, and demo rehearsal |

Ownership means coordination and completion, not exclusive access to a layer. Every feature needs a primary owner and a reviewer. Pair Noah and Gavin on browser/API contracts; Gavin and Vladislav on auth/persistence; Parth and Gavin on features/inference; Parth and Vladislav on ingestion storage. Rotate reviews where practical so no critical component has only one person who understands it.

Hold two short integration checkpoints per week if the calendar permits. Bring working code or a reproducible failure, not only a status description. At each checkpoint: run the current complete flow, identify blockers, update ownership, and decide what can be merged. Integrate throughout each phase.

## 5. Milestones and completion gates

### M0 — Agree on scope and make the scaffold reproducible

Lead: Gavin. All four participate. Start immediately.

- Confirm final deadline, presentation length, grading requirements, required hosting, expected individual contributions, and available weekly hours.
- Agree on this roadmap, target scope, supported symbols, daily frequency, and the smallest professor-demo scenario.
- Review the frontend redesign under issue #1; keep its wording concise and future features honest.
- Each person installs the repository and runs frontend checks plus backend tests.
- Verify hosted CI on the current branch and choose a normal PR/review process.
- Record major decisions in short documents: data conventions, API conventions, authentication approach, and launch approach. Each decision has an owner and a due milestone.

Gate: all four can start the current app from documented commands, CI is green, and the team has assigned actual dates to M1–M6. No feature is marked done merely because one laptop runs it.

### M1 — Deliver one complete stock-search-to-chart flow

Lead: Noah and Gavin. Parth supplies a small deterministic dataset; Vladislav reviews launch/setup.

- Agree on a symbol-search and historical-bars response before implementing both ends.
- Add a fixture-backed data adapter to FastAPI. Use actual historical observations with documented provenance and permitted use; do not generate market-looking numbers to imply real performance.
- Noah builds ticker entry, range selection, chart rendering, and loading/empty/error states against the agreed response.
- Gavin adds validation, bounded queries, consistent errors, and routing between the development frontend and API.
- Parth verifies ordering, date coverage, null handling, and symbol normalization.
- Automate one browser happy path and an unsupported-symbol path; unit/contract tests cover response structure and invalid ranges.

Gate: a teammate can start both services, search a supported stock, change its range, and see API-provided bars. The app still demonstrates historical data when the internet is unavailable. No account or ML dependency blocks this milestone.

### M2 — Add reliable ingestion and persistence

Lead: Vladislav and Parth. Gavin integrates the repository/data layer; Noah adds freshness states.

- Choose a provider after evaluating access, cost, permitted caching/redistribution, coverage, rate limits, adjusted data, and failure behavior. Record the decision before investing in integration.
- Add PostgreSQL, SQLAlchemy models, and versioned Alembic migrations. Use a documented local setup, preferably a small Compose configuration if the team can run it.
- Persist stocks, daily bars, source, adjustment convention, and ingestion state. Define natural uniqueness keys before importing.
- Build a command that imports or refreshes supported symbols with bounded retries, per-symbol progress, and correction-aware upserts. A failed symbol must not falsely advance its coverage marker.
- Keep seed/fixture mode explicit. Store larger datasets outside Git; keep a tiny permitted deterministic fixture for automated checks, with a narrow ignore exception if needed.
- API reads persisted bars. Browser requests must not download an entire universe or train a model.
- Add useful indexes, isolated database tests, a liveness endpoint, and database readiness behavior.

Gate: a blank database can migrate and seed; repeated ingestion does not duplicate records; restarting preserves data; a simulated provider failure yields either clearly dated cached data or a controlled error. Missing credentials never expose secrets or crash the frontend.

### M3 — Add trustworthy technical analysis

Lead: Parth for numerical conventions; Gavin for API integration; Noah for visualization.

- Start with one moving average and test exact expected values, then implement additional agreed indicators.
- Specify lookback periods, EMA initialization, RSI flat-price behavior, standard-deviation convention, and missing-bar policy.
- Compute against sufficient prior data, then trim to the display window. Align every indicator value to its bar timestamp; represent insufficient history explicitly.
- Frontend toggles only implemented indicators. Use labels, units, source dates, and concise explanatory help when it helps interpretation.
- Test empty/short/constant/rising/falling series and known numerical fixtures. Verify the latest overlapping indicator is stable when changing display range under the documented history policy.

Gate: the integrated chart has at least one verified indicator, no invented Buy/Sell score, and clear handling of insufficient observations. Finish RSI/MACD/Bollinger only after the first indicator flow passes.

### M4 — Add accounts and persistent watchlists

Lead: Gavin and Vladislav. Noah builds the account/watchlist flow. Parth reviews behavior as a second user.

- Choose established authentication/session tooling. Do not write custom cryptography. Define session expiry, sign-out, password handling or identity-provider boundaries, and classroom-demo account recovery.
- Agree on watchlist ownership, duplicate-add behavior, and deletion behavior.
- Implement registration if included, login/logout, current-user lookup, and watchlist add/list/remove routes.
- Store identity references and owned entries with database constraints. Enforce ownership in API queries, not only by hiding buttons.
- For cookie sessions, implement appropriate cookie settings and CSRF defenses; for other approaches, document storage, expiry, and relevant protections. Add explicit origin configuration when needed.
- Seed two demo users through a safe local process; keep actual credentials out of Git and screenshots.

Gate: user A can add/remove a stock and retain it after refresh/restart. User B cannot read or mutate A's entries even by altering request IDs. Expired/invalid sessions fail safely; logout clears access. CI covers ownership failures.

### M5 — Build and integrate an honest ML experiment

Lead: Parth. Gavin owns inference integration; Vladislav owns records/outcomes; Noah owns prediction/history screens.

Research can start in parallel after M2's data conventions stabilize. Public inference waits for the research gate below.

Proposed target for team agreement: after a completed trading session t and provider finalization, predict whether the consistently adjusted close at the next exchange trading session exceeds the adjusted close at t. Specify the timezone, earliest availability time, zero-return policy, holidays, missing sessions, and horizon. If predictions are displayed before the cutoff, features must be changed accordingly; never use unavailable closing data.

- Create a versioned dataset/feature pipeline shared by training and inference. Begin with recent returns, one volatility measure, volume features, and available tested indicators.
- Use synchronized chronological splits across stocks. Fit preprocessing on training only, purge boundary samples whose label horizon crosses a split, tune on validation, and keep the final test period untouched until selection is fixed.
- Compare a training-derived majority baseline with Logistic Regression. Random Forest is optional. Set seeds, record dates/symbols/sample counts, and document limitations such as a fixed present-day stock universe.
- Report balanced accuracy, a confusion matrix, class balance, and an appropriate probability metric if probabilities are shown. Do not call raw model probabilities calibrated confidence without evaluating calibration.
- Save the model, preprocessing, ordered features, library versions, data/feature version, and artifact checksum together. Load only trusted artifacts.
- Add a bounded inference path using a ready artifact; never train during a browser request. Insufficient history or unavailable artifacts must produce an honest unavailable state.
- Persist each forecast with model version, symbol, feature cutoff, generation time, target session, output, and any displayed probability. Define a uniqueness rule so retries do not produce contradictory duplicates.
- Resolve outcomes idempotently after the target session data is final. Record resolution time and outcome source/version; preserve forecast inputs instead of overwriting forecasts during model refresh.
- Build history from stored records. For a new project, use separately labeled held-out historical replay records so the demo does not require waiting weeks for outcomes.

Research gate: one command reproduces a baseline and selected-model evaluation. Results are reported honestly even if the model is worse. Integration gate: API output agrees with the offline pipeline on the same fixture, forecast provenance is visible, pending outcomes remain pending, and historical replay is clearly distinguished from newly generated forecasts. Aggregate metrics use the same eligible sample set for model and baseline.

### M6 — Stabilize, deploy if required, and rehearse

Lead: Vladislav. Every owner verifies their part on the actual demo environment.

- Freeze new features. Run the complete flow from a fresh checkout and database on a second machine.
- Resolve integration bugs, verify mobile/desktop usability and keyboard access, and review logs for secret exposure.
- If hosted: configure HTTPS, secrets, API routing/origins, migrations, readiness, restarts, and artifact loading. Test the actual deployed URL, not just localhost.
- Preserve a known-good local release and dataset snapshot. Document launch, reset, seed, and recovery commands. Test reset only on an explicitly disposable demo database.
- Rehearse the exact presentation with prepared accounts and symbols, including refresh persistence, one failure case, and prediction evaluation.
- Prepare a short architecture slide, model evaluation evidence, limitations, and a backup recording/screenshots. The recording supplements the app; it does not replace verifying the app works.

Gate: another teammate can launch the demo using the runbook, and the team completes two timed rehearsals without ad hoc code edits. The release commit, data snapshot, and model artifact are identifiable and recoverable.

## 6. Contracts that prevent integration rework

These are proposed interfaces to agree on, not endpoints that exist today.

| Boundary | Proposed contract | Must settle before implementation |
| --- | --- | --- |
| Symbol lookup | GET /api/stocks?query=... | Supported universe, normalization, bounded results, unknown vs unsupported |
| Price history | GET /api/stocks/{symbol}/prices?range=... | Allowed ranges, chronological OHLCV bars, daily session date, source, adjustment policy, coverage and last observation |
| Indicators | GET /api/stocks/{symbol}/indicators?range=... | Timestamp alignment, null warm-up values, period defaults, price consistency |
| Identity | /api/auth/... and GET /api/me | Chosen auth mechanism determines exact routes and session handling |
| Watchlist | GET/POST /api/watchlist and DELETE /api/watchlist/{symbol} | Authenticated owner, uniqueness, repeat operation semantics |
| Forecast/history | /api/predictions | Generation vs retrieval semantics, model/cutoff/horizon, pending/complete/unavailable, historical replay |

Use ISO UTC instants for actual timestamps and explicit exchange session dates for daily bars. A session date is not automatically midnight UTC. Agree on a compact error shape such as code/message, distinguish invalid input, unsupported symbol, insufficient history, and unavailable dependencies, and keep raw exceptions out of responses. Cap all history/list requests. Export OpenAPI examples or shared fixtures so frontend development does not guess payloads.

Initial persistence entities: stocks, daily bars, ingestion runs/state, users or external identity references, watchlist entries, model versions, prediction records, resolved outcomes, and evaluation runs. Add entities when their milestone starts; avoid implementing the entire future schema in M1.

## 7. Schedule and parallel work

Let D be the confirmed demo deadline. Assign dates at M0 after estimating available team hours. These are planning proportions of remaining working time, not promised durations:

| Portion of remaining time | Main objective |
| --- | --- |
| First 10% | M0 decisions and reproducible setup |
| Next 20% | M1 integrated flow and M2 data/persistence |
| Next 25% | M3 analysis and M4 accounts/watchlists; Parth begins M5 research |
| Next 20% | M5 inference, records, outcomes, and evaluation UI |
| Final 25% | M6 stabilization, deployment, and rehearsal; no optional features |

Do not wait until the end to investigate deployment: Vladislav checks hosting/runtime requirements and runs a smoke deployment during M2 if hosting is required. Likewise, Parth defines the target during M0 and starts research once data is stable; ML must not be postponed until all UI work finishes.

Critical dependency chain: agreed data semantics → reliable historical data → features/chronological evaluation → versioned model → inference and recorded outcomes. In parallel: frontend/API integration → persistent stock analysis; and database identity design → auth/watchlist ownership. M6 depends on all release features passing their gates.

At the midpoint, cut optional indicators and extra model comparisons if M1/M2 are incomplete. At the start of the final quarter, lock the demonstrated scope and stop adding features. If fewer than several integration sessions remain, renegotiate the target release immediately rather than compressing away tests and rehearsal.

## 8. Turn the approved roadmap into GitHub issues

Create milestone tracking issues for M0–M6 after team agreement. Fully detail only M0/M1 and the immediate database/provider decisions; refine later tasks as earlier contracts settle. Reuse existing issue #1 for the frontend redesign.

Each implementation issue should contain: user-visible outcome, one primary owner, reviewer, dependencies, in/out of scope, payload/data examples where relevant, acceptance checks, and demo evidence. Prefer tasks that fit within one integration interval and can produce a focused PR. Split by working behavior instead of creating four giant frontend/backend/database/ML issues.

First issue candidates:

1. Agree on demo acceptance criteria, real dates, and supported data scope — all; Gavin coordinates.
2. Define symbol/history API examples and validation contract — Gavin; Noah reviews.
3. Prepare a small permitted historical fixture and provenance notes — Parth; Vladislav reviews.
4. Implement fixture-backed symbol/history routes with contract tests — Gavin; Parth reviews.
5. Build ticker/range/chart UI against actual routes — Noah; Gavin reviews.
6. Add an automated search-to-chart flow and setup runbook — Vladislav; Noah reviews.
7. Select provider and document data conventions — Parth; Gavin reviews.
8. Design initial bars schema and migration/import behavior — Vladislav; Parth reviews.

Do not mark a milestone complete until its integration gate passes, even if all individual PRs have merged.

## 9. Definition of done and professor-demo readiness

Every PR: focused scope, no secrets, concise user-facing copy, appropriate unit/contract/integration checks, relevant lint/build passing, docs matching behavior, and another teammate's review. CI should use fixtures/disposable services and never require personal provider credentials. A green build is not proof that cross-layer behavior works.

Before presentation, all four should be able to answer: where prices come from; what is persisted; how users are isolated; when a feature becomes available; what a prediction means; how leakage is prevented; which period was held out; how the baseline compares; and what fails gracefully without the internet.

Release checklist:

- [ ] Required scope and demonstration format confirmed with the professor.
- [ ] Clean installation, migration, seed, and launch verified on a second machine.
- [ ] Browser → API → stored data → chart works end to end.
- [ ] Watchlist survives refresh/restart; two-user isolation verified.
- [ ] Indicator numerical and date-alignment checks pass.
- [ ] Model and baseline evaluation is reproducible and labeled with its period/sample count.
- [ ] Forecast/history distinguishes pending outcomes and historical replay.
- [ ] Production or local demo configuration has no committed secrets.
- [ ] Main demonstration runs without depending on a fresh provider response.
- [ ] Timed rehearsal completed twice; each person has a speaking role and backup owner.
- [ ] Known-good release, dataset, artifact, runbook, and backup presentation are available.

The next action is a team review of this proposal: confirm dates and grading constraints, agree on the first milestone, and assign its small issues. The immediate engineering goal is M1: one complete, honest, repeatable stock-search-to-chart workflow.
