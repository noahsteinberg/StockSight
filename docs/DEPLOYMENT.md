# Deployment plan and remaining gates

No deployment is claimed. Hosting, budget, domain and final demo requirements
remain undecided. [CURRENT_HANDOFF.md](CURRENT_HANDOFF.md) records the current locally
verified foundation. CI definitions test code and disposable PostgreSQL/browser
flows; they do not publish services, and a hosted run on the published head remains
an acceptance gate.

Build the frontend with `npm ci` and `npm run build`; publish `frontend/dist`
through the chosen host without committing generated files. Provide same-origin
`/api` routing to FastAPI; Vite dev/preview servers are not production hosting.
Install pinned backend runtime dependencies, run reviewed Alembic migrations
through `0004_app_sessions`, and supervise Uvicorn behind HTTPS. Keep PostgreSQL
private, provision least-privilege roles, and define backups/restore and rollback.
Never import/seed or downgrade production automatically during API startup.

Before public release:

- Configure exact HTTPS frontend Origin and Auth0 callback/logout/web origins;
  match domain/audience/public client settings and User-Delegated API access.
- Verify Secure/HttpOnly app cookies, same-origin CSRF checks, absolute expiry,
  logout revocation and cross-account isolation on the deployed URL.
- Decide and implement/accept the provider-driven session-revocation policy for
  account disable/password changes. Current app sessions last until local
  revocation or expiry; copied bearer tokens retain provider-defined expiry.
- Verify recovery delivery and a complete reset flow; receipt alone is not proof
  of a successful password change. Keep credentials entered directly by users.
- Confirm dataset usage rights, adjustment/calendar conventions and freshness;
  snapshot import is not a live provider feed.
- Verify `/api/health` and `/api/ready` plus actual public and authenticated flows;
  process logs alone do not establish service reachability or storage readiness.
- Rehearse migration/backup recovery on disposable data, second-machine setup,
  hosted CI and the professor demo. Keep a working explicitly historical local demo.

Before adding inference, define trusted artifact storage, version/checksum and
loading behavior; training stays offline. ML/forecasts/outcomes and evaluation
remain outstanding MVP work, independently of hosting.
