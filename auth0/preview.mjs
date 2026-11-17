// Local visual approximation only. Never collects credentials or calls Auth0.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const template = await readFile(new URL('./universal-login.html', import.meta.url), 'utf8');
const output = new URL('../artifacts/auth0/', import.meta.url);
await mkdir(output, { recursive: true });
const css = `<style>${await readFile(new URL('./preview.css', import.meta.url), 'utf8')}</style>`;

for (const signup of [false, true]) {
  const widget = `<section class="preview-card" aria-labelledby="account-title">
    <h1 id="account-title">${signup ? 'Create an account' : 'Log in'}</h1>
    <p class="subtitle">Continue to StockSight.</p>
    <div class="preview-field"><label for="username">Username</label><input id="username" name="username" autocomplete="username" placeholder="Your username" disabled></div>
    ${signup ? '<div class="preview-field"><label for="email">Email address (optional)</label><input id="email" name="email" type="email" autocomplete="email" placeholder="you@example.com" disabled></div>' : ''}
    <div class="preview-field"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="${signup ? 'new-password' : 'current-password'}" placeholder="Enter your password" disabled></div>
    <button class="primary" disabled>Continue</button>
    <p class="switch">${signup ? 'Already have an account? <a href="login-preview.html">Log in</a>' : 'New to StockSight? <a href="signup-preview.html">Create an account</a>'}</p>
    <div class="preview-divider">OR</div>
    <button class="secondary" type="button" disabled><svg class="google-icon" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6C44.4 38.03 46.98 31.85 46.98 24.55z"/><path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.87 23.87 0 0 0 0 24c0 3.87.93 7.52 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.91-5.8l-7.73-6c-2.15 1.45-4.92 2.3-8.18 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>Continue with Google</button>
    <p class="preview-note">Design preview · Sign-in is disabled.</p>
  </section>`;
  const html = template
    .replace(/{{ locale[^}]*}}/g, 'en')
    .replace(/{{ dir[^}]*}}/g, 'ltr')
    .replace(/{{ prompt.screen.texts.pageTitle[^}]*}}/g, `${signup ? 'Sign up' : 'Log in'} | StockSight`)
    .replace('{%- auth0:head -%}', css)
    .replace('{%- auth0:widget -%}', widget);
  const name = `${signup ? 'signup' : 'login'}-preview.html`;
  await writeFile(new URL(name, output), html);
  console.log(fileURLToPath(new URL(name, output)));
}
