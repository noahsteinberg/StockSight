# Vercel deployment

The production app is [StockSight](https://stocksight-rose.vercel.app), on the
Vercel project owned by Noah. The [current handoff](CURRENT_HANDOFF.md) records
the last observed release and acceptance status. Use the existing project for
updates.

## Project

`vercel.json` builds Vite from `frontend` and FastAPI from `backend` in the same
deployment. `/api/*`, `/docs/*`, and `/openapi.json` reach FastAPI with their
original paths. Other requests reach the static frontend. The current app uses
hash routes, so dashboard/analysis refresh needs no server-side router.

The backend entrypoint `vercel_app:app` uses only environment variables, refuses
to start without a database, HTTPS app origin and Auth0 settings, and never
migrates/imports/seeds on startup. Local `app.main:app` and explicit demo startup
remain available as documented in LOCAL_START.md.

## Production settings

The backend runtime dependencies are declared in `backend/pyproject.toml` for
Vercel's Python build and mirrored in `backend/requirements.txt` for local/CI
installation. Keep both lists synchronized. A tool-only pyproject takes precedence
over requirements.txt on this deployment path and can produce a READY build whose
function crashes at import with a missing dependency. The manifest parity test
guards that boundary; build success alone is not runtime acceptance.

In the Vercel project's Environment Variables, set these for **Production**:

| Setting | Value / source |
| --- | --- |
| `STOCKSIGHT_DATABASE_URL` | Supabase transaction pooler URL on port 6543; store as a secret |
| `STOCKSIGHT_APP_ORIGIN` | `https://stocksight-rose.vercel.app` |
| `STOCKSIGHT_AUTH0_DOMAIN` | Existing Auth0 tenant hostname |
| `STOCKSIGHT_AUTH0_AUDIENCE` | Existing StockSight API identifier |
| `VITE_AUTH0_DOMAIN` | Same existing Auth0 tenant hostname |
| `VITE_AUTH0_CLIENT_ID` | Existing SPA's public client ID |
| `VITE_AUTH0_AUDIENCE` | Same existing StockSight API identifier |
| `VITE_AUTH0_DATABASE_CONNECTION` | Existing Auth0 database connection if it differs from the default |

No database password or Auth0 client secret belongs in `VITE_*`, Git, workflow
artifacts or frontend code. Existing private local settings do not travel with
Git. The local database contains the complete accepted team snapshot; hosted
coverage and its explicit retention limit are recorded in the
[current handoff](CURRENT_HANDOFF.md). Connecting Supabase alone does not transfer
data or implement market-data refresh. The hosted import is a separate,
deliberately authorized operation.

Use the exact HTTPS origin in Auth0 and preserve local entries. Set the dedicated
verification fallback URL using the [account guide](ACCOUNTS.md#auth0-tenant-setup).

Migrations use a separate direct/session pooler URL on port 5432, as documented
in [Supabase setup](SUPABASE.md). Hosted head is `0006_market_refresh` after the
November 23 coordinated release; verify the current version and existing data;
do not run seeds, imports or destructive tests against the hosted database.

## Automatic deployment and GitHub Actions

The existing Vercel Git integration deploys from the repository root on pushes
to main. Feature-branch deployments are disabled in vercel.json. Native Vercel
deployment requires no CLI token in GitHub Actions.

- ci.yml runs lint, tests, builds and browser checks using disposable services.
- deployment-check.yml runs a read-only smoke check on successful Production
  deployment events and can also be dispatched manually. If set, the GitHub
  repository variable PRODUCTION_URL must match the canonical production URL.
  The workflow defaults to the rose domain.

Review CI on the PR before merging. GitHub Actions and the post-deployment
smoke workflow run independently of native Vercel deployment.

## Acceptance

From the repository root:

```sh
python scripts/check_deployment.py https://stocksight-rose.vercel.app
```

Smoke checks frontend delivery, database readiness, public stock data,
indicator snapshot/date agreement, guest sessions and private-route protection.
Confirm Vercel published the intended commit and inspect hosted Actions status.
Run authenticated acceptance separately using the
[account checklist](ACCOUNTS.md#verification).

For rollback, select the previous known-good production deployment in Vercel
and repeat the smoke check. Vercel rollback can affect automatic production
domain assignment. Application rollback does not revert database migrations.
