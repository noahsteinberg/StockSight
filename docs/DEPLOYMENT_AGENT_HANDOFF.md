# StockSight deployment handoff for Noah's agent

Prepared November 16, 2026. Task: deploy the existing frontend and backend to
Vercel, connect automatic production updates from GitHub main, and verify the
application. Do the implementation and verification autonomously within the
owner's authorized accounts. Ask the human only for missing account authorization
or private credential entry that connected tools cannot supply safely.

## Start here

Repository: https://github.com/noahsteinberg/StockSight

Fetch and inspect current `main` before doing anything. Deployment implementation
is already published in `1d620e2`; `2db40a9` records initial account blockers.
This handoff and a configurable production smoke workflow follow those commits.
Use the latest main, not an older frontend branch. Preserve unrelated local work.
Read `AGENTS.md`, `docs/CURRENT_HANDOFF.md`, `docs/VERCEL.md`,
`docs/SUPABASE.md` and `docs/SESSION_HANDOFF.md`.

Do not rebuild the app or change its authentication provider. React/Vite,
FastAPI, SQLAlchemy/Alembic, Supabase PostgreSQL and Auth0 already have integration
code. The incomplete ML pages must remain explicitly unavailable.

## Ownership decision — resolve before creating infrastructure

Gavin created this project using his connected Vercel account:

- Team: CSE4095, slug `cse-4095`, ID `team_RxG2798XIR3wFICeCXQgb1tT`.
- Project: `stocksight`, ID `prj_QbMykxRMshWfu6QGZGN4nJeD3yTG`.
- Reserved domain: `https://stocksight-cse4095.vercel.app`.
- Node 24.x; six public production settings have been saved.
- No deployment has been verified. No Supabase secret was saved there.

Gavin cannot invite Noah on his current free plan. The repository belongs to
Noah's personal GitHub account. Vercel requires the owner to connect a personal
repository; adding Gavin as a GitHub collaborator does not resolve this.

**Default supported route:** use Noah's authenticated Vercel account and import
Noah's repository into his own project. Noah does not need membership in Gavin's
Vercel project for this route. Verify the actual account/team first. If connected
tools cannot authorize the GitHub app, have Noah install/authorize it for
`noahsteinberg/StockSight`; this account authorization cannot be completed by
editing repository code.

Do not assume Gavin's project IDs or reserved domain belong to Noah's account.
Do not delete, transfer or detach Gavin's project/domain. Choose an available
production domain on Noah's project and record its exact origin. A domain move
requires separate coordination with Gavin; it is not needed to deploy on a new
Vercel-provided domain. Do not upgrade plans or incur charges without approval.

If the owners instead arrange supported access to Gavin's existing project,
reuse it and its reserved origin. Do not promise that merely authorizing the
GitHub app makes a collaborator able to connect this personal repository.

Hobby deployment author/collaboration restrictions may affect teammates' pushes.
Verify the actual account policy and test it. Do not strip Git metadata, forge
authors or change repository ownership to bypass a deployment restriction.
For a classroom release, Noah can own/review/merge the release under the supported
workflow; document any limits instead of promising every author's push deploys.

## Existing deployment code

- Root `vercel.json`: two Vercel Services, frontend and backend, one public origin.
- Frontend root `frontend`, Vite, `npm ci`, `npm run build`, output `dist`.
- Backend root `backend`, FastAPI, entrypoint `vercel_app:app`.
- `/api/*`, `/docs/*`, `/openapi.json` route to the backend without stripping paths.
- Hash-based frontend pages need no server router.
- `backend/vercel_app.py` ignores local env files and requires an explicit database,
  HTTPS origin and Auth0 settings. It never migrates, seeds or imports at startup.
- `.vercelignore` excludes local secrets, datasets, environments and test artifacts.
- `.github/workflows/ci.yml`: frontend, backend/disposable PostgreSQL and browser checks.
- `.github/workflows/deployment-check.yml`: public read-only smoke after successful
  Production deployment status, plus manual dispatch. Uses repository variable
  `PRODUCTION_URL`, with Gavin's reserved domain as the default.
- `scripts/check_deployment.py`: frontend HTML, readiness/database mode, stock
  search, price/indicator alignment, guest session, unauthorized watchlist and
  invalid-range checks. Uses only Python's standard library.

Vercel Services is beta. Verify support on the actual account and inspect builds.
Keep Project Root Directory at the repository root. The service-specific build
settings live in vercel.json; do not override the whole project to frontend-only.

## Configure the chosen production origin

Let APP_ORIGIN be the exact canonical HTTPS origin, without trailing slash.
These settings belong in the chosen Vercel project's **Production** environment:

| Key | Value |
| --- | --- |
| `STOCKSIGHT_DATABASE_URL` | Secret Supabase transaction-pooler URL, port 6543 |
| `STOCKSIGHT_APP_ORIGIN` | APP_ORIGIN |
| `STOCKSIGHT_AUTH0_DOMAIN` | `dev-uz71oip7v88hdtsp.us.auth0.com` |
| `STOCKSIGHT_AUTH0_AUDIENCE` | `https://stocksight-api` |
| `VITE_AUTH0_DOMAIN` | `dev-uz71oip7v88hdtsp.us.auth0.com` |
| `VITE_AUTH0_CLIENT_ID` | `DsEQAk55JjH1R67jZ58IrVDWjlV1ALuE` |
| `VITE_AUTH0_AUDIENCE` | `https://stocksight-api` |

