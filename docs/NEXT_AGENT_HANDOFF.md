# StockSight — next AI/team handoff

Updated November 17, 2026, America/New_York. Noah requested documentation,
publication and then a stop. ML is explicitly paused. Do not start implementation
or research from this document alone; wait for the next user's task.

## Start here

1. ../AGENTS.md and CURRENT_HANDOFF.md: existing coding/data/auth contracts.
2. FRONTEND_ML_INTEGRATION_SPEC.md: detailed pages, visual tokens, feature wording,
   example responses, adapter/hook behavior, states, connections and acceptance.
3. ML_PRODUCT_INTEGRATION_PLAN.md: artifact, persistence and operations design.
4. ../ml/docs/RESEARCH_STATUS_HANDOFF.md and NEXT_SESSION_TARGET_ROUND_REVIEW.md:
   experiments, findings, input locations, limitations and paused next steps.
5. handoff-issues/README.md: six ready issue drafts and prefilled creation links.
6. API.md, ARCHITECTURE.md, APP_VIEWS.md, SESSION_HANDOFF.md, SUPABASE.md,
   VERCEL.md and LOCAL_START.md for the layer being changed.

The new specification supersedes conflicting old proposed endpoints and the old
click-to-generate idea. Preserve implemented prices/indicators/account/session
contracts and current UI. Older roadmap ownership is coordination, not a reason
to override Noah's current role or reassign teammates.

## Current application and deployment

Repository: https://github.com/noahsteinberg/StockSight; production branch main.
Live URL: https://stocksight-rose.vercel.app.
React/Vite/plain CSS, hash navigation, UConn colors, stock search/chart, SMA20/RSI14,
FastAPI/SQLAlchemy/Alembic, Auth0 app sessions and private watchlists exist.
Predictions/Performance remain unavailable. No ML serving, persisted predictions/
outcomes, approved artifact or automated provider refresh exists.

Active Vercel stocksight project: prj_RjOsm0SDpprpf9iOWOA5NIfrAhtq, Noah's team
team_5tJ25Ir3aeN4EZ734n78riyE. Old project IDs and Gavin's reserved domain are
historical, not active deployment targets. Seven Production variables are present;
never retrieve/print secrets. Noah reports updating the exact rose app origin.

a2cece2 fixed skipped Python dependencies using backend/pyproject.toml; five
focused startup/manifest tests and pip check passed. f433229 recorded production
acceptance and corrected smoke-check default URL. Both main pushes automatically
created READY deployments. Last observed pre-handoff release: f433229,
deployment dpl_343QFtwsaD8H5apAnVeRqKHCQrkd. Public smoke passed HTML, health,
database readiness, AAPL prices/indicators, guest sessions and private-route
rejection. Noah reports UI looks fine and Auth0 settings are now fixed. Record
Auth0 as user-reported until save/refresh/logout and two-account ownership tests
have hosted evidence. Browser automation was unavailable. No current hosted CI
pass or release gate was verified; the old billing lock is dated evidence only.
If repository PRODUCTION_URL is set it must match rose; it overrides YAML fallback.

## Supabase

Stock Sight project rgvyrcpdgycczjsqwhad, us-east-1, active healthy, Parth's org
zfmsnepyvlpkwpmksptp. Noah's plugin now sees it. Read-only inspection found role
postgres, read-only settings off, public CREATE and read/write privileges on
all seven existing tables. No test writes were performed.
Known Alembic head is 0005_backend_only_access; inspect actual head before adding
the next revision. Preserve backend-only/RLS access and existing tables.
Hosted sample is one AAPL series, 506 bars ending 2017-02-16; it is not live data.
The local 494-stock snapshot was not transferred to Supabase.
Noah reset the database password and entered the URL directly in Vercel.
Teammates must update private local connections. Credentials are not in Git/chat.
No hosted seed/reset/reimport or destructive test is authorized by this handoff.

## ML and next implementation slice

No absolute-direction candidate qualified. Excess-return HGB shows weak positive
ranking in six training folds and improved extreme-decile spread vs original
HGB; overall rank IC is similar and decays later. There is no approved confidence,
profit or live-model claim. Research is PAUSED; next saved-prediction checks are
concentration/turnover/publication timing, not more model families.

Only when asked, start a small AAPL foundation from latest main: versioned schema,
honest unavailable GET endpoint, frontend adapter/cancellable hook and tests in
existing Predictions styling. No fake production forecasts, training endpoint,
learned risk claim or schema migration is needed for this first increment.
Persistence, hosted refresh and model serving are separate gated issues.

## Git and merge instructions

This curated documentation handoff is published directly to main; no immediate
merge is needed for it. Deployment fixes are already on main. Completed local
research/planning branch tips are published as archives. DO NOT merge their old
app code wholesale into current main. Later use a focused PR for selected research
modules only. Main includes frozen summaries/JSON so another AI can understand
the research without switching the application to an old checkout.

Fetch and inspect status before work. Preserve unrelated checkouts. Course root:
C:\Users\noahs\OneDrive - University of Connecticut\Fall26\CSE4095.
Primary StockSight-fresh remains on plan/next-session-direction. Main worktree
StockSight/.worktrees/main-latest may lag remote until safely fast-forwarded.
Documentation worktree: StockSight/.worktrees/integration-research-handoff.
Research paths and ignored transfer requirements are in the ML handoff.
Datasets/checkpoints, environments and secrets intentionally remain unpushed.

## Issues limitation and stop

Connected GitHub issue creation returned 403 Resource not accessible by integration.
No issues were created. Full bodies and prefilled creation links are preserved
under handoff-issues. A human can submit them or a later Issues-write-enabled
connection can publish them. Existing open #1/#2 concern earlier frontend work;
review instead of closing/reassigning automatically. Git pushes are working;
the issue permission error is separate. No ongoing training or subagents remain.
