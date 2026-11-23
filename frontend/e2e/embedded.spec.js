import { test, expect } from '@playwright/test';
import { createHash, generateKeyPairSync, sign } from 'node:crypto';
import { Buffer } from 'node:buffer';
import process from 'node:process';

async function mockSuccessfulPasswordLogin(page, request, onPasswordLogin) {
  const proof = await (await request.get('/api/test/identity?user=alice')).json();
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const jwk = publicKey.export({ format: 'jwk' });
  await page.route('https://e2e.auth0.test/.well-known/jwks.json', route => route.fulfill({ json: { keys: [{ ...jwk, kid: 'provider-test-key', use: 'sig', alg: 'RS256' }] } }));
  await page.route('https://e2e.auth0.test/co/authenticate', route => {
    onPasswordLogin(route.request().postDataJSON());
    return route.fulfill({ json: { login_ticket: 'synthetic-ticket', co_id: 'synthetic-co', co_verifier: 'synthetic-verifier' } });
  });
  await page.route('https://e2e.auth0.test/authorize**', route => {
    const url = new URL(route.request().url());
    expect(url.searchParams.get('response_type')).toBe('token id_token');
    expect(url.searchParams.get('state')).toBeTruthy();
    expect(url.searchParams.get('nonce')).toBeTruthy();
    const now = Math.floor(Date.now() / 1000);
    const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'provider-test-key', typ: 'JWT' })).toString('base64url');
    const payload = Buffer.from(JSON.stringify({
      iss: 'https://e2e.auth0.test/', aud: 'test-only-client', sub: 'auth0|alice',
      iat: now, exp: now + 300, nonce: url.searchParams.get('nonce'),
      at_hash: createHash('sha256').update(proof.access_token).digest().subarray(0, 16).toString('base64url'),
    })).toString('base64url');
    const signature = sign('RSA-SHA256', Buffer.from(`${header}.${payload}`), privateKey).toString('base64url');
    const fragment = new URLSearchParams({ access_token: proof.access_token, id_token: `${header}.${payload}.${signature}`, state: url.searchParams.get('state'), token_type: 'Bearer', expires_in: '300' });
    return route.fulfill({ status: 302, headers: { location: `${url.searchParams.get('redirect_uri')}/#${fragment}` }, body: '' });
  });
  return proof.access_token;
}

