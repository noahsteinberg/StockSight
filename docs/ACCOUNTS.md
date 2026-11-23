# Accounts, sessions and watchlists

## Account pages

- `/#/login`, `/#/signup`, and `/#/reset-password` render the real React forms.
  Account buttons open these pages. Browser back/forward and direct links work.
- Missing public Auth0 configuration disables sign-in with an explicit message.
- Username/password goes directly to Auth0 using Auth0.js cross-origin login.
  Auth0 manages password verification, policies, abuse protection and identities.
  No StockSight password endpoint, password table or client secret is introduced.
- Signup uses Auth0's public `/dbconnections/signup` endpoint so the existing
  flexible-identifier connection can continue accepting usernames without an email.
  After account creation, the current flow directs the user to sign in.
  The optional email can be used for recovery; Auth0 owns verification requirements.
- Reset sends Auth0's recovery email. The confirmation does not identify whether
  an account exists. Accounts without recovery email may need administrator help.
- Google uses the existing official React SDK, Authorization Code + PKCE, and
  `connection=google-oauth2`; the provider consent/sign-in screens remain external.
- **Trouble signing in?** opens a hosted password sign-in option for blocked cross-site
  cookies or an interactive Auth0 challenge. It uses hosted Universal Login with
  the same database connection and Authorization Code + PKCE. Google retains its
  own connection and button.

## Session boundary

Auth0.js uses its supported `token id_token` response for cross-origin password
login (Implicit grant). It generates transaction state and nonce, then validates
the callback and the RS256 ID token. This is separate from Google's existing
Authorization Code + PKCE path. Do not substitute a Resource Owner Password grant.

On a password callback, the fragment is removed from the address bar immediately
before asynchronous processing. The verified access token goes once to
`POST /api/auth/session`. The backend independently checks its signature, issuer,
audience, expiry and user identity before issuing the existing HttpOnly cookie.
No token is persisted by the application. Auth0.js may store short-lived
state/nonce transaction metadata, not the user's password or received tokens.
React StrictMode reuses a single restoration promise so nonce transactions are
not consumed twice. Rejected callbacks cannot bootstrap an app session.

Refresh, CSRF/expected-user headers, expiry, logout revocation, cross-tab account
switching and private watchlist isolation continue through `useAccount()` and
`authorizedFetch`.

## Auth0 tenant setup

Keep the existing SPA, database connection, API audience and users. Do not recreate
them. Use the same public settings in `frontend/.env.local` or deployment variables:

```dotenv
VITE_AUTH0_DOMAIN=YOUR_TENANT.auth0.com
VITE_AUTH0_CLIENT_ID=YOUR_SPA_CLIENT_ID
VITE_AUTH0_AUDIENCE=https://stocksight-api
VITE_AUTH0_DATABASE_CONNECTION=Username-Password-Authentication
```

The connection setting must match the actual enabled database connection name.
The backend's issuer/audience configuration must still match the issued tokens.
There is no browser client secret or Management API token.

In the Auth0 SPA settings:

1. Preserve the existing Authorization Code grant. Enable **Implicit** for the
   Auth0.js response type, if not already enabled. Use RS256 signing.
2. Register the exact application origin in **Allowed Callback URLs**, **Allowed
   Logout URLs**, **Allowed Web Origins**, and **Allowed Origins (CORS)**. Local
   development uses `http://127.0.0.1:5173`. The deployed origin recorded in the
   current handoff is `https://stocksight-rose.vercel.app`; confirm the actual site
   before editing its allowlists. Do not use wildcards.
3. Enable cross-origin authentication for the existing application where the
   tenant exposes that setting. Preserve username signup and optional-email
   flexible identifiers on the existing database connection.
4. After deploying the verification page, set **Cross-Origin Verification Fallback
   URL** to `https://stocksight-rose.vercel.app/cross-origin-verification.html`.
   This is a dedicated Vite HTML entry, not the main React app or a login route.
   It invokes Auth0.js `crossOriginVerification()` only inside an iframe with the
   configured Auth0 origin. It accepts messages only from that origin and parent.
5. Enable the existing Google connection for this SPA. Preserve user-delegated
   API access to the configured audience.
