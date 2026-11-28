# StockSight release and next increments

The next increment has been implemented on PR #28 for review. Explore now has
explainable research ideas while retaining full search and pagination. Patterns
are embedded in Analysis, with legacy links preserved. The approved 21-session
ranking diagnostic is complete and does not qualify a serving model. Read the
[current handoff](CURRENT_HANDOFF.md) and
[evaluation report](../ml/docs/PATTERN_RANKING_DEVELOPMENT.md) first.

For this increment, review the local Explore panel and Analysis's expanded
patterns, wait for checks on #28, and obtain Noah's release approval before
merge. No schema or environment change is needed. After release, verify public
filters and both methods, then saved-sector suggestions, watchlist actions,
preferences reset and isolation using two real authorized accounts.

The remaining ML work requires an approved new protocol addressing execution
timing, adjustment, universe bias and uncertainty. Keep model output unavailable
while those questions remain unresolved. Earlier proposed steps below provide
the background to this completed increment.

Start with [the current handoff](CURRENT_HANDOFF.md) for branch and delivery
status. [PR #26](https://github.com/noahsteinberg/StockSight/pull/26) shipped
Dashboard, Explore, Compare, preferences, Settings, the quote widget and
research-signal availability. The release starts with 494 supported stocks.
Daily history comes from Supabase after the Yahoo updater writes completed
sessions. The TradingView panel in Analysis displays a separate quote, with
provider-dependent freshness. No widget prices enter the stored history.

## Preview and regression checklist

Open the local review preview at `http://127.0.0.1:5177/` while it is running.
It uses an isolated copy of all 494 hosted series through November 25, 2026
with up to 260 sessions per stock. It includes public market data only.
The Max chart can show a longer history in production. Real Auth0 account
actions are for hosted acceptance. The automated account suite uses test users.

| View | Try this |
| --- | --- |
| Dashboard | Open the bare URL and click the logo from another page. Both should land here. Open Explore with the main button. |
| Explore | Confirm 494 supported stocks, 10 stocks on the first page and 50 pages. Pick a sector, sort by highest or lowest daily change, then use Next and Previous. Search by company and try Reset filters. A result should open the matching ticker in Analysis. |
| Analysis | Pick AAPL, verify the latest stored date, ranges, SMA/RSI, price inspection, Refresh data and CSV. Review the separate quote panel and historical replay. Add AAPL to comparison, and open its research signal. |
| Compare | With one stock, the tray prompts for one more and Compare offers an empty state. With two stocks, check the indexed chart, common dates and change summary. Add up to four, remove one and revisit the link. |
| Signals | Open AAPL's research signal from Analysis and confirm its ticker persists. Model performance is accessible from that view and Methodology. Both say that approved evidence is unavailable. Existing deep links still work. |
| Settings | Set indicator defaults, reload and open Analysis. Confirm the selected indicators start on. Repeat the main path at phone width. |

## Release checklist for #26

The migration, merge and public production checks were completed on November
27, 2026. Step 5 is the remaining acceptance. Use the same order for future
schema releases and verify the current Alembic revision before each rollout.

1. Get Noah's preview sign-off and verify GitHub checks on the reviewed PR
   head. Confirm that `main` is still the production deployment branch.
2. Use the existing [Supabase migration procedure](SUPABASE.md#3-migrate-the-new-database).
   Confirm the hosted Alembic revision before applying anything. From the
   reviewed PR and an authorized direct or session-pooler migration connection,
   apply `0007_user_preferences` once if the revision is still
   `0006_market_refresh`. Verify the new revision, the table's RLS and
   browser-role revocations, and existing price and watchlist reads.
   This is the only new release migration. It adds a private preferences table;
   the stock catalog, daily bars and updater keep their existing schema.
   A disposable PostgreSQL rehearsal preserved all 506 fixture bars,
   verified the Alembic revision and RLS, and confirmed both browser roles
   lack read and write privileges on the new table.
3. Merge #26 into `main` after those checks. Vercel builds production from that
   merge. The release uses the existing app settings and Auth0 configuration.
4. Check production `/api/ready`, Explore totals and categories, a two-stock
   comparison, and Analysis prices and indicators for AAPL and a non-AAPL
   ticker. Review the latest stored dates against the refresh workflow. A
   market holiday or a pending provider update can leave the prior close as
   the latest stored point.
5. With authorized test accounts, verify sign in, watchlist save/reload/remove,
   sign out, and sign in as a second account. From Dashboard or Settings, save
   purpose, sectors, horizon and a default chart window. Confirm reload restores
   them, Explore explains sector matches, Analysis uses the saved window, and
   the second account sees neither the first watchlist nor its preferences.
   Verify reset as the first account and record the results in the current handoff.
6. If production has a regression, follow [Vercel rollback](VERCEL.md) and
   verify the previous deployment. Retain the additive table when rolling back
   the application.
7. Reconcile the stacked PRs #20–#24 and the quote PR #16 against what shipped.
   Link their delivered work to #26 and record any scope that still needs review.

## Assign the next work

Vlad (@Londarh) coordinates the frontend follow-up with Gavin (@Hab1yer) on
hosted account acceptance, Parth on price and metadata inputs, and Noah on ML
research approval.
Use [issue #27](https://github.com/noahsteinberg/StockSight/issues/27) to record
acceptance and link follow-up work. Give the next agent this file, the current
handoff, and the relevant specialist guide.

**Before changing code, contracts, schema or UX, the next agent must show its
supervising human the proposed increment and a short screen outline, ask focused
multiple-choice questions for unresolved UX decisions, and wait for explicit
approval.** Reuse agreed behavior and record the chosen scope, including how to
verify it. Return the result for review before deployment.

### First increment: make exploration useful with existing data

Start after hosted acceptance. Keep Dashboard as the watchlist home and
Explore as the public discovery page. Consider an opt-in **Research ideas** view
within Explore that starts with saved sector matches and allows a user-selected
descriptive sort. Reuse public Explore and private discovery, their pagination,
and the existing comparison tray and watchlist actions. Show the reason for
each match, the last complete session and the exact calculation for any new
metric. Positive or negative daily change is observed price history.

Keep purpose and horizon in optional private preferences. In this release,
sectors drive matching and the chart window drives Analysis/Compare defaults.
Purpose and horizon are saved for future behavior. As the first follow-up,
propose one useful effect for each, such as highlighting Compare for
`compare`, or selecting a reviewer's approved historical window for a research
ideas view. Ask the reviewer how the effect should appear and how users
override it. A preference in weeks/months/years specifies interest; it does
not request an unvalidated forecast horizon. An optional invite on Dashboard
and a link from Settings already cover entry. Any historical-volatility filter
needs an agreed metric, history requirement, units and handling for sparse data.

### ML increment: validate one question, then wire one approved output

1. Ask Noah and Vlad to approve resuming research. Review the saved continuous
   target/ranking evidence from `research/next-session-targets`. Start with a
   bounded check of rank concentration, turnover, timing, folds and simple
   baselines. Choose one question and one horizon up front. Keep the protected
   evaluation and final test sealed until the experiment and promotion rules
   call for them. A longer horizon is a new target requiring its own evidence.
2. If an output qualifies, register a reviewed artifact and run inference out
   of band on data with an explicit cutoff. Review feature parity, minimum
   history, eligible universe and publication after finalized daily bars.
   Design a proposed Alembic migration and idempotent write path for immutable
   forecasts and separate realized outcomes. Key them by ticker, target,
   horizon, as-of session and model version, and record the data snapshot and
   publication time. Expose predictions only when the stored records satisfy
   the approved contract. See [ML product plan](ML_PRODUCT_INTEGRATION_PLAN.md)
   and [signal specification](FRONTEND_ML_INTEGRATION_SPEC.md).
3. Connect the existing typed signal adapter and Analysis/Predictions/Compare
   views to those stored results. Keep unavailable and stale states. Add a
   ticker picker on Predictions only if the approved flow calls for a standalone
   browsing page. Use Model performance for the model version, evaluated dates,
   target/horizon, coverage, baselines and out-of-sample metrics with limitations.
   Keep probability null unless supported by calibration evidence. Provide a
   match reason and context when combining an approved rank with user sector
   interests. Keep personal preferences out of model training.

If no candidate passes, the Explore and comparison release remains usable and
the current signal availability response stays in place.
