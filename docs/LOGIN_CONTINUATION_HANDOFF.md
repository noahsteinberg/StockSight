# StockSight login continuation handoff

Prepared November 17, 2026. Read this first in the next conversation, then
[AGENTS.md](../AGENTS.md), [CURRENT_HANDOFF.md](CURRENT_HANDOFF.md), and
[EMBEDDED_LOGIN.md](EMBEDDED_LOGIN.md).

November 22 checkpoint. PR #13 is merged into main at `dcb4418`.
The dedicated verification HTML and its script returned HTTP 200 from the rose
origin. The public deployment smoke check passed against hosted database storage.
The tenant's exact fallback URL and real-user sign-in are still unverified.

## Goal and user decisions

Finish publishing and configuring the custom StockSight login/signup flow.
The user approved the compact Apple-inspired panel, system typography, restrained
blue controls, existing navy stock-chart background, and **no animations**.
Preserve the current routes and authentication/session behavior.

The user wants username/password forms on StockSight, with Auth0 managing
identities/password validation, plus Google sign-in. They requested removal of
the “Continue with Auth0 sign-in” fallback link. They explicitly chose to keep
`https://stocksight-rose.vercel.app` for now rather than obtain a custom domain.
Do not silently switch authentication architecture or weaken verification policies.
ML work is outside this task.

## Checkout and publication status

- Workspace: `C:\Users\gavin\Documents\School Stuff\cse 4095\Project\stocksight`.
- Branch: `fix/auth0-verification`, tracking `origin/fix/auth0-verification`.
- Implementation commit: `d88a7a87dedba37d262eda09905ada0cb63db219`.
- Fix branch is pushed. PR: <https://github.com/noahsteinberg/StockSight/pull/13>.
- PR #13 is **merged** into main at `dcb4418`.
- Previous embedded-login implementation PR #12 was merged into main at
  `0c793499ac81c8be446fa4a2115ab740838ceb7c`; its Vercel deployment succeeded.
- Production: <https://stocksight-rose.vercel.app>.
- The dedicated verification handler is available on production. The live
  account experience still needs the acceptance checks below.
- Repository instructions expect verified local commits. Pushing/merging requires
  user instruction. Earlier user authorized pushing a branch/opening a PR;
  no instruction to merge PR #13 was received in this conversation.

## What caused the failures

1. Live Auth0 logs first showed `Cross origin login not allowed.`
2. User explicitly approved enabling “Allow Cross-Origin Authentication” on the
   existing StockSight SPA and allowing only `https://stocksight-rose.vercel.app`
   in Allowed Origins (CORS). Those settings were saved and reloaded to verify.
3. Later attempts logged `Unable to configure verification page.` The application
   had no dedicated Auth0 cross-origin verification page/fallback URL configured.
4. Callback failures were being flattened into “Could not restore your session.
   Sign in again.”, which hid the distinction between provider and app-session errors.

There is also a separate browser limitation: with the app on `vercel.app` and Auth0
on `auth0.com`, embedded password login can fail when third-party cookies are
blocked. The verification fallback cannot overcome that in Chrome/Safari without
a same-site custom domain. Do not promise that this patch makes password login
reliable in those conditions. Google remains the alternative. Official reference:
<https://auth0.com/docs/get-started/applications/set-up-cors>.

## Changes in PR #13

- `frontend/cross-origin-verification.html`: separate minimal HTML entry, no React
  app/password form/session exchange, noindex and no-referrer.
- `frontend/src/cross-origin-verification.js`: uses the existing Auth0.js client
  and `crossOriginVerification()`. Only initializes inside an iframe for the
  configured Auth0 origin; message guard checks both origin and parent source.
- `frontend/vite.config.js`: builds both the main app and verification HTML entry.
- `frontend/src/AuthPage.jsx` / `.css`: removes the hosted Auth0 fallback control.
  Google, validation, password controls, and routes are preserved.
- `frontend/src/embedded-auth.js`: safe errors classified by provider codes;
  exported client factory and typed `AuthFlowError`. No raw provider descriptions
  or credentials are shown. No security challenge is bypassed.
