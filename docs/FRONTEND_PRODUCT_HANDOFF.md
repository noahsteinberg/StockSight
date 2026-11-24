# StockSight product and frontend implementation handoff

Owner/coordinator: **Vladislav (Vlad), @Hab1yer**. Requested by Noah after the
daily-data rollout. This is a proposed implementation plan, **not implemented
features and not permission for an AI to start coding**. Review checkpoint:
main `e9a4620`, with PR #16 still open and reporting merge conflicts.

Master execution tracker: [issue #19](https://github.com/noahsteinberg/StockSight/issues/19),
assigned to @Hab1yer. Keep approved decisions and per-increment progress there.

## 1. Mandatory instruction for Vlad and his AI agent

**Before changing application code, API contracts, database schema, dependencies
or UI behavior, ask the human supervising the agent to review the proposed
changes and explicitly approve the first increment.** Noah authorized writing
this document and consolidating issues; that does not authorize another agent
to implement every proposal below automatically.

Read AGENTS.md and CURRENT_HANDOFF.md first. Verify current main, PRs, schema and
working tree; checkpoints here can become old. Explain the existing behavior,
proposed behavior, affected pages/files/contracts, data dependencies and how the
increment will be tested. Show a small wireframe or screen outline. Ask concise
multiple-choice questions about unresolved UX decisions, with a recommendation
and a free-text alternative. Ask in small batches, usually three questions.
Record answers and the approved scope in the master issue. **Wait for an explicit
answer/approval; silence is not approval.** Reuse earlier decisions instead of
asking the same question repeatedly. Ask again when scope materially changes.

Do not present a finished implementation for the first time as the approval
request. First make the intended change concrete and reviewable; get approval;
then implement a small branch/PR. Show the result for human review before
merging or deploying. A later explicit authorization can cover a named merge or
rollout; do not repeatedly ask for already-granted permission.

Suggested opening questions (these are **unanswered proposals**, not decisions):

| Question | Recommended option | Alternatives |
| --- | --- | --- |
| What ships first? | Explore + comparison + existing watchlist | Preferences in the first release; stock-detail polish only |
| Which navigation should be primary? | Explore, Analysis, Compare, Watchlist | Keep current navigation until the first feature ships |
| What should “recommendations” mean initially? | Explainable matches to research filters | Hide ideas until ML is approved; separately approve a historical-metric ranking |

Before the relevant later increment, also ask: is signup optional for browsing
(recommended yes); should preferences be skippable (yes); maximum comparison size
(four); quote widget during historical replay (hide it or clearly label it as
present-day); and whether preferences belong in an account page or small panel.
Confirm filter defaults, reset behavior, mobile layout and return-after-login
behavior rather than inventing consequential details.

Copyable instruction for the next agent:

> Read AGENTS.md, docs/CURRENT_HANDOFF.md and docs/FRONTEND_PRODUCT_HANDOFF.md.
> Audit current main and open PR #16. Do not change application code yet. Explain
> the first proposed increment, show its page flow/wireframe, ask my unresolved
> UX questions as concise multiple-choice questions, and wait for me to approve
> the plan. Then implement only that approved increment in a focused branch,
> test it, and return it for review before merging/deploying. Never invent prices,
> sector metadata, model signals or accuracy. Do not resume paused ML research.

## 2. Product direction and feasible first release

StockSight should help someone **discover supported stocks, understand their
history, compare a few choices, save a private watchlist, and optionally tailor
discovery to research interests**. This is stock research, not a brokerage or
full portfolio-management system. It should remain useful even when no ML model
qualifies. No holdings, trades, money balances, tax lots or portfolio optimizer
are needed for this release.

First useful release: a real Explore list backed by stored data, a clear stock
detail, two-to-four-stock comparison, and the existing persistent watchlist.
Optional preferences and explainable discovery follow. Approved ML signals can
plug into the same views later. Do not make sector enrichment, a profile, a
new model or a vendor widget prerequisites for basic browsing/comparison.

Prefer a few working views over many empty pages or feature cards. Keep Gavin's
navy/white UConn identity, IBM Plex fonts, plain CSS, native chart and accessible
controls. Add features within that visual system; no framework/router/chart
replacement without a separately approved need.

## 3. What exists, and what does not

| Capability | Reviewed state |
| --- | --- |
| Deployment | Vercel main-only deployment, same-origin React → FastAPI → Supabase |
| Daily prices | 494 tickers, 1,214,290 retained bars, latest sessions 2026-11-23 at verification; up to 2,500 per stock |
| Updates | Validated Yahoo offline CLI, additive migration 0006, audit/recovery, guarded idempotent writes |
| Actions | Manual preview and update both passed for all 494; Noah reports enabling the schedule variable; first scheduled event not yet observed |
| Price UI | Search, 1M/3M/1Y/Max, price/volume, inspection, replay, CSV, explicit stored-data refresh |
| Indicators | Backend SMA20 and Wilder RSI14 with price/indicator snapshot agreement |
| Accounts | Auth0 + opaque app sessions + private watchlists; preserve ownership/CSRF/session contracts; full hosted two-account acceptance still needs recorded evidence |
| Latest quote | PR #16 proposes TradingView widget; unmerged, conflicts reported; not a backend quote feed |
| Catalog | Existing stock fields: symbol, name, exchange, currency; importer can set name=symbol and exchange=UNKNOWN; no sector field |
| Search API | GET /api/stocks?query=... returns at most 50 matches; not a paginated 494-stock screener |
| Missing product features | Explore, comparison, preferences, sector enrichment, discovery recommendations and their APIs |
| ML | Research paused, no approved serving artifact, no signal/evaluation API, no forecast/outcome persistence |

The manual preview was run 45328253600; manual update 45328799719. Both passed
without new price changes because history was already current. User confirmation
of the enable variable is not evidence that a scheduled event has run. Record
the first automatic result when it actually happens. Do not rerun migrations,
reset Supabase or reimport the frozen Parquet as part of frontend work.

Current app routes are in use-page-route.js; App.jsx owns navigation and selected
symbol; Analysis.jsx owns stock detail; Pages.jsx holds other current pages.
repository.py owns bounded daily reads; db.py defines actual tables. Existing
views called Predictions and Model performance are honest unavailable views.

## 4. Daily close and latest quote: two compatible displays

**Do not integrate the widget's displayed number into daily_bars.** A quote and
a completed session close are different observations. Searching a stock should
load its stored history and, if approved, its independently selected widget.

| Data | Display/consumer | Storage rule |
| --- | --- | --- |
| Completed daily OHLCV | Chart, indicators, CSV, watchlist close/change, descriptive metrics | Existing validated updater → daily_bars; dates and revision from the API |
| TradingView latest quote | Small optional panel on the selected stock detail | Vendor-owned iframe; no scraping, extraction or database writes |
| ML signal | Separate dated research panel with target/horizon/version | Future approved offline inference and immutable records; never inferred from a quote |

Use “Latest stored close · [actual session]” and “Latest quote · TradingView ·
may be delayed”. Do not advertise an exact current price or universal real-time
coverage. Vendor timestamps/delay indications remain vendor-owned; iframe load
success is not proof of available data. TradingView documents delayed stock data
and does not expose widget values as an export/data API:
[data FAQ](https://www.tradingview.com/widget-docs/faq/data/).

PR #16 integration checklist, after human approval:

1. Inspect its current diff/base and CI again. Reconcile conflicts on a fresh
   branch from current main; do not restore its old application/handoff files.
2. Port/rebase MarketQuote.jsx, tradingview-symbols.js, isolated CSS and relevant
   tests. Preserve today's Refresh data action, chart layout, revisions, auth
   behavior, daily updater and current documentation. Obtain review before merge.
3. Keep the verified exchange/share-class map, attribution, retry/link fallback,
   cleanup on ticker changes and range-change independence. Do not treat that
   map as verified company/sector metadata in the database.
4. Fix all stale November 12/“refresh unfinished” statements in its docs. Show
   actual as_of from current responses. Use one widget on stock detail, not 25
   external iframes in Explore or one per comparison cell.
5. Recheck AAPL/MSFT, BRK-B/BF-B, a blocked script and unsupported listing, fast
   ticker switches, historical replay, 320px layout and attribution visibility.
   Mocked widget tests and a real-vendor browser check are different evidence.

Refresh data re-fetches stored chart/indicator/watchlist responses. It neither
runs Actions nor downloads Yahoo. A new page load reads current storage; an
already-open page needs refresh/reload. No polling is required for the first
release. A future “new data available” hint needs approval and must not disrupt
a pinned date or replay. A widget can update independently on its vendor's terms.

## 5. Navigation and page responsibilities (approval required)

Recommended primary navigation: **Explore · Analysis · Compare · Watchlist**.
Preferences live under the account menu; Methodology/help in secondary navigation.
Signals and model evidence are contextual links until real ML exists. Preserve
old URLs/bookmarks, back/forward, selected symbol and keyboard focus behavior.

| Page / route proposal | What it shows | Main next actions |
| --- | --- | --- |
| Explore / #/explore | Search, bounded stock list, actual last close/date, sector when verified, compact filters, comparison selection and discovery explanation | Open stock; compare; save; clear filters |
| Analysis / existing #/analysis?symbol=AAPL | Current chart tools plus verified company/sector context, optional separate quote, clear freshness and compact signal availability | Save; add to comparison; inspect/replay/export; view evidence |
| Compare / #/compare?symbols=AAPL,MSFT&range=1y | Two-to-four stocks, common-date price comparison, same-basis metrics table and separate signal availability | Add/remove stock; change range; open detail; save individual stock |
| Watchlist / existing #/dashboard | Existing private saved stocks with useful dates/changes, search/sort and comparison selection | Open; compare selection; remove; edit preferences |
| Preferences / #/preferences | Optional research-interest questionnaire, saved/default state, edit/reset | Save; skip; view matching stocks |
| Signals / existing #/predictions?symbol=... | Real typed unavailable initially; later approved signal and history | Return to detail; see same-model evidence |
| Evidence / existing #/performance | Honest unavailable until approved evaluation exists; then versioned evidence | Read methodology; return to source stock |
| Methodology / existing #/methodology | Sources, close vs quote, data dates, metrics, match rules and ML limitations | Understand a metric/source |

Do not immediately add all these as prominent tabs. Agree whether Explore becomes
the landing page; keep legacy root behavior until the approved navigation change.
Existing login/signup/reset-password routes remain intact. Do not silently change
Auth0 callbacks or replace account infrastructure to add preferences.

### Explore: an actual discovery surface

Start with search, all/sector filter, sort and 25-item pages (maximum API page 50).
Default alphabetical ordering until a different reviewed sort is implemented.
Include supported-universe count, filtered count, last stored session and a clear
filter reset. Optional controls must earn their space; put advanced filters in a
small expandable panel. Missing fields show “Unknown” or “Unavailable”, not zero.

Each row/card: ticker, verified name or ticker fallback, sector/Unknown, latest
stored close + date, historical daily change when valid, Save and Compare. Keep
two-to-four comparison selections in a small tray with count and Clear. Guest
browsing/comparison works without login; saving uses the existing sign-in flow.
Do not request 25 separate full histories or indicators for one list page.

```text
Explore stocks                     Search ticker or company
Sector [All]  Sort [A–Z]  [More filters]  [Reset]
494 supported · 25 shown · stored daily data
Stock / sector     Last close / date     Daily change    Save  Compare
...
Compare selected (2 of 4)                         [Compare]
```

Loading, empty results, no supported metadata, stale metrics and API failure need
different states. Preserve filters/pagination in the URL. Do not silently broaden
a user's filter to produce results. The old local autocomplete is a suggestion
aid, not the authoritative screener or company/sector database.

### Analysis: preserve the strongest existing work

Keep the full-width SVG chart and current date inspection/replay/CSV, SMA/RSI
toggles, ranges, saving and saved-stock chips. Add a compact company/sector line,
Add to comparison and an optional separate latest-quote panel. Retain chart
snapshot-mismatch handling. Current quote must not masquerade as the selected
historical replay date; approve hiding or explicitly separating it during replay.

Below the chart: concise historical metrics with definitions/coverage, then an
honest “Research signal unavailable” panel with a contextual evidence link.
Avoid large repeated disabled “Generate prediction” panels when the API cannot
generate anything. Reword/reorganize them only after human review; do not fake ML.

### Compare: meaningful differences on a common basis

Limit to four canonical supported symbols. Validate/deduplicate the URL and make
over-limit/unknown symbols explicit. For the first chart, show price-only change
indexed to 100 at the first common valid date. Use common trading dates, disclose
actual start/end and exclude missing dates rather than forward-filling prices.
Never compare nominal dollar price as if it measured which stock performed best.

Show stored close/date per stock separately from the common-window comparison.
If histories end on different dates, align to the shared cutoff and disclose it;
never silently mix a stale stock with a newer one. New/short histories need a
shorter disclosed common window or an unavailable comparison, not invented bars.

Metrics can include period price change, observed variability and drawdown only
after their price-basis and numerical rules pass review. No total-return claim
without validated corporate-action/dividend handling. For split-affected or
incompatible windows, show the raw chart with a warning and mark derived metrics
unavailable; do not rank a split artifact as an opportunity. Use a legend that
does not depend on color, keyboard-readable table and a mobile-contained table.

### Watchlist: the user's research shortlist

Reuse the existing watchlist repository, ownership checks, 100-stock cap and
retry/error UI. Show last stored close and actual date, sort/filter known values,
and let the user compare selected entries. Do not turn watchlist membership into
a holding or an investment recommendation. No account's list/cache may appear
for a second account, including after slow requests, logout or quick switching.

## 6. Optional preferences: exact proposed questions and lifecycle

This is a lightweight research-preference profile, not a suitability assessment.
Browsing stays available without it. Offer a skippable invitation after sign-in
or from Watchlist; do not hijack every login. Confirm login-return behavior first.

| Proposed question | Choices | Use |
| --- | --- | --- |
| What would you like to do? | Learn about stocks; Compare choices; Track a shortlist; No preference | Help text/default discovery section, not price prediction |
| Which sectors interest you? | Multi-select from the verified catalog; All sectors / No preference | Transparent inclusion filter; disclose taxonomy/Unknown coverage |
| What research horizon interests you? | Weeks; Months; Years; Not sure | Content preference; does not select/retrain an unapproved ML horizon |
| Which chart window should open by default? | 1M; 3M; 1Y; Max | Maps to existing 1mo/3mo/1y/all API enums |
| Which historical fluctuation level would you like to explore? | Lower; Middle; Higher; No preference | Optional descriptive filter only after reviewed metrics/thresholds exist |

Defaults are neutral, not an inferred risk tolerance. Disable/explain the final
question until its metric exists. Do not collect income, wealth, bank details,
age, holdings, identity documents or passwords. Keep the initial form short,
editable, resettable and skippable. A long-term preference does not turn the
one-session research model into a long-term forecast.

Proposed storage: one backend-owned user_preferences row keyed to existing
UserIdentity.id, with schema_version, optional purpose/horizon/default_range,
sector IDs, optional observed-volatility preference, created_at and updated_at.
Validate enumerations/sector IDs and size limits server-side. A later migration
must inspect the actual Alembic head; do not assume 0007 is free. Preserve existing
tables and RLS/browser-role restrictions; use current Auth0 identity resolution,
not Supabase auth.uid(). No direct browser-to-Supabase profile access.

Flow: form → usePreferences/adapter → authorizedFetch → private FastAPI service
→ owner-keyed repository → preferences table. Reads/writes/reset require current
account checks; cookie writes retain Origin/CSRF protection. No client-supplied
user_id decides ownership. Clear user-specific caches on logout/account switch;
guest filters can remain ephemeral but private preferences must not be saved in
shared localStorage or URLs. Test two-account isolation and refresh persistence.

## 7. Recommendations: separate matches, history and model evidence

There are three different concepts, and the UI/API must identify which is shown:

1. **Preference match, feasible without ML:** “Matches your selected sectors” or
   “Matches your research filters”. Backend uses verified metadata and approved
   historical filters. Return the reasons and input dates. Default deterministic
   alphabetical ordering is acceptable; do not manufacture a recommendation score.
2. **Historical research sort:** optional, separately approved ordering such as
   past price change or observed variability. Label the window, price basis and
   rule version. Past movement is not a forecast or a model success rate.
3. **Approved ML signal, future:** served only after Noah/team approve a target,
   horizon, evaluation and artifact. Display availability, cutoff, publication,
   target session, same-model evidence and model/data versions.

First release language should be “Ideas to explore”, not Buy/Sell/Hold orders.
Do not imply personalized financial suitability or accurate future returns.
Concrete example, **illustrative UI behavior only**: a signed-in user selects
Technology and a 1Y chart default. Explore displays supported stocks with verified
Technology metadata and explains the match. It still says “No approved model
signal” if no model is serving. It does not invent a probability for that user.

Profile fields filter or reorder eligible stock facts through explicit rules;
they do not automatically become ML training inputs or alter the model's score.
Personalized requests stay private; do not send preference/user IDs to vendor
widgets or put them into public cache keys. Offer “Use my preferences” and a
clear reset, so the user understands why results differ from the full universe.

## 8. Data, APIs and frontend adapters to add deliberately

All entries marked proposed below need contract review and tests before coding.
Do not change the response type of existing /api/stocks to break autocomplete.

| Consumer | Existing or proposed contract | Responsibilities |
| --- | --- | --- |
| Search/detail | Existing GET /api/stocks?query=..., /stocks/{symbol}/prices, /indicators | Preserve current bounded contracts and canonical symbols |
| Explore | Proposed GET /api/explore?query=&sector=&sort=symbol&limit=25&cursor= | New paginated catalog/summary DTO; total/filtered counts; deterministic tie-break; no private state in public response |
| Compare | Proposed GET /api/compare?symbols=AAPL,MSFT&range=1y | Validate 2–4 symbols; bounded shared-date series/metrics; per-stock revisions; no provider requests |
| Sector options | Proposed GET /api/sectors | Verified taxonomy, metadata version and unknown/missing coverage |
| Preferences | Proposed GET/PUT/DELETE /api/me/preferences | Authenticated owner-only reads, validated save/reset; current session/CSRF rules |
| Personalized ideas | Proposed GET /api/me/discovery?limit=25 | Private preferences + eligible catalog/metrics + explicit match reasons; never a public user-ID query |
| Signal panel | Proposed GET /api/stocks/{symbol}/signals?horizon_sessions=... | Start with real typed model_not_approved/unavailable; do not assume an arbitrary horizon is supported |
| Model evidence/history | Existing unavailable views; future bounded APIs from ML spec | Available only with reviewed persisted records/evaluation; not part of first Explore increment |

Catalog row proposal: symbol, nullable verified company_name/sector/exchange,
metadata_status/source/updated_at, last_stored_close, as_of_session,
series_revision, nullable daily_change_pct with metric_status/reason. Filterable
metrics additionally need calculation_version, price_basis, window_start/end,
input_revision and eligibility/freshness. Nulls are not zero; source coverage
does not imply every field is known for all 494 stocks.

Metadata is **new work**. Inspect existing names/exchanges before overwriting
them. Parth should review a permitted metadata source or small curated import
with provenance. Company name/exchange can be enriched independently of sector;
do not infer sector from ticker. Prefer a reviewed small sample and an idempotent
import before all-symbol enrichment. Retain Unknown rows and disclose incomplete
sector coverage. No per-search Yahoo info request or hundreds of client widgets.

Optional catalog_metadata (symbol FK, name/sector/exchange, source/taxonomy/version,
verified/fetched dates) can avoid rewriting historical series provenance. Exact
columns and migration need approval. A static reviewed map can bootstrap known
metadata but must not be misrepresented as a complete current database source.

For sortable whole-universe historical metrics, build a small versioned metrics
snapshot offline from stored bars after successful refresh, with an idempotent
backfill for initial use. Do not compute 494 full feature histories per public
request. If prices advance but metrics fail, expose stale/unavailable metrics by
input revision and retain usable charts. Do not run a full metrics rebuild once
per symbol inside the Yahoo writer. Keep ingestion, derived metrics and inference
as separate jobs/steps with explicit dependency/partial-failure handling.

The first Explore version can use indexed/batched latest-bar summaries without
a new metrics job. Comparison can calculate a bounded 2–4-stock window in the
backend. Definitions must pin rounding, sample size, missing-date policy,
corporate actions and window endpoints. Percentage price change is not total
return; risk summaries are descriptive and need Parth's numerical review.

Frontend modules should be small JS DTO validators/adapters and cancellable hooks
(for example explore-api.js/use-explore.js, compare-api.js/use-compare.js,
preferences-api.js/use-preferences.js, signal-api.js/use-signal.js). Reuse existing
timeout/retry/error and authorizedFetch patterns. No TypeScript migration is
required to implement typed API/view contracts. Cancel superseded requests and
prevent a slow prior symbol, account or filter response replacing the new one.

## 9. ML integration boundaries and deferred work

Read ml/README.md and the two older integration documents for detailed scientific
contracts. Their old “ingestion unfinished” and “AAPL-only foundation next” status
is superseded by this plan/current handoff. Their honesty, versioning, ownership,
point-in-time and promotion constraints still apply.

No research model is approved. Existing next-session and continuous-target work
did not establish deployable directional accuracy; weak development-fold ranking
is not serving approval. Longer horizons are an idea to evaluate separately,
not a UI toggle that changes the old model's meaning. ML remains paused until
Noah explicitly resumes it. Do not run training, tune thresholds, score protected
data, export a serving artifact or merge an old research branch for this task.

Immediate integration task after core discovery: define/test the real unavailable
signal response and connect existing views for supported stocks. Keep unknown
symbols 404, invalid inputs 422, sanitized storage failure 503, and a valid
supported stock without a model 200 unavailable. Available fixtures are test-only.
Probability/confidence, rank percentile, historical volatility and match strength
are different concepts. Do not show fabricated percentages, explainability or
predicted chart extensions. Future provenance must separate replay from publication.

Later, separately approved: immutable model manifests/versions, prediction batches,
forecasts/outcomes and reliability APIs; trusted artifact/feature parity; offline
settled-input inference; outcome resolution; then shadow serving and public
activation. Existing 01:17/06:17 price jobs use a 30-minute completed-session
buffer; that is **not ML settlement/publication approval**. Older research has
additional timing rules. Freeze a separate settlement policy with Parth/Noah,
including provider revisions and next-available entry, before inference.

Frozen-research backlog remains preserved: audit saved rankings for stock/day
concentration, turnover and publication timing first; predeclare any candidate
before protected 2019–2021 evaluation; keep the final 2022–2026 test reserved.
Changing the issue tracker does not resume or complete that research.

## 10. Incremental implementation order and ownership

| Increment | Reviewable deliverable | Gate / coordination |
| --- | --- | --- |
| 0: approve direction | Current audit, selected navigation, wireframes, answers and first PR scope in master issue | Vlad + supervising human; no application code yet |
| 1: useful Explore | Paginated supported-stock summaries, search/reset, real close/date, compare-selection tray | Preserve existing API/search/auth; no fake sector or metrics; Gavin reviews API/UI contracts |
| 2: Compare + watchlist flow | Common-date 2–4-stock chart/table, shareable public comparison URL, private watchlist compare action | Parth reviews price basis/formulas; real empty/error/short-history states |
| 3: metadata + quote/detail polish | Reviewed metadata import and sector filter; resolve/review PR #16; compact stock context | Parth reviews metadata/widget; reconcile current main and run vendor checks before merging |
| 4: optional preferences + ideas | Skippable private preferences, explicit matching reasons and reset; no ML claim | Approve form/questions/migration first; Gavin reviews session/ownership; Vlad tests persistence |
| 5: honest ML connector | Real typed unavailable signal API/adapters integrated into stock views | Noah reviews meaning; no training or prediction-table scaffolding needed to show unavailable |
| Later: evaluated ML | Only an approved target/artifact and separately reviewed persistence/inference/outcomes | Noah/Parth research; Gavin API; Vlad persistence coordination; separate approval |

Metadata can be worked on in parallel by a human teammate after agreement, but
do not launch unsupervised agents or silently reassign another person's work.
Each increment should be a focused branch/PR with exact behavior and evidence,
not one huge refactor. If the semester deadline is tight, ship increments 1–2
and honest states first. Preferences/ML must not block a usable research app.

## 11. Acceptance and regression checklist

- Show real supported data end to end: Explore → detail → Compare → sign in →
  Save → reload → Watchlist → compare saved items. A guest can discover/compare.
- Show an Unknown sector/name and a no-results filter honestly. No silently
  substituted data, hardcoded dates or invented company facts.
- Verify daily close vs vendor quote labels, provider failure isolation, latest
  stored dates after refresh, replay behavior, CSV and indicator snapshot alignment.
- Test comparison missing/short/stale histories and split-affected windows; pin
  numerical conventions, common-date normalization and nullable metrics.
- Test preferences save/edit/reset/reload and two-account isolation, including
  stale network responses. Keep the existing watchlist error visible until Retry.
- Test keyboard navigation, visible focus, reduced motion and 320/390/1440px
  layouts. Tables may scroll in their own container; pages must not overflow.
- Keep full-universe provider downloads, metrics backfills and ML out of browser
  requests. No new paid service, API key, public database grant or data reset.
- Run relevant backend Ruff/pytest, frontend lint/build and meaningful browser
  tests. Use disposable _test databases for schema/write tests. Distinguish unit,
  TestClient, HTTP, mocked-vendor, real-vendor and hosted Auth0 evidence.
- Review migration DDL and any hosted-write preview with the supervising human
  before applying it. Preserve daily-refresh audits, recovery data and source hash.
- Human reviews the completed increment before merge/deploy. Main deploys to
  Vercel; feature branches currently do not. Update CURRENT_HANDOFF.md, API and
  architecture guides when an actual capability changes.

## 12. Issue consolidation and remaining operational follow-up

The master issue is the execution tracker for this plan. Proposed consolidation:

| Older issue | Disposition and preserved responsibility |
| --- | --- |
| #1 frontend identity | Completed; existing restrained application replaces the old landing page |
| #2 phase-one validation/mobile/tests | Completed; current CI/browser coverage and a fresh dependency audit provide evidence |
| #7 hosted data/refresh | Completed manual delivery; first scheduled event observation remains an operational follow-up |
| #11 CI/billing restriction | Completed; current CI and both real Actions refresh runs pass |
| #5 unavailable ML connector | Superseded by increment 5, not claimed implemented |
| #6 prediction persistence | Consolidated into later approved ML work, not claimed implemented |
| #8 paused ranking follow-up | Preserved in ml/README.md and section 9; remains paused, not completed |
| #9 artifact/inference/outcomes | Consolidated into later approved ML work, not claimed implemented |

Close superseded issues as not planned under their old standalone scope, with a
link to the master tracker; do not mark unfinished features completed. Leave
PR #16 open for focused review/integration. Preserve older issue bodies/evidence.

Daily-history configuration is finished: manual Actions acceptance passed and
Noah reports the enable variable set. Remaining verification is the first actual
scheduled run and user notification preferences. Do not claim “all live data”:
intraday streaming and backend quote storage are outside this delivery. A new
backend quote feed would require its own provider/rights/timestamps/schema plan;
it is unnecessary to use Parth's independent display widget.

## 13. Reading order and precedence

1. AGENTS.md and CURRENT_HANDOFF.md: instructions and actual delivery/evidence.
2. This document: current product direction, approval gates and phased UX plan.
3. ARCHITECTURE.md, API.md, ACCOUNTS.md, LOCAL_START.md: existing contracts/setup.
4. DAILY_REFRESH.md, PRICES_IMPORT.md, INDICATORS.md: prices/provenance/numerics.
5. FRONTEND_ML_INTEGRATION_SPEC.md and ML_PRODUCT_INTEGRATION_PLAN.md: proposed
   scientific contracts, read with their current-status notices.
6. ml/README.md and linked frozen reports: paused research and evaluation gates.
7. ROADMAP.md/SPECIFICATION.md: earlier team proposal and original milestones;
   do not treat completed milestones there as a current implementation backlog.

This plan supersedes older product-priority/page proposals where they conflict;
it does not override implemented security contracts, recorded research gates or
later explicit human decisions. Preserve historical evidence rather than deleting
it. Keep CURRENT_HANDOFF.md the sole continuation-status file; this file is the
durable proposed product specification, not another competing status handoff.
