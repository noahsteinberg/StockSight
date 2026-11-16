import { test, expect } from '@playwright/test';
import process from 'node:process';

async function token(request, user = 'alice', expired = false) {
  return (await (await request.get(`/api/test/identity?user=${user}&expired=${expired}`)).json()).access_token;
}

test.beforeEach(async ({ request }) => {
  for (const user of ['alice', 'bob']) {
    const accessToken = await token(request, user);
    await request.delete('/api/watchlist/AAPL', { headers: { Authorization: `Bearer ${accessToken}` } });
  }
});

test('account creation entry, save, refresh, open analysis and persistent removal', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Sign in to keep your saved stocks here.')).toBeVisible();
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByText('Alice Example')).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('stocksight:e2e-signup'))).toBe('true');
  const save = page.waitForResponse(response => response.url().endsWith('/api/watchlist') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Save to watchlist', exact: true }).click();
  expect((await save).status()).toBe(201);
  await expect(page.getByRole('button', { name: 'Saved to watchlist' })).toBeDisabled();
  await page.reload();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  await page.getByRole('link', { name: 'Open AAPL analysis' }).click();
  await expect(page.getByRole('heading', { name: 'AAPL Apple Inc.' })).toBeVisible();
  await page.getByRole('button', { name: 'Remove AAPL' }).click();
  await expect(page.getByText('No saved stocks yet.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('No saved stocks yet.')).toBeVisible();
});

test('two users have isolated lists; sign-out removes private UI', async ({ page, browser, request }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Save to watchlist', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5175' });
  try {
    const bob = await context.newPage();
    await bob.addInitScript(() => sessionStorage.setItem('stocksight:e2e-next-user', 'bob'));
    await bob.goto('/');
    await bob.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(bob.getByText('Bob Example')).toBeVisible();
    await expect(bob.getByText('No saved stocks yet.')).toBeVisible();
    const bobToken = await token(request, 'bob');
    expect((await request.delete('/api/watchlist/AAPL', { headers: { Authorization: `Bearer ${bobToken}` } })).status()).toBe(204);
    await page.reload();
    await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  } finally { await context.close(); }
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toHaveCount(0);
  await expect(page.getByText('Sign in to keep your saved stocks here.')).toBeVisible();
  expect((await request.get('/api/watchlist')).status()).toBe(401);
});

test('storage failure has a real retry path', async ({ page }) => {
  await page.route('**/api/watchlist', route => route.request().method() === 'GET' ? route.fulfill({ status: 503, json: { detail: { code: 'ACCOUNT_STORAGE_UNAVAILABLE' } } }) : route.continue());
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Your watchlist is unavailable. Try again.');
  await page.unroute('**/api/watchlist');
  await page.getByRole('button', { name: 'Retry watchlist' }).click();
  await expect(page.getByText('No saved stocks yet.')).toBeVisible();
});

test('expired signed access token is rejected through the actual API', async ({ page, request }) => {
  const expired = await token(request, 'alice', true);
  await page.route('**/api/test/identity?user=alice', route => route.fulfill({ json: { access_token: expired } }));
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Sign in again or retry');
  await page.unroute('**/api/test/identity?user=alice');
  await page.getByRole('button', { name: 'Retry watchlist' }).click();
  await expect(page.getByText('No saved stocks yet.')).toBeVisible();
});

test('mobile account and saved-stock actions fit the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Save to watchlist', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Remove AAPL' })).toBeVisible();
  await page.getByRole('link', { name: 'Watchlist', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (process.env.STOCKSIGHT_VISUAL_QA === '1') await page.screenshot({ path: '../.local-data/accounts-mobile.png', fullPage: true });
});

test('official Auth0 SDK sends signup to hosted authorization with PKCE', async ({ page }) => {
  let authorization;
  await page.route('https://e2e.auth0.test/authorize**', route => {
    authorization = new URL(route.request().url());
    return route.fulfill({ contentType: 'text/html', body: '<p>Test authorization boundary reached.</p>' });
  });
  // This server uses the actual Auth0 React SDK, without the test alias.
  await page.goto('http://127.0.0.1:5176');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByText('Test authorization boundary reached.')).toBeVisible();
  expect(authorization.searchParams.get('audience')).toBe('https://stocksight-test-api');
  expect(authorization.searchParams.get('screen_hint')).toBe('signup');
  expect(authorization.searchParams.get('redirect_uri')).toBe('http://127.0.0.1:5176');
  expect(authorization.searchParams.get('response_type')).toBe('code');
  expect(authorization.searchParams.get('code_challenge_method')).toBe('S256');
  expect(authorization.searchParams.get('code_challenge')).toBeTruthy();
  expect(authorization.searchParams.get('state')).toBeTruthy();
  expect(authorization.searchParams.has('client_secret')).toBe(false);
});

test('invalid OAuth callback fails safely in the official SDK', async ({ page }) => {
  await page.goto('http://127.0.0.1:5176/?code=invalid&state=invalid');
  await expect(page.getByRole('alert')).toContainText('Sign-in did not finish. Try again.');
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toHaveCount(0);
});
