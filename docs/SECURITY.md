# Security foundation

Public chart routes read stored historical data. Auth0 validates account identity;
private watchlist routes enforce ownership in database queries. Development binds
to loopback. See AUTH0_WATCHLIST_HANDOFF.md for token handling, setup and the
remaining hosted-authentication acceptance gate.

- Keep local `.env` files out of Git; `.env.example` contains safe examples only. Use deployment secret storage later.
- Never log connection strings, tokens, passwords, or authorization headers. Browser `VITE_*` values are public.
- Review dependency updates and lockfile diffs; run lint, build, and tests before merging.
- Validate symbols, ranges, limits, and payload sizes when real endpoints are added. Return stable errors without exposing raw provider/database exceptions.
- Auth0 Universal Login and the official React SDK handle signup and sign-in.
  The API validates signed access tokens against a fixed issuer and audience;
  never use an ID token or an unverified subject as API authentication.
- Private APIs accept bearer tokens or an opaque HttpOnly app cookie. Cookie-based
  writes require an exact Origin and a per-session CSRF token. Keep routing
  same-origin; no broad CORS policy is enabled. See SESSION_HANDOFF.md.
- Auth0 tokens stay in SDK memory; the app cookie is backed by a hashed identifier
  in PostgreSQL with absolute expiry and immediate per-session logout revocation.
  Copied Auth0 JWTs retain their provider expiry. Out-of-band Auth0 account changes
  do not yet revoke all app sessions; apply the documented deployment policy.
- Use HTTPS in deployment. Keep training artifacts trusted and versioned; never deserialize untrusted pickle/joblib files.
- If a secret is exposed, revoke/rotate it and notify the team; deleting the file alone is insufficient.

Educational use does not remove the need to protect user data. Do not claim predictions are investment advice or guaranteed outcomes.
