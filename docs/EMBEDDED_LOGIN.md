# StockSight account pages

Implemented November 17, 2026. This supersedes the hosted-page-only design drafts
in `auth0/` and the Universal Login-only frontend descriptions in older handoffs.
The existing backend session, CSRF, ownership and watchlist contracts are unchanged.

## Behavior

- `/#/login`, `/#/signup`, and `/#/reset-password` render the real React forms.
  Account buttons open these pages. Browser back/forward and direct links work.
- The approved navy chart background is static. The compact panel, system fonts,
  blue primary action and Google icon match the design preview. No animation or
  animation control is included. Reduced-motion preferences disable transitions.
- Missing public Auth0 configuration disables sign-in with an explicit message.
  Configured forms are functional and do not display the old disabled-preview notice.
- Username/password goes directly to Auth0 using Auth0.js cross-origin login.
  Auth0 manages password verification, policies, abuse protection and identities.
  No StockSight password endpoint, password table or client secret is introduced.
- Signup uses Auth0's public `/dbconnections/signup` endpoint so the existing
  flexible-identifier connection can continue accepting usernames without an email.
  Creation does not silently sign in. The user follows the login link afterward.
  The optional email can be used for recovery; Auth0 owns verification requirements.
- Reset sends Auth0's recovery email. The confirmation does not identify whether
  an account exists. Accounts without recovery email may need administrator help.
- Google uses the existing official React SDK, Authorization Code + PKCE, and
  `connection=google-oauth2`; the provider consent/sign-in screens remain external.
- **Trouble signing in?** opens a password recovery option for blocked cross-site
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
`authorizedFetch`. No backend code, schema or existing account data changes.

## Tenant setup before live acceptance

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
   can otherwise block the password flow. The user chose to keep the vercel.app
   address for now. Use **Trouble signing in?** for the hosted password path when
   cross-site cookies block the embedded form. Google is also available.

These settings are not applied automatically by the source changes. The old
Universal Login Liquid template/theme upload is not needed for these local forms.

After configuration, have the user test an existing username, signup with and
without recovery email, invalid password, recovery-email delivery, Google,
refresh, logout and two-account watchlist isolation. Use a browser that restricts
third-party cookies to check and clearly record the password-login limitation. Do not print credentials or tokens.

## November 17 verification-page follow-up

Live Auth0 logs showed `Cross origin login not allowed.` The user approved
enabling cross-origin authentication for the existing SPA and adding only the
production origin to Allowed Origins (CORS); the saved settings were verified.
Later live attempts logged `Unable to configure verification page.`
The page/handler above addresses the missing SDK verification endpoint. Auth0
explicitly documents that Chrome/Safari cannot use this fallback to overcome
blocked third-party cookies without a same-site custom domain.

The UI now distinguishes provider callback failure from app-session creation
failure instead of presenting every problem as session restoration failure.
Provider descriptions, credentials and tokens are never echoed into errors.

## Verification

The account Playwright suite uses isolated SQLite, signed test identities and
intercepted Auth0 HTTP boundaries. It is separate from live-tenant acceptance.
It covers signup, rejected password login, recovery requests, SDK callback
validation/session creation, rejected callbacks, Google PKCE, session refresh,
expiry, logout revocation, two-user isolation, and desktop/mobile layout.
The test alias exists only in Vite's `e2e-accounts` serve mode and cannot be built
for production. No new authentication bypass or test endpoint is in the real app.

Official references:
- [Auth0.js and its cross-origin login flow](https://auth0.com/docs/libraries/auth0js)
- [Verification-page setup and browser support](https://auth0.com/docs/get-started/applications/set-up-cors)
- [Browser cookie constraints](https://auth0.com/docs/authenticate/login/cross-origin-authentication)
- [Hosted and embedded login](https://auth0.com/docs/authenticate/login/universal-vs-embedded-login)
