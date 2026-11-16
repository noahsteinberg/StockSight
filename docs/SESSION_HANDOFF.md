# Persistent Auth0 app sessions

Implemented November 16, 2026 on feature/auth0-watchlists. This supersedes the
earlier localhost refresh limitation in AUTH0_WATCHLIST_HANDOFF.md. The frontend
design is unchanged; its redesign is deferred at Gavin's request.

## Behavior

Auth0 still owns signup, login, password policies and recovery. After login the
React SDK exchanges a valid Auth0 access token for an opaque StockSight session.
The browser receives an HttpOnly cookie, and PostgreSQL stores its SHA256 digest,
identity reference, CSRF token, API audience and expiry. Auth0 access/refresh
tokens are not stored in PostgreSQL, localStorage or sessionStorage.

On refresh the frontend restores the app session through its own API, so Auth0's
localhost consent/third-party-cookie restrictions do not interrupt an existing
session. Restored sessions display “Your account” when an Auth0 profile is not
available in SDK memory. The API remains the authority for identity and ownership.

Sessions have an absolute eight-hour lifetime by default; ordinary requests and
refresh do not extend it. There are at most five active sessions per account.
Creating a session rotates the browser's previous session; expiry and eviction
invalidate old cookies. Expired rows are cleaned up during new session creation.

Logout revokes the current app session in PostgreSQL before asking the SDK to log
out of Auth0. A copied/replayed revoked app cookie is rejected immediately.
If Auth0 logout fails after app revocation, the UI reports that separately.
Already issued Auth0 bearer tokens retain their provider-defined expiry; app
logout does not revoke every bearer token or all other device sessions.

## API contract

| Endpoint | Authentication / request | Response |
| --- | --- | --- |
| GET /api/auth/session | Optional app cookie | 200 authenticated/user/csrf_token/expires_at, or authenticated=false |
| POST /api/auth/session | Valid Auth0 API access token and exact Origin | 200 session state and HttpOnly Set-Cookie |
| POST /api/auth/logout | App cookie, exact Origin and X-CSRF-Token | 204; expired/revoked session cleanup is idempotent |
| /api/me and /api/watchlist routes | App cookie or valid Auth0 bearer token | Existing account/watchlist contract |

The cookie is stocksight_session, host-only, HttpOnly, SameSite=Lax, Path=/api.
Secure is enabled for HTTPS deployment origins. Plain HTTP is accepted only for
loopback development. Do not log cookies, bearer headers or CSRF values.

For cookie-authenticated unsafe requests, the API requires both:

- Origin matching STOCKSIGHT_APP_ORIGIN exactly.
- X-CSRF-Token matching the synchronizer token from the current session response.

The frontend additionally sends X-Session-User with its expected local user ID.
The API rejects a mismatch with 401 rather than applying a stale tab's mutation
to another account. The frontend rechecks session identity on focus/visibility
changes. Private responses are no-store and nosniff. Bearer clients remain
supported and do not use ambient cookie authentication when an Authorization
header is supplied; an invalid explicit bearer token never falls back to a cookie.
OpenAPI advertises both supported private-route authentication methods.

The create-session endpoint requires a fresh valid bearer proof; an existing
cookie alone cannot extend or replace its own lifetime. Login/session creation
and cookie writes also require the configured Origin. Session records are bound
to the configured issuer and API audience, so changing either invalidates them.

## Configuration and migration

In ignored backend/.env:

```dotenv
STOCKSIGHT_APP_ORIGIN=http://127.0.0.1:5173
STOCKSIGHT_SESSION_MAX_AGE_SECONDS=28800
```

The lifetime is configurable from 300 to 86400 seconds. Use an exact HTTPS
frontend origin for deployment and configure that origin in Auth0's callback,
logout and web-origin settings. No client secret or persistent token cache is
needed for this session bridge. Existing Auth0 domain/audience/SPA settings remain.

Run the environment check from backend before live operations, then
`python -m alembic upgrade head`. Migration 0004_app_sessions adds one table and
its indexes. It does not modify stock data or existing watchlists. Use a checkout
containing migration 0004 with the shared development database after upgrading.

The local development database was migrated and checked for schema drift. All
2,947,701 market rows, 494 series and source hashes were preserved. The existing
identity and saved AAPL entry were retained.

## Username signup and optional recovery email

Gavin configured the existing Username-Password-Authentication connection with
Auth0 Flexible Identifiers. The live form now requires a username and password
and offers email as optional. Login accepts username or email; the original
email-based account was verified to remain usable with its existing watchlist.

For equivalent setup in another tenant, enable username as an identifier and
require it at signup, with email optional at signup and not required on profiles.
Retain email as an identifier for legacy accounts. Keep the profile-wide username
requirement off during transition if existing users lack usernames. Preserve user
IDs; do not recreate existing users or key watchlists by username/email.

Auth0 still validates passwords and username uniqueness. Recovery email is useful
but not required to create an account. Without an email/phone recovery channel,
forgotten-password recovery needs administrator assistance. Do not fabricate email
addresses for test accounts. The user enters passwords directly into hosted
Auth0 forms; no local password endpoints were introduced.

References: [Auth0 Flexible Identifiers](https://auth0.com/docs/authenticate/database-connections/activate-and-configure-attributes-for-flexible-identifiers),
[username-only support](https://support.auth0.com/center/s/article/Is-it-possible-to-create-users-using-username-and-password-instead-of-the-email-password-combination),
[OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
and [OWASP CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Verification

- Full backend run: 83 passed, one SQLite invocation of the PostgreSQL-only
  concurrency test skipped; its PostgreSQL invocation passed.
- Focused account/session security follow-up after OpenAPI annotation: 23 passed,
  one PostgreSQL-only test skipped in that SQLite-only follow-up.
- 11 chart browser tests and 9 account/session browser tests passed against
  disposable PostgreSQL. Coverage includes refresh with simulated SDK state
  removed, logout-cookie replay rejection, expiry, account switching between tabs,
  two-user isolation, and real-SDK PKCE/callback behavior.
- Backend lint/format, frontend lint/build and migration/model consistency passed.
- Real Auth0: original-account refresh retained login and AAPL; removal survived
  refresh and AAPL was restored afterward; logout kept private data hidden.
- The user created a second username account. It initially saw no stocks, then
  saved MSFT and retained it across refresh without another prompt. Returning to
  the original account showed only AAPL. Original-account refresh again succeeded.
- Two negative requests to the development tenant were rejected: missing required
  signup credentials returned 400, and the existing test username returned 400
  invalid_signup. No existing password was submitted or changed. Generic Auth0
  signup errors remain enabled rather than exposing account enumeration details.
- Gavin confirmed receipt of a recovery email. A real password change was not
  performed by the agent or independently verified; passwords and reset links
  remain private.

Ignored evidence: .local-data/app-session-verification.json,
.local-data/session-development-migration.json, .local-data/auth0-negative-signup.json
and the local real-session acceptance report. No screenshots were needed for the
live session checks. All signed-token fixtures and token-issuing endpoints remain
test-only and absent from the normal application.

## Boundaries for Noah

The account/watchlist core is locally verified; this does not complete indicators,
ML, prediction history, evaluation, hosted CI or second-machine acceptance.
Before public deployment, confirm HTTPS/origins, production Auth0 settings, mail
delivery and credential-reset acceptance, and the policy for revoking app sessions
when an Auth0 account is disabled or a password changes elsewhere. App sessions
currently remain valid until local revocation or their absolute expiry; there is
no Auth0 account-change webhook integration. A valid bearer proof can create a
new app session, which is a separate lifetime from the short-lived access token.