for (const mode of ['login', 'signup']) {
  test(`${mode} establishes the existing HttpOnly app session and opens the dashboard`, async ({ page, request }) => {
    const username = 'test-username';
    const password = 'Synthetic-only!789';
    const events = [];
    await page.route('https://e2e.auth0.test/dbconnections/signup', route => {
      const payload = route.request().postDataJSON();
      expect(payload).toMatchObject({ username, password, connection: 'Username-Password-Authentication' });
      expect(payload).not.toHaveProperty('email');
      expect(payload).not.toHaveProperty('client_secret');
      events.push('signup');
      return route.fulfill({ status: 200, json: { username } });
    });
    const accessToken = await mockSuccessfulPasswordLogin(page, request, payload => {
      expect(payload).toMatchObject({ username, password, realm: 'Username-Password-Authentication' });
      events.push('login');
    });
    await page.goto(`/#/${mode}`);
    await page.getByLabel('Username', { exact: true }).fill(username);
    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: mode === 'signup' ? 'Create account' : 'Continue', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'My dashboard' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
    expect(events).toEqual(mode === 'signup' ? ['signup', 'login'] : ['login']);
    expect(page.url()).toMatch(/#\/dashboard$/);
    const cookie = (await page.context().cookies()).find(cookie => cookie.name === 'stocksight_session');
    expect(cookie.httpOnly).toBe(true);
    const stored = await page.evaluate(() => [...Object.values(localStorage), ...Object.values(sessionStorage)].join(' '));
    expect(stored.includes(accessToken)).toBe(false);
    expect(stored.includes(password)).toBe(false);
    await page.reload();
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  });
}

// Actual Auth0.js, with the remote Auth0 HTTP boundary intercepted. No real users.
test('successful signup with a blocked auto-login offers recovery without another signup', async ({ page }) => {
  let signupCount = 0, loginCount = 0;
  await page.route('https://e2e.auth0.test/dbconnections/signup', route => {
    signupCount++;
    return route.fulfill({ status: 200, json: { username: 'test-username' } });
  });
  await page.route('https://e2e.auth0.test/co/authenticate', route => {
    loginCount++;
    return route.fulfill({ status: 403, json: { error: 'requires_verification' } });
  });
  await page.goto('/#/signup');
  await page.getByLabel('Username', { exact: true }).fill('test-username');
  await page.getByLabel('Password', { exact: true }).fill('Synthetic-only!789');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('finish verifying your sign-in');
  await expect(page.getByRole('status')).toContainText('Account created');
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Continue on Auth0' })).toBeEnabled();
  await expect(page.getByRole('link', { name: 'Log in', exact: true })).toHaveAttribute('href', '#/login');
  expect(signupCount).toBe(1);
  expect(loginCount).toBe(1);
  expect((await page.context().cookies()).some(cookie => cookie.name === 'stocksight_session')).toBe(false);
});

test('signup rejection does not start auto-login and allows retry', async ({ page }) => {
  let startedLogin = false;
  await page.route('https://e2e.auth0.test/co/authenticate', route => {
    startedLogin = true;
    return route.abort();
  });
  await page.route('https://e2e.auth0.test/dbconnections/signup', route => route.fulfill({
    status: 400, json: { code: 'invalid_signup' },
  }));
  await page.goto('/#/signup');
  await page.getByLabel('Username', { exact: true }).fill('test-username');
  await page.getByLabel('Password', { exact: true }).fill('Synthetic-only!789');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Could not create the account');
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toBeEnabled();
  expect(startedLogin).toBe(false);
});

test('password login uses cross-origin Auth0 and safely displays rejection', async ({ page }) => {
  let payload;
  await page.route('https://e2e.auth0.test/co/authenticate', route => {
    payload = route.request().postDataJSON();
    return route.fulfill({ status: 403, json: { error: 'access_denied', error_description: 'DO NOT DISPLAY RAW PROVIDER DETAILS' } });
  });
  await page.goto('/#/login');
  await page.getByLabel('Username', { exact: true }).fill('test-username');
  await page.getByLabel('Password', { exact: true }).fill('Synthetic-only!789');
  await page.getByRole('button', { name: 'Show password' }).click();
  await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('type', 'text');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Check your username and password');
  await expect(page.getByRole('alert')).not.toContainText('DO NOT DISPLAY');
  expect(payload.realm).toBe('Username-Password-Authentication');
  expect(payload.username).toBe('test-username');
  expect(payload).not.toHaveProperty('client_secret');
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('');
  await expect(page.getByRole('button', { name: 'Continue with Auth0 sign-in' })).toHaveCount(0);
});

test('reset email is sent through Auth0 with a non-enumerating confirmation', async ({ page }) => {
  let payload;
  await page.route('https://e2e.auth0.test/dbconnections/change_password', route => {
    payload = route.request().postDataJSON();
    return route.fulfill({ status: 200, contentType: 'text/plain', body: 'Request accepted.' });
  });
  await page.goto('/#/login');
  await page.getByRole('link', { name: 'Forgot password?' }).click();
  await page.getByLabel('Recovery email').fill('synthetic@example.com');
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('status')).toContainText('If an account has this recovery email');
  expect(payload.email).toBe('synthetic@example.com');
});