6. For reliable embedded login in production browsers, place the app and Auth0
   custom domain under the same top-level domain. Third-party-cookie restrictions
   can otherwise block the password flow. The production app uses a vercel.app
   origin. Use **Trouble signing in?** for the hosted password path when
   cross-site cookies block the embedded form. Google is also available.

For a new environment, create a **Single Page Application** and an RS256 API
whose identifier is the logical access-token audience. Enable **User-Delegated
Access** for the SPA under the API's Application Access settings. If Auth0 reports
that the client cannot access the resource server, check this application grant
and the audience. Machine-to-machine access is unnecessary. Use short-lived API
access tokens (300 seconds in the demo tenant).

In the backend's ignored environment, configure the matching Auth0 domain and
audience plus the exact frontend origin:

```dotenv
STOCKSIGHT_AUTH0_DOMAIN=YOUR_TENANT.auth0.com
STOCKSIGHT_AUTH0_AUDIENCE=https://stocksight-api
STOCKSIGHT_APP_ORIGIN=http://127.0.0.1:5173
STOCKSIGHT_SESSION_MAX_AGE_SECONDS=28800
```

Use the hostname alone for the Auth0 domain. Set the app origin to the actual HTTPS
origin in production. Session lifetime can range from 300 to 86400 seconds.
Restart both processes after local configuration changes. Follow
[local startup](LOCAL_START.md) and migrate to the current Alembic head. Revision
0003 adds identity/watchlist storage, 0004 adds sessions, and 0005 controls
backend-only access. The historical chart remains available without Auth0.

## Username signup and optional recovery email

The existing Username-Password-Authentication connection uses Auth0 Flexible
Identifiers. The signup form requires a username and password
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
addresses for test accounts. The user enters passwords directly into the sign-in forms; no local password endpoints were introduced.

References: [Auth0 Flexible Identifiers](https://auth0.com/docs/authenticate/database-connections/activate-and-configure-attributes-for-flexible-identifiers),
[username-only support](https://support.auth0.com/center/s/article/Is-it-possible-to-create-users-using-username-and-password-instead-of-the-email-password-combination),
[OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
and [OWASP CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Persistent sessions

Auth0 still owns signup, login, password policies and recovery. After login the
frontend exchanges a valid Auth0 access token for an opaque StockSight session.
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

### Session API

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

## Watchlist API

Private routes accept an app cookie or a valid Auth0 API access token. An ID token
is an identity document and cannot authorize API calls. The server pins RS256 and
validates issuer, audience, signature, expiry, issued-at and subject, plus
not-before when supplied. It rejects machine identities and retrieves keys only
from the configured issuer.

| Method and path | Request | Success |
| --- | --- | --- |
| GET /api/me | App session or bearer token | 200 `{ "id": "local-user-uuid" }` |
| GET /api/watchlist | App session or bearer token | 200 `{ "items": [{ "symbol": "AAPL", "name": "Apple Inc.", "added_at": "ISO-UTC", "daily_change_pct": -0.12 }], "limit": 100 }` |
| POST /api/watchlist | App session or bearer token; JSON `{ "symbol": "AAPL" }` | 201 saved item; 200 same item on repeat |
| DELETE /api/watchlist/{symbol} | App session or bearer token | 204; repeated removal also 204 |

On the Analysis watchlist branch, saved items include `daily_change_pct`, calculated from the two most recent
stored closes. A value of `-0.12` means `-0.12%`. The value is `null` when
there is insufficient history.

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

## Verification

Use [local verification](LOCAL_START.md#verification) for isolated browser and
backend checks. The test issuer and SDK alias exist only in the account harness.
Test evidence covers signup, callback validation, session restoration and expiry,
logout revocation, ownership isolation and watchlist persistence.

For hosted acceptance, have the user exercise database and Google sign-in,
signup with and without a recovery email, recovery delivery, refresh, watchlist
persistence and logout. Verify a second account's data stays isolated. Test the
hosted password path in a browser that blocks third-party cookies. The
[handoff](CURRENT_HANDOFF.md) records the last live evidence. App sessions expire
or can be revoked through logout. There is currently no webhook for out-of-band
Auth0 account changes or password resets.
