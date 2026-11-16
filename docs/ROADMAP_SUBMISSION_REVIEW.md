# Adversarial review of roadmap against submitted proposal

Historical requirements review, retained with its original scope and verdict.
Current implementation and phased continuation are in
[CURRENT_HANDOFF.md](CURRENT_HANDOFF.md); full MVP gates remain in ROADMAP.md.

Reviewed November 15, 2026.

## Verdict

Revise before treating the roadmap as the team's final delivery agreement. It broadly implements the submitted proposal, but several milestone gates could pass without delivering user actions promised to the professor. The most direct scope conflict is optional registration despite an explicit account-creation promise. Missing calendar commitments also prevent a defensible feasibility assessment.

This is a document/requirements review, not a code review or merge approval. No application tests were run for this comparison. No submitted document, production code, or roadmap was modified, and this report has not been published to GitHub.

## Reviewed sources and limits

- Submitted proposal: the user-supplied `TeamProjectProposal (2).docx`, read directly from its Word document XML. Relevant locations below use its numbered sections and feature subheadings, not unverified page numbers.
- Implementation roadmap: `docs/ROADMAP.md` at commit `1b11cf82244f5dc48452cdd1bd596c5b7036d916`. References use one-based lines in that revision.
- The SharePoint link required authentication. The uploaded file is treated as the submitted version at the user's direction; its equality with the current SharePoint version and the professor's receipt cannot be independently established.
- No grading rubric, final deadline, team availability, or professor-approved scope changes were supplied. Recommendations identify planning risks rather than predict grades or declare the full project infeasible.

Severity: P1 means a release/commitment gap to resolve before approving the plan. P2 means a concrete acceptance or execution gap to resolve before the affected milestone begins. These are document findings, not software vulnerabilities.

## Confirmed findings

### F1 — P1: Registration can be omitted while the accounts milestone passes

Proposal evidence: section 3, User Accounts and Watchlists, states users will be able to create an account and log in. Section 4, Front-end, also anticipates login and registration pages.

Roadmap location: `docs/ROADMAP.md:124` makes registration conditional with “if included”; lines 127–129 permit seeded accounts and test existing-user watchlists. The demo starts with a prepared account at line 17. The release checklist has no account-creation check.

Failure scenario: the team builds login/logout for two seeded users, passes all stated M4 checks, and demos watchlists. A professor asks to create a new account, and that promised feature is missing.

Impact: an explicit MVP commitment becomes optional without an approved scope change.

Required change: make user-initiated account creation mandatory, through the selected identity mechanism, and add a gate covering a new user, sign-in, watchlist persistence, and sign-out. Keep prepared accounts for rehearsal, but do not let them substitute for signup. If signup is to be cut, record the professor's approval separately. This does not imply implementing custom password storage or every account-management feature.

Suggested acceptance: a previously unregistered demo user can complete the supported signup flow, sign in, create a private watchlist entry, sign out, and sign back in to retrieve it. Duplicate/invalid registration and unauthorized requests are handled safely.

### F2 — P1: Calendar and capacity remain unresolved, so the plan cannot demonstrate semester feasibility

Proposal evidence: section 7 claims the project is achievable within the remaining semester; section 6 promises incremental delivery and a final demonstration.

Roadmap locations: `docs/ROADMAP.md:70` and `:77` defer actual dates to M0; `:183`–`:191` allocate percentages of an unspecified remaining period. The file remains explicitly an unapproved proposal at line 3.

Failure scenario: everyone accepts the milestone descriptions but nobody assigns dates or checks available hours. Authentication and the ML integration share the same API/frontend contributors, and both arrive just before the demonstration with no real stabilization window.

Impact: there is no way to determine whether the protected final 25% exists, when a scope cut is triggered, or whether the critical path fits the semester. This is a missing scheduling decision, not proof that the project is late; the actual deadline was not supplied.

Required change: before approving the roadmap, add the actual submission/demo dates, each person's realistic capacity, milestone review dates, an integration checkpoint, and an explicit feature-freeze date. Estimate the first milestone in small tasks before extrapolating the rest. Assign one accountable coordinator per milestone, including co-led milestones, and name coverage for absences.