test('unsolicited fragment tokens fail closed and are removed from the URL', async ({ page }) => {
  let created = false;
  await page.route('**/api/auth/session', route => {
    if (route.request().method() === 'POST') created = true;
    return route.continue();
  });
  await page.goto('/#access_token=invalid&id_token=invalid&state=untrusted');
  await expect(page.getByRole('heading', { name: 'Log in' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Sign-in could not be verified');
  expect(page.url()).toMatch(/#\/login$/);
  expect(created).toBe(false);
});

test('provider callback errors offer Auth0 recovery without exposing provider details', async ({ page }) => {
  await page.goto('/#error=server_error&error_description=private-provider-details&state=failed-transaction');
  await expect(page.getByRole('alert')).toHaveText('Password sign-in is temporarily unavailable. Try again or continue on Auth0.');
  await expect(page.getByRole('alert')).not.toContainText('private-provider-details');
  await expect(page.getByRole('button', { name: 'Continue on Auth0' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Continue with Google' })).toBeEnabled();
  expect(page.url()).toMatch(/#\/login$/);
});

test('password verification sends the user to the hosted database connection with PKCE', async ({ page }) => {
  await page.route('https://e2e.auth0.test/co/authenticate', route => route.fulfill({
    status: 403, json: { error: 'requires_verification' },
  }));
  let authorization;
  await page.route('https://e2e.auth0.test/authorize**', route => {
    authorization = new URL(route.request().url());
    return route.fulfill({ contentType: 'text/html', body: '<p>Hosted test challenge</p>' });
  });
  await page.goto('http://127.0.0.1:5176/#/login');
  const hosted = page.getByRole('button', { name: 'Continue on Auth0' });
  await expect(hosted).toBeHidden();
  await page.getByText('Trouble signing in?').click();
  await expect(hosted).toBeVisible();
  await page.getByText('Trouble signing in?').click();
  await page.getByLabel('Username', { exact: true }).fill('test-username');
  await page.getByLabel('Password', { exact: true }).fill('Synthetic-only!789');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('finish verifying your sign-in');
  await expect(page.getByLabel('Password', { exact: true })).toHaveValue('');
  await hosted.click();
  await expect(page.getByText('Hosted test challenge')).toBeVisible();
  expect(authorization.searchParams.get('connection')).toBe('Username-Password-Authentication');
  expect(authorization.searchParams.get('prompt')).toBe('login');
  expect(authorization.searchParams.get('response_type')).toBe('code');
  expect(authorization.searchParams.get('code_challenge_method')).toBe('S256');
  expect(authorization.searchParams.get('state')).toBeTruthy();
  expect(authorization.searchParams.has('password')).toBe(false);
});

test('dedicated verification page is separate from the app and ignores untrusted parents', async ({ page }) => {
  await page.goto('/cross-origin-verification.html');
  await expect(page.getByRole('status')).toContainText('used automatically');
  await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
  await page.route('**/verification-harness', route => route.fulfill({ contentType: 'text/html', body: `<p role="status">No verifier messages</p><script>addEventListener('message', () => document.querySelector('p').textContent = 'Unexpected verifier message');</script><iframe src="/cross-origin-verification.html#origin=http%3A%2F%2F127.0.0.1%3A5175"></iframe>` }));
  await page.goto('/verification-harness');
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('status')).toHaveText('No verifier messages');
  await expect(page.frameLocator('iframe').getByRole('status')).toContainText('used automatically');
});

test('configured Auth0 parent can complete the SDK verifier handshake', async ({ page }) => {
  // Keep both synthetic frames on HTTPS. Loading a localhost HTTP iframe from
  // an HTTPS provider would test mixed-content protection instead of the SDK.
  await page.route('https://app.stocksight.test/**', async route => {
    const url = new URL(route.request().url());
    const response = await route.fetch({ url: `http://127.0.0.1:5175${url.pathname}${url.search}` });
    return route.fulfill({ response });
  });
  await page.route('https://e2e.auth0.test/verification-harness', route => route.fulfill({ contentType: 'text/html', body: `
    <p role="status">Waiting</p>
    <iframe src="https://app.stocksight.test/cross-origin-verification.html#origin=https%3A%2F%2Fe2e.auth0.test"></iframe>
    <script>
      addEventListener('message', event => {
        if (event.origin !== 'https://app.stocksight.test') return;
        if (event.data.type === 'ready') event.source.postMessage({ type: 'co_verifier_request', request: { id: 'nonexistent-synthetic-id' } }, event.origin);
        if (event.data.type === 'co_verifier_response' && event.data.response.verifier === '') document.querySelector('p').textContent = 'Verified handshake';
      });
    </script>` }));
  await page.goto('https://e2e.auth0.test/verification-harness');
  await expect(page.getByRole('status')).toHaveText('Verified handshake');
});

test('local account routes fit desktop and mobile without animation', async ({ page }) => {
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ['login', 'signup', 'reset-password']) {
      await page.goto(`/#/${route}`);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      expect(await page.locator('.ss-chart').first().evaluate(el => getComputedStyle(el).animationName)).toBe('none');
      if (process.env.STOCKSIGHT_VISUAL_QA === '1' && ((width === 1440 && route === 'login') || (width === 390 && route === 'signup'))) {
        await expect(page.getByRole('button', { name: route === 'login' ? 'Continue' : 'Create account', exact: true })).toBeEnabled();
        await page.screenshot({ path: `../.local-data/embedded-${route}-${width}.png`, fullPage: true });
      }
    }
  }
});
