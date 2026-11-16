# Auth0 accounts and watchlist foundation

**Current session behavior:** [SESSION_HANDOFF.md](SESSION_HANDOFF.md) records the
refresh fix, cookie/CSRF contract, username signup with optional recovery email,
and real two-account verification. It supersedes earlier refresh limitations below.

This increment implements the account UI, Auth0 SDK integration, validated private
API routes and PostgreSQL watchlists. Noah can continue from the existing React
components and the OpenAPI contract. SMA20/RSI14 backend is now implemented (INDICATORS.md); indicator UI and ML
remain separate work. CURRENT_HANDOFF.md is the current continuation entry point.

Real Auth0 authorization/sign-in and private-watchlist persistence were verified
after tenant setup on November 16. The user completed hosted authentication;
no password was collected by the agent. Automated tests separately use signed
test identities in an isolated harness. No test identity endpoint is mounted by
app.main. Additional hosted account-lifecycle checks remain below.

## Auth0 setup for another environment

The development tenant is already configured. These are reproduction steps, not
an instruction to replace the tenant/connection or recreate existing users.
User-Delegated Access and username signup with optional recovery email are enabled;
see SESSION_HANDOFF.md for the preserved existing-account behavior.

1. Create an Auth0 tenant, then create an application named StockSight with type
   **Single Page Application**. Use Universal Login with a database connection
   enabled for that application and self-service signup allowed.
2. In the application's Settings, set all three fields below to
   `http://127.0.0.1:5173`:
   - Allowed Callback URLs
   - Allowed Logout URLs
   - Allowed Web Origins
3. Under Applications → APIs, create **StockSight API**, identifier
   `https://stocksight-api`, signing algorithm **RS256**. The identifier is a
   logical audience; it does not need to be a hosted URL.
4. Open that API's **Application Access** tab. Edit the StockSight SPA and enable
   **User-Delegated Access**, then save. When using per-app authorization, the SPA
   needs this explicit grant before Auth0 will issue a token for this audience.
   Client/Machine-to-Machine access is not needed for this user-login flow.
5. Set the API's access-token expiration and browser-flow expiration to 300
   seconds for this demo. No Management API access or client secret is needed.
6. Supply these three public values: tenant **Domain**, application **Client ID**,
   and API **Identifier**. Do not send a password, client secret or bearer token.

Use exactly the same hostname when opening the app and configuring callbacks.
If using localhost instead, explicitly register its URLs as well. Add exact HTTPS
production origins when deploying; do not use wildcard callbacks. Auth0 permits
local development exceptions, but deployment requires HTTPS.

