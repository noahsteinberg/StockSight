# Deployment

The Vercel project `stocksight` exists in the CSE4095 team. Its reserved production
origin is `https://stocksight-cse4095.vercel.app`. The repository now contains
configuration to deploy React/Vite and FastAPI together, with same-origin `/api`
routing and GitHub Actions CI/post-deployment checks.

See [VERCEL.md](VERCEL.md) for exact project settings, production secrets,
GitHub installation, automatic updates, Auth0 URLs, smoke checks and rollback.
Infrastructure preparation is not proof of a working deployment: GitHub access,
the hosted Supabase secret, Auth0 production configuration and live acceptance
must be verified before calling the app deployed.

The hosted database must already be migrated through `0005_backend_only_access`.
Runtime never migrates, imports or seeds. The production entrypoint refuses
missing database/HTTPS-origin/Auth0 settings instead of silently serving fixture
data. Credentials stay in Vercel secrets. Preserve a working local demo.

Before declaring the account flow accepted, verify Secure/HttpOnly cookies,
refresh restoration, watchlist persistence, logout and two-account isolation on
the actual production origin. Public smoke tests establish public API/data
integration only. Password reset/account-disable session revocation, data usage
rights, adjustment/calendar conventions and second-machine acceptance remain
separate follow-up items documented in CURRENT_HANDOFF.md.

ML training/inference, forecasts/outcomes, evaluation and automatic market-data
refresh remain unfinished independently of deployment.