Auth0 values above are existing public SPA configuration, not passwords/client
secrets. Preserve the existing tenant, application, users and delegated API grant.

Parth previously verified the actual hosted Supabase backend connection. Obtain
the private connection through the team's authorized secret channel or let its
holder enter it directly in Vercel. It is not committed in Git and is not present
in Gavin's existing Vercel project. Do not ask for a password/URL in agent chat,
print it, put it in a `VITE_*` variable, or copy it into a document.
Use the actual dashboard-provided pooler URL; do not invent its host/user details.

Gavin confirmed on November 16 that he added
`https://stocksight-cse4095.vercel.app` to all three existing Auth0 application
fields: Allowed Callback URLs, Allowed Logout URLs, and Allowed Web Origins.
If APP_ORIGIN differs, add APP_ORIGIN to those same three fields, preserving
the existing production/local entries. Do not use wildcard callback URLs.
Frontend redirect URI is the root origin. No `/callback` route is required.

Set repository Actions variable `PRODUCTION_URL` to APP_ORIGIN, so smoke tests
target the chosen deployment. Update the runbook's canonical origin too if needed.

## Preserve the existing database

Supabase acceptance reported schema head `0005_backend_only_access`, seven
RLS-protected tables, and only the explicitly selected 506-bar AAPL historical
fixture (2015-02-17 through 2017-02-16). It did not import the large team snapshot.
Gavin's local database separately contains 494 series and 2,947,701 accepted bars
through 2026-11-12. Do not conflate these databases or call either feed live.

Verify hosted readiness/schema/data read-only. Do not run app.seed, reset tables,
reimport the snapshot, delete volumes or run reset-capable tests against Supabase.
If migrations are actually missing, review the required changes and use the
separate direct/session migration connection (port 5432); never downgrade the
hosted database. The browser must never receive the database credential.

## Automatic updates and GitHub Actions

Use Vercel's native Git integration as the deployment mechanism. Connect the
chosen project to `noahsteinberg/StockSight`, production branch `main`. This
builds frontend/backend together on supported main pushes without a GitHub
Actions VERCEL_TOKEN. Avoid introducing a second competing deployment workflow.
Configure separate preview data/auth/origins before promising working previews.

Actions workflows are already present; they test source and verify deployments.
They do not themselves deploy, gate native promotion, or automatically roll back.
Use PR review/CI before merges. If release-gating is required, configure supported
deployment checks explicitly and verify them; do not claim a gate from YAML alone.

**Existing account blocker:** GitHub Actions run
https://github.com/noahsteinberg/StockSight/actions/runs/44008087297
refused all jobs before executing any steps. GitHub's annotation said the account
is locked due to a billing issue. Noah must resolve the account restriction through
GitHub; code edits, another workflow, reruns or Vercel authorization cannot fix it.
Do not pay/upgrade/change billing on Noah's behalf without authorization.
Native Vercel deployment is a separate mechanism, so investigate it independently.

After the restriction is resolved, rerun CI for the actual release commit and
manually run Check live deployment if no deployment event has arrived yet.
Verify a later supported main push creates a new Vercel deployment with that SHA.

## Acceptance — complete the work rather than just offering commands

1. Run relevant local checks; backend results already recorded were 92 passing,
   two PG-only skips. These are dated local results, not hosted CI acceptance.
2. Deploy the selected project and wait for READY. Inspect build logs on failure
   and fix configuration/package issues within scope. Never infer success from
   a created project or queued build.
3. Run `python scripts/check_deployment.py APP_ORIGIN`; require storage database.
4. In the real browser, load Analysis, search AAPL, change ranges, toggle SMA20
   and RSI14, inspect source/as-of labels, and check frontend requests hit same-origin API.
5. With the user entering credentials, verify Auth0 login, save/open/remove,
   refresh persistence and logout. Test two-user ownership separately. Do not
   collect passwords or capture account identifiers/tokens in artifacts.
6. Observe a subsequent authorized main push deploying automatically, check the
   matching commit in Vercel, then repeat public smoke checks. Check Actions after
   billing is restored; distinguish unavailable runners from failing tests.
7. Commit/push any final URL/runbook/workflow fixes. Report actual URL, project,
   release SHA, public/authenticated/CI results and any specific remaining blocker.

Do not claim ML forecasts, evaluated accuracy, provider refresh or complete MVP.
Do not claim account acceptance from public smoke checks alone.

## Official references

- https://vercel.com/docs/git/vercel-for-github
- https://vercel.com/docs/deployments/troubleshoot-project-collaboration
- https://vercel.com/docs/services
- https://vercel.com/docs/services/config-reference

## Copy-paste prompt for Noah

> Deploy StockSight from the latest main. Read AGENTS.md and
> docs/DEPLOYMENT_AGENT_HANDOFF.md first, then complete its deployment and
> acceptance steps in my authorized accounts. The implementation is already in
> the repo. Use my Vercel account for my personal GitHub repository if Gavin's
> free project cannot be shared. Choose and record the actual production origin,
> configure the existing Auth0 app for it, preserve Supabase data, set the
> PRODUCTION_URL GitHub variable, and verify automatic main deployments. Ask me
> only for required private credential entry/account authorization. Diagnose the
> recorded GitHub Actions billing lock separately; do not change billing or plans
> without approval. Return the working URL and evidence, not just a setup plan.
