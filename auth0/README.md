# StockSight Universal Login

**Current implementation:** the app now renders its own functional login/signup
and recovery forms. See [embedded login setup](../docs/EMBEDDED_LOGIN.md).
The files in this directory preserve the earlier hosted-template design and its
disabled standalone preview; uploading them is not required for the local forms.

A compact, opaque panel over StockSight's existing navy background and recognizable
stock chart. System typography, a quiet border, 22px corners, 36px preview padding,
filled inputs, and a restrained blue action keep the form in focus. The chart
background is static; there is no animation control or background JavaScript.
The decorative chart is illustrative and does not display live prices.
The checked-out `feature/frontend-redesign` branch still has the older app styling.

`universal-login.html` is an Auth0 **New Universal Login Liquid page template**.
It keeps the Auth0 widget intact for login, signup, password reset, MFA,
Google sign-in, validation, and accessible field behavior. It does not add an
embedded password form or alter the app's authentication flow.

## Preview

From the repository root, run:

```powershell
node auth0/preview.mjs
```

Open `artifacts/auth0/login-preview.html` or `signup-preview.html` in a browser.
These previews use the exact page shell with an approximate, disabled form in
place of the Auth0 widget. They cannot accept credentials or sign anyone in.
The real widget's spacing and fields depend on your connection settings.
The local preview has no glass or backdrop blur. The panel is opaque.
No generated Auth0 classes are overridden. The live widget retains its native
keyboard navigation, autofill, validation, loading states, and Google branding.
The preview includes Google's four-color G icon, explicit autocomplete tokens,
and the existing disabled-sign-in notice. Fields and authentication buttons
remain disabled rather than simulating successful authentication.

## Configure the widget theme

In **Auth0 Dashboard → Branding → Universal Login → Update branding theme**,
set these values and preview both login and signup:

| Setting | Value |
| --- | --- |
| Primary button | `#2865d6` |
| Primary button label | `#ffffff` |
| Links / focus | `#9dc1ff` / `#77acff` |
| Page background | `#060e20` |
| Widget background | `#151e2c` |
| Input background | `#1a2330` |
| Header / input text | `#f2f4f8` |
| Body / input placeholders | `#aab5c7` |
| Input / secondary button border | `#303845` |
| Widget width | `400px` |
| Widget corners | `22px` |
| Input / button corners | `10px` |
| Widget border / shadow | Off (the shell provides these) |

`theme.patch.json` contains the matching colors and borders for the Management
API: PATCH `/api/v2/branding/themes/{themeId}` after exporting the current theme.
It is a partial theme update, not a new tenant configuration. It does not change
connections, custom text, authentication behavior, or routes.

The shell and preview use `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
and make no external font requests. The Auth0 widget uses its configured theme
font; remove the previous custom IBM Plex font setting if present. Auth0's font
editor accepts hosted font files rather than a CSS system stack. Exact widget
typography, field spacing, and hover/pressed rendering remain Auth0-controlled;
the preview is a visual approximation, not a replacement credential form.

Remove the default Auth0 logo from the widget using its theme logo visibility
option; the shell supplies the StockSight wordmark immediately above the panel.

Under **Branding → Universal Login → Custom Text**, customize the login/signup
titles and descriptions to use `StockSight`, removing the development tenant
name visible in the original screenshot. Suggested login title: `Log in`;
signup title: `Create an account`; description: `Continue to StockSight.`
Keep existing connection requirements (including username and optional email).

## Apply the page template

Auth0 requires a **configured custom domain** for this template, and the template
is uploaded through the **Management API**. Theme-only customization above is
available independently of this surrounding layout. Do not paste this file into
the Classic Login custom HTML editor.

1. Export the current tenant theme, custom text, and page template for rollback.
2. Configure and verify your custom domain in Auth0, and verify that the app's
   Auth0 domain and API token issuer settings are compatible with that domain.
3. With an appropriately scoped Management API token (`update:branding`), send
   `PUT /api/v2/branding/templates/universal-login` a JSON object with a `body`
   property containing the complete contents of `universal-login.html`.
4. Test an actual authorization redirect from StockSight using the custom domain:
   login, signup, Google sign-in, wrong password, reset password, logout, and any
   enabled MFA. Check narrow screens and keyboard focus as well.

The template affects the tenant's Universal Login flows; review other apps using
the same tenant before publishing. The preview is not evidence of a live Auth0
login test. Nothing in these files publishes tenant settings automatically.

Auth0 references:
- [Page templates and custom-domain requirements](https://auth0.com/docs/customize/login-pages/universal-login/customize-templates)
- [Theme editor](https://auth0.com/docs/customize/login-pages/universal-login/customize-themes)
- [Custom text](https://auth0.com/docs/customize/login-pages/universal-login/customize-text-elements)
