# Vercel deployment and automatic updates

Prepared November 16, 2026. This is the deployment runbook; recorded acceptance
must distinguish configured infrastructure from a verified live application.

## Recorded delivery status — November 16, 2026

Deployment configuration was committed as `1d620e2` and pushed to `main`, including
the Supabase branch history. Local backend verification passed 92 tests with two
PostgreSQL-only cases skipped; Ruff lint/format passed. Frontend lint/build passed
after the Supabase merge; no frontend source changed in this deployment increment.

Vercel project/domain creation and six public production settings succeeded.
Git linking was rejected because the GitHub integration is not authorized for
`noahsteinberg/StockSight`. The production Supabase secret is not configured on
this project. Auth0 production callback/logout/origin configuration remains
unconfirmed. No successful Vercel build, live HTTP/browser acceptance or automatic
redeployment is claimed.

GitHub Actions run `44008087297` triggered on the pushed commit, but all three jobs
were refused before any steps started. GitHub's annotation was: "The job was not
started because your account is locked due to a billing issue." The repository
owner must resolve that account restriction before hosted CI/smoke jobs can run.
This is distinct from a workflow/test failure and from Vercel Git authorization.

## Project

- Team: CSE4095 (`cse-4095`).
- Project: `stocksight`, ID `prj_QbMykxRMshWfu6QGZGN4nJeD3yTG`.
- Canonical production origin: `https://stocksight-cse4095.vercel.app`.
- Repository: `noahsteinberg/StockSight`; production branch: `main`.
- Project Root Directory: repository root, not `frontend` or `backend`.
- Node: 24.x. Vercel Services is currently beta.

`vercel.json` builds Vite from `frontend` and FastAPI from `backend` in the same
deployment. `/api/*`, `/docs/*`, and `/openapi.json` reach FastAPI with their
original paths. Other requests reach the static frontend. The current app uses
hash routes, so dashboard/analysis refresh needs no server-side router.

The backend entrypoint `vercel_app:app` uses only environment variables, refuses
to start without a database, HTTPS app origin and Auth0 settings, and never
migrates/imports/seeds on startup. Local `app.main:app` and explicit demo startup
remain available as documented in LOCAL_START.md.

## Production settings

In the Vercel project's Environment Variables, set these for **Production**:

| Setting | Value / source |
| --- | --- |
| `STOCKSIGHT_DATABASE_URL` | Supabase transaction pooler URL on port 6543; store as a secret |
| `STOCKSIGHT_APP_ORIGIN` | `https://stocksight-cse4095.vercel.app` |
| `STOCKSIGHT_AUTH0_DOMAIN` | Existing Auth0 tenant hostname |
| `STOCKSIGHT_AUTH0_AUDIENCE` | Existing StockSight API identifier |
| `VITE_AUTH0_DOMAIN` | Same existing Auth0 tenant hostname |
| `VITE_AUTH0_CLIENT_ID` | Existing SPA's public client ID |
| `VITE_AUTH0_AUDIENCE` | Same existing StockSight API identifier |

No database password or Auth0 client secret belongs in `VITE_*`, Git, workflow
artifacts or frontend code. Existing private local settings do not travel with
Git. The local database currently contains the large team snapshot; Parth's
Supabase acceptance used only 506 AAPL bars ending 2017-02-16. Connecting Supabase
does not transfer the larger dataset or implement market-data refresh.

Preserve existing Auth0 localhost settings and add the canonical production
origin to Allowed Callback URLs, Allowed Logout URLs and Allowed Web Origins.
Do not use wildcard callback URLs. Keep the API's User-Delegated Access grant.

Migrations use a separate direct/session pooler URL on port 5432, as documented
in SUPABASE.md. Confirm hosted head `0005_backend_only_access` and existing data;
do not run seeds, imports or destructive tests against the hosted database.

## Automatic deployment and GitHub Actions

Connect the existing project to GitHub in Vercel Settings → Git. The GitHub owner
must install/authorize Vercel for this repository. Set the Production Branch to
`main`. Once connected, every push to `main` builds and publishes frontend and
backend together; no CLI token is needed in GitHub Actions. This uses Vercel's
native deployment integration, rather than launching a second competing build
from Actions. Feature branches can build previews after separate Preview
database/Auth0/origin settings are configured. Production settings are not
automatically copied into previews.

The GitHub Actions workflows complement this deployment:

- `ci.yml`: frontend lint/build, backend lint/tests against disposable PostgreSQL,
  and real browser/account suites, on pushes and pull requests.
- `deployment-check.yml`: read-only production smoke checks when GitHub receives
  Vercel's successful Production deployment status; also manually runnable under
  Actions → Check live deployment. Checks frontend HTML, database readiness,
  AAPL prices/indicator date alignment, guest sessions, unauthorized watchlist
  rejection and invalid-range rejection.

Native Vercel builds and CI run independently. CI and the post-deployment smoke
check do **not** currently block a production promotion or roll it back. Review
and pass CI on PRs before merging to main. A failed build keeps the previous
successful deployment; a runtime smoke failure needs investigation/rollback.
Keep the workflow files on the default branch for deployment events to trigger.

## Acceptance

Run from the repository root with Python:

```sh
python scripts/check_deployment.py https://stocksight-cse4095.vercel.app
```

Also open the HTTPS app in a browser: inspect AAPL, toggle SMA20/RSI14, change
ranges, sign in through hosted Auth0, save/open/remove a watchlist item, refresh,
and sign out. A user must enter their own credentials. Verify a second account's
isolation separately. Public smoke tests do not establish authenticated acceptance.

To prove updates are automatic, push a reviewed source change to main, observe
the matching commit in Vercel and GitHub Actions, then repeat the public checks.
Do not claim automatic deployment from a one-off uploaded source deployment.

For rollback, select the prior known-good production deployment in Vercel and
roll it back; verify production afterward. Rollback may disable automatic domain
assignment until a later deployment is explicitly promoted. Database migrations
are separate and are not reversed by a frontend/backend rollback.