Official references: [Auth0 React SDK](https://github.com/auth0/auth0-react),
[SPA SDK configuration](https://github.com/auth0/auth0-spa-js),
[token best practices](https://auth0.com/docs/secure/tokens/token-best-practices),
and [PyJWT validation](https://pyjwt.readthedocs.io/en/stable/usage.html).
API grant configuration follows Auth0's
[application access policy guide](https://auth0.com/blog/developers-guide-api-access-policies-auth0/).

If Auth0 returns `Client ... is not authorized to access resource server ...`,
check step 4 and the API's user-access policy. Keep per-app authorization and grant
the StockSight SPA user access rather than broadening access for every application.

## Local configuration and startup

Implementation branch: `feature/auth0-watchlists` in the current worktree. Use a
checkout containing migration 0004 for startup and Alembic commands: the shared
local development database has already been upgraded to that revision.

Copy frontend/.env.example to ignored frontend/.env.local and set:

```dotenv
VITE_AUTH0_DOMAIN=YOUR_TENANT.auth0.com
VITE_AUTH0_CLIENT_ID=YOUR_SPA_CLIENT_ID
VITE_AUTH0_AUDIENCE=https://stocksight-api
```

Add to ignored backend/.env, preserving the existing database URL:

```dotenv
STOCKSIGHT_AUTH0_DOMAIN=YOUR_TENANT.auth0.com
STOCKSIGHT_AUTH0_AUDIENCE=https://stocksight-api
```

Use the actual lowercase tenant hostname without https://, a path or a port.
VITE_* settings are public browser configuration; never put a secret there.
FastAPI reads backend/.env; Vite reads frontend/.env.local. Both processes need
restarting after configuration changes.

From backend, using its virtual environment:

```powershell
.\.venv\Scripts\python.exe -m app.environment_check --require-docker
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.doctor
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

From frontend, use `npm ci` then `npm run dev`. See LOCAL_START.md for Docker
startup and execution access. Migration 0003 adds only identity/watchlist tables;
it does not reimport or replace the market snapshot. Do not run app.seed over
that snapshot. No seeding occurs during normal application startup.

With Auth0 unset, public stock analysis still works; the UI reports that sign-in
is being set up. Protected endpoints fail closed. Missing account tables make
database readiness fail until migrations are applied.

## API contract

Signup/login/logout use Auth0 Universal Login through the official React SDK;
there are no local password endpoints. A valid API access token bootstraps the
first-party session. Normal frontend private calls use the HttpOnly cookie plus
CSRF/expected-user headers through authorizedFetch. Bearer callers remain
supported. An ID token is not an API credential. OpenAPI advertises both schemes;
SESSION_HANDOFF.md owns session creation/restoration/logout details.

| Method and path | Request | Success |
| --- | --- | --- |
| GET /api/me | App session or bearer token | 200 `{ "id": "local-user-uuid" }` |
| GET /api/watchlist | App session or bearer token | 200 `{ "items": [{ "symbol": "AAPL", "name": "Apple Inc.", "added_at": "ISO-UTC" }], "limit": 100 }` |
| POST /api/watchlist | App session or bearer token; JSON `{ "symbol": "AAPL" }` | 201 saved item; 200 same item on repeat |
| DELETE /api/watchlist/{symbol} | App session or bearer token | 204; repeated removal also 204 |

Symbols are trimmed/uppercased and validated. A saved symbol must have a
canonical series in storage. Lists are bounded to 100 entries per account,
ordered by newest save then symbol. Duplicate saves preserve added_at, including
at capacity. PostgreSQL serializes saves per account to enforce capacity and
duplicate semantics under concurrent requests. Private responses use no-store.

The owner always comes from verified issuer + subject, mapped to a local UUID.
There is no caller-supplied owner field; extra POST fields are rejected. Removing
a symbol affects only the current user's entry, even if another user has saved
the same symbol. Display names come from Auth0 in the UI; local identity storage
does not copy email, profile or passwords.

Errors retain `{ "detail": { "code": "...", "message": "..." } }`, except
FastAPI's standard 422 validation structure:

- 401 UNAUTHENTICATED: absent, invalid, expired, wrong-issuer/audience or non-user
  token; includes WWW-Authenticate: Bearer.
- 404 UNSUPPORTED_SYMBOL: no canonical stored series for an add.
- 409 WATCHLIST_FULL: 100 entries reached; remove one first.
- 422: malformed symbol/body or unexpected owner fields.
- 503 AUTH_NOT_CONFIGURED / AUTH_UNAVAILABLE / ACCOUNT_STORAGE_UNAVAILABLE:
  configuration, key retrieval or storage unavailable. No fixture fallback and
  no raw credentials/driver errors.

## Authentication decisions and limitations

- The SDK handles Authorization Code + PKCE, state and redirect processing.
  Create account uses screen_hint=signup. It handles local-cache cleanup and
  Auth0 logout; app passwords and custom cryptography are not implemented.
- The API pins RS256 and validates signature, issuer, audience, exp, iat and sub
  (plus nbf when supplied), with 10 seconds of clock tolerance. Client-credentials
  identities are rejected. JWKS comes only from the configured HTTPS issuer,
  never token-provided URLs; retrieval has a timeout and bounded cache.
- Access tokens stay in SDK memory. An opaque, HttpOnly first-party app session
  now restores login after refresh. No Auth0 token is persisted in browser storage
  or the database. See SESSION_HANDOFF.md for the cookie and CSRF contract.
- Logout clears the local login and Auth0 session, but an already copied access
  JWT can remain valid until expiration. The proposed 300-second lifetime limits
  that window. Immediate server-side revocation is not implemented; do not claim
  that logout invalidates every previously issued bearer token.
- Private APIs now accept either a verified bearer token or the app session.
  Cookie-authenticated writes require an exact Origin and CSRF token. Vite proxies
  /api; production must provide same-origin routing. No permissive CORS was added.
- Auth0 owns password policies, duplicate signup, recovery, email delivery and
  identity-provider controls. Verify these in the configured tenant before a
  public release; local signed-token tests cannot prove hosted behavior.

## Frontend handoff

- AuthProvider.jsx wraps the official SDK and exposes a small account context.
- AccountControls.jsx provides signup/sign-in/sign-out and current-user display.
- use-watchlist.js owns authorized requests, cancellation, retry and mutations.
  Returned state is keyed to the current subject so logout/user changes hide
  another user's list immediately.
- Watchlist.jsx is the personal dashboard: signed-out/empty/loading/error states,
  open-stock navigation and removal. App.jsx owns the selected stock; Analysis.jsx
  supports saving and opening saved stocks without introducing a second chart.
- The existing paper/ink design, chart contracts, range controls and fixture demo
  remain. Company names absent from the market snapshot still display tickers.

## Verification commands and remaining live acceptance

Backend: run pytest with a unique backend/.pytest_cache subdirectory as basetemp;
set STOCKSIGHT_TEST_DATABASE_URL only to a disposable PostgreSQL _test database
to include PostgreSQL cases. These tests migrate and downgrade their own tables.

Frontend:

```powershell
npm run lint
npm run build
npm run test:e2e
npm run test:e2e:accounts
```

The account browser suite uses separate ports 5175/5176/8102. Most UI scenarios
use a test-only Auth0 SDK boundary and real signed JWTs/API/storage. Separate
scenarios use the actual SDK to check signup audience/PKCE and invalid callback
handling. Hosted credentials and successful OAuth code exchange are not tested.
Set STOCKSIGHT_E2E_ACCOUNTS_DATABASE_URL to a separate disposable PostgreSQL
_test database for browser/database coverage; absent that, it explicitly creates
a disposable SQLite file. Never use the normal development database.

The fixture is restricted to `vite serve --mode e2e-accounts`; production builds
in that mode fail. Its token issuer is in backend/tests/e2e_accounts_app.py only.
Neither app.main nor app.demo exposes /api/test/identity. Screenshots, video and
tracing are off in the account suite unless a one-off visual check is explicitly
requested with STOCKSIGHT_VISUAL_QA=1.

Current real-tenant results are in SESSION_HANDOFF.md: signup/login/logout,
refresh persistence, removal, two-user isolation, negative signup requests and
recovery email delivery are verified. A full password change and production
provider-revocation policy remain separate acceptance work; no real password was
changed by the agent. The earlier evidence below is retained as history.

## Local verification November 16, 2026

- 68 backend tests passed with PostgreSQL enabled. One SQLite-only invocation of
  the PostgreSQL concurrency scenario was skipped; the PostgreSQL invocation
  passed, including 12 concurrent duplicate adds yielding one new entry.
- An additional focused check confirmed configured authentication with missing
  or unmigrated storage returns a controlled 503. Production exposes no test
  identity issuer endpoint.
- 11 existing chart browser tests and 7 account browser tests passed against
  disposable PostgreSQL. The latter include real-SDK PKCE signup initiation and
  invalid-callback handling, alongside the explicit test identity harness.
- Backend Ruff lint/format and frontend lint/build passed. One headless mobile
  layout image was inspected; continuous capture was not enabled.
- Migration 0003 was applied to the existing local development database. All
  2,947,701 market rows, 494 series and every source hash were unchanged; there
  was no schema drift. No accounts or watchlist entries were fabricated there.
- A temporary normal app.main HTTP server reported database readiness, returned
  exact ticker T first, rejected unauthenticated private requests and returned
  404 for /api/test/identity. That verification server was stopped afterward.

Ignored evidence: .local-data/auth-foundation-verification.json,
.local-data/account-development-migration.json and corresponding command logs.
The remaining hosted lifecycle checks above are not replaced by these results.

## Earlier live Auth0 continuation (November 16, 2026)

Historical pre-session-fix evidence: the refresh limitation described in this
section is resolved by the later app-session implementation in SESSION_HANDOFF.md.
Do not reintroduce persistent Auth0 token caching to address it.

- Loaded Gavin's supplied public domain/client ID/audience into ignored local
  environment files. The database URL was preserved. Tenant OpenID discovery and
  RSA JWKS retrieval succeeded over verified HTTPS.
- The initial live request was rejected because the SPA lacked a user-delegated
  API grant. Gavin enabled it in the Auth0 dashboard; the real hosted signup page
  then opened successfully. The setup steps above now include that grant.
- The user completed hosted authentication manually and returned to StockSight.
  The real access-token-protected watchlist loaded, and saving AAPL succeeded.
- A browser refresh did not silently restore the local Auth0 session. Interactive
  sign-in required the hosted consent page again. After reauthentication, the
  same saved AAPL entry was retrieved. Persistence is verified; seamless silent
  session restoration is not verified in this local browser setup. Tokens remain
  in SDK memory under the existing design; no persistent token cache was added.
- Changed the analysis view to MSFT, then opened saved AAPL from the dashboard.
  The ticker and chart returned to AAPL correctly. The AAPL entry was left saved.
- The regular API and frontend are running on ports 8000/5173 from this worktree.
  No source-data import or replacement was performed during this continuation.

No passwords, bearer tokens, callback codes, emails or Auth0 session state are
included in Git or the local acceptance report. This is evidence of one real
Auth0 user flow, not a claim that every hosted lifecycle scenario has passed.