Suggested acceptance: all four agree on dated checkpoints and owners; the first end-to-end release and ML research review occur before the freeze; a rehearsal and a recovery session have reserved time. If estimates exceed capacity, negotiate scope rather than silently shortening verification.

### F3 — P2: The prediction gate proves agreement with the offline model but not a complete user request-and-return workflow

Proposal evidence: section 2 says the user can receive a prediction; section 4, Back-end and Database, describes requesting predictions and storing/retrieving their records. Section 3 promises users can return to previous predictions.

Roadmap locations: `docs/ROADMAP.md:144`–`:149` require inference, records, and replay separation, but the gate does not explicitly require creating a forecast through the browser and later finding the same persisted result. The proposed prediction contract at line 175 leaves generation versus retrieval semantics unresolved. The demo at line 21 opens a recorded prediction rather than exercising creation.

Failure scenario: API inference is tested, historical replay records populate a history screen, and the demo shows those records. The user-facing action that creates a prediction, handles a retry, and retrieves that exact result after refresh was never integrated.

Impact: component checks pass while the forecast workflow described in the submission remains incomplete. Historical replay is a sound demo technique, but it does not by itself prove forecast creation and persistence.

Required change: define whether selecting a stock automatically generates a forecast or an explicit action does so. Specify the output and retry policy, then add one browser-to-API-to-database acceptance test. Define whether prediction history is per-user or shared; the proposal does not settle this, so either can be chosen if clearly documented.

Suggested acceptance: from the analysis page, generate a prediction using a declared cutoff, receive its stable identifier/model/horizon, refresh or sign back in as applicable, and retrieve the same stored prediction. Repeating the request follows documented deduplication rules. Then run outcome resolution on a historical example and verify pending-to-completed behavior without rewriting the original forecast. A time-controlled replay can prove this without waiting for a trading day, if clearly labeled.

### F4 — P2: Personal dashboard is promised but has no explicit milestone acceptance check

Proposal evidence: section 3, User Accounts and Watchlists, promises a personal dashboard for viewing and accessing followed stocks. Section 4 lists a personal dashboard among the expected pages.

Roadmap locations: `docs/ROADMAP.md:118`–`:129` cover account/watchlist UI and ownership, but do not require opening a followed ticker from a personalized list. The demo at lines 17–20 searches first and tests persistence only afterward.

Failure scenario: backend CRUD and add/remove buttons pass M4, but there is no navigable saved-stock list or way to open analysis from it after login.

Impact: persistence is present, but the promised dashboard user experience is missing.

Required change: define the smallest dashboard as the signed-in user's watchlist page or panel. No extra charts, summary cards, or separate dashboard framework are necessary. Add empty-state, saved-list rendering, open-analysis, removal, and return-navigation checks.

Suggested acceptance: sign in, see your saved stocks, open one into its analysis page, return to the list, remove it, and verify it stays removed after refresh. A new user sees an understandable empty list.

### F5 — P2: The indicator completion gate permits less than the stated target and proposal

Proposal evidence: section 3, Stock Search and Analysis, plans several indicators, while explicitly allowing the exact indicator selection to change.

Roadmap locations: `docs/ROADMAP.md:33` names moving average followed by RSI/MACD/Bollinger as capacity permits; line 116 lets M3 complete with one verified indicator. Line 46 also proposes one indicator as fallback. The release checklist at line 230 verifies numerical/date alignment but does not settle the minimum set.

Failure scenario: only a moving average ships, the milestone is marked complete, and the professor expects several analysis indicators based on the proposal.

Impact: an internal minimum can undercut the submitted expectation. This is not an obligation to implement every example named in the proposal; the specific set is intentionally flexible.

Required change: distinguish an early M3 increment from final-release acceptance. Agree on a small final set, for example moving average plus RSI, and list the others as optional. If only one will ship, acknowledge the reduction and obtain agreement instead of presenting the original analysis scope as fully delivered.

## Commitment coverage