- `frontend/src/AuthProvider.jsx`: preserves safe callback errors rather than
  flattening every failure into session restoration.
- Browser regression tests and setup/handoff documentation updated.

Underlying architecture remains: React/Vite/plain CSS, lazy Auth0.js password
flow, Google via official Auth0 React SDK with Authorization Code + PKCE, backend
JWT verification followed by an opaque HttpOnly StockSight session cookie.
Preserve CSRF, expiry, logout, and account-switch/watchlist isolation. Never persist
provider tokens or put client secrets in frontend code.

## Verification completed before commit

- `npm run lint`: passed.
- `npm run build`: passed; output includes `cross-origin-verification.html`.
- `npm run test:e2e:accounts`: **20 passed**.
- Focused embedded-auth suite: **9 passed**.
- `npm run test:e2e`: passed; final Playwright result recorded passed/no failed tests.
- `git diff --check`: passed; source and docs committed, no secrets/generated artifacts.

Tests use disposable SQLite, synthetic identities, and intercepted provider HTTP.
Verifier tests exercise the real SDK handshake under synthetic HTTPS origins,
including trusted/untrusted parent behavior. These are not real-user Auth0 login,
production-cookie, email delivery, or live deployment acceptance.
An initial synthetic HTTP iframe test failed due to mixed-content protection;
the corrected HTTPS test and full account suite passed.

## Next steps, in order

1. In the **existing StockSight SPA** Auth0 settings, verify **Cross-Origin
   Verification Fallback URL** is exactly:
   `https://stocksight-rose.vercel.app/cross-origin-verification.html`.
   Do this after the page is deployed. Preserve existing allowed URLs/origins and
   security policies. Apply any required action-time approval for security settings.
2. Have the user enter their own credentials and test real sign-in. Do not handle
   or print their password, callback tokens, cookies, or reset links. Inspect safe
   Auth0 log descriptions to distinguish browser-cookie failure, provider rejection,
   and StockSight session creation failure.
3. Confirm fallback link absent, Google still available, session refresh/logout,
   signup/reset behavior, and private watchlist isolation as appropriate. Clearly
   report any remaining browser limitation instead of declaring full acceptance.
4. Update the handoff with tenant configuration and live account test evidence.

Before starting servers or live HTTP/database tests, run backend virtualenv Python
`-m app.environment_check` from `backend` as required by AGENTS.md. Use configured
escalation for sandbox/network denial; do not restart services repeatedly to fix
permission errors. Do not seed/reset/reimport the normal database.

## Access and tooling notes

- Auth0 tenant: `dev-uz71oip7v88hdtsp.us.auth0.com`.
- Existing SPA client ID (public): `DsEQAk55JjH1R67jZ58IrVDWjlV1ALuE`.
- Database connection: `Username-Password-Authentication`.
- Expected API audience documented as `https://stocksight-api`; verify current
  deployment configuration without printing secret values.
- Auth0 settings were accessible in the user's signed-in Chrome. Use fresh browser
  inventory/state; old tab handles may be stale. Avoid dumping full settings trees,
  which may contain secrets. Users enter hosted credentials themselves.
- GitHub connector PR creation previously returned 403; signed-in Chrome successfully
  created PR #13. Git push worked through approved escalation. `gh` was unavailable.
- GitHub Actions checks were failing because repository-owner account billing was
  locked, not because tests ran and found code failures. PR #13 showed three failing
  optional checks; inspect current annotations if relevant before repeating that claim.
  Vercel's independent Git integration previously deployed main despite Actions failure.
- Production Vercel is under `noah-steinbergs-projects`; connected Vercel tools lacked
  access to that team. Do not recreate/move the project to work around this.
- There is no local frontend Auth0 env file and no normal local DB running established
  for this task. Do not invent configuration or expose backend `.env` values.

## Suggested next-conversation prompt

> Read `docs/LOGIN_CONTINUATION_HANDOFF.md` and continue the StockSight login fix.
> Verify the Auth0 fallback setting and finish real-login acceptance.
> Keep vercel.app, preserve the static
> navy-chart design, and do not claim browser-cookie restrictions are solved.