| Submitted commitment | Roadmap support | Review conclusion |
| --- | --- | --- |
| Account creation and login | M4 | Partial: signup is optional; fix F1 |
| Saved personal watchlist | M4 ownership/persistence gate | Aligned |
| Personal dashboard | Account/watchlist UI mentioned | Partial: add navigation/return workflow, F4 |
| Ticker lookup and historical chart | M1/M2 | Aligned; limited symbols/history are permitted by proposal section 7 |
| Several useful indicators | M3 | Minimum final set unresolved, F5 |
| ML-based short-term direction | M5 | Aligned in design; browser creation/retrieval needs a gate, F3 |
| Previous predictions and observed outcomes | M5 | Strong research design; explicitly verify persisted user workflow |
| Frontend/backend/database integration | M1/M2 and later gates | Aligned; fixture-first sequencing is a sensible intermediate step |
| React, FastAPI, relational storage | Architecture and M2 | Aligned with expected stack |
| Noah/frontend; Gavin/API; Parth/data/ML; Vladislav/database/testing/deployment | Ownership table | Aligned; specific deadlines/capacity still absent |
| Incremental branches, PR review, and integration | Working agreements and gates | Aligned as a plan; execution was not audited |
| Final testing/deployment/demo | M6 | Detailed gates; hosting requirement remains to be confirmed |

## Things that should not be reported as defects

- Reordering work to get stock search/chart integration before accounts does not violate the proposal. The proposal describes broad stages, not an immutable task sequence.
- A restricted daily-bar universe is expressly consistent with its feasibility section.
- No evidence establishes a promise of intraday streaming, guaranteed returns, an exact-price model, or a particular accuracy threshold. Do not add those requirements.
- A model that does not outperform a baseline can still demonstrate valid educational research. The team must still deliver the agreed inference/evaluation workflow or clearly obtain a scope change.
- Historical replay, an offline fallback, chronological evaluation, versioned artifacts, and continuous integration strengthen the proposal rather than contradict it.
- The proposal says deployment is part of the final work, but does not establish a requirement for public cloud hosting. Confirm the rubric instead of assuming hosting is optional or mandatory.

## Unresolved risks requiring evidence, not invented findings

1. Current implementation progress: this review compared documents, not remote branches, PRs, or working features. The roadmap's October 29 status paragraph is historical and should be dated explicitly or replaced by a maintained status table. No conclusion about all teammates' current progress follows from this checkout.
2. Provider availability and permitted use: the plan explicitly requires a provider decision, but the decision itself was not supplied. Confirm access before assigning ingestion and ML delivery dates.
3. Point-in-time ML data: the plan correctly forbids future information. Verify that adjusted prices, provider corrections, chosen stock universe, and replay timestamps actually respect that rule when datasets exist. This is a research verification item, not a confirmed leakage bug.
4. Workload concentration: Parth owns data, indicators, and research, while Gavin and Noah appear throughout integration. The role split matches the proposal, but capacity must be checked in the dated plan. Move adapter or indicator implementation to another teammate if estimates show a bottleneck.
5. Professor expectations: deadline, presentation duration, specific indicator count, hosting, and minimum model expectations need the actual rubric or explicit agreement. Neither document can substitute for that evidence.

## Recommended correction order

Before approving the roadmap:

1. Make account creation mandatory or document an approved scope reduction.
2. Fill in real dates, capacity, one accountable milestone coordinator, and the feature freeze.
3. Add the small dashboard flow and one complete generate/persist/retrieve prediction flow to acceptance criteria.
4. Agree on the final indicator set and distinguish partial increments from release completion.
5. Create a submission traceability checklist linking each promised capability to its milestone, issue, test, and demo step. Preserve the submitted proposal; put changes in a dated decision log.

Then create only the near-term implementation issues in detail. Keep all four submitted MVP areas in final acceptance unless the professor agrees to a reduction. First demonstrate one integrated stock-analysis flow; start data/ML decisions in parallel so prediction work does not wait for the final UI.

Recommendation: retain the architecture and milestone structure, revise the acceptance gates, and approve only after scheduling decisions are filled in. No rewrite of the application is justified by this review.
