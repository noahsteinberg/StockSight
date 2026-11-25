import { test, expect } from '@playwright/test';
import process from 'node:process';

async function token(request, user = 'alice', expired = false) {
  return (await (await request.get(`/api/test/identity?user=${user}&expired=${expired}`)).json()).access_token;
}

async function signIn(page) {
  const hash = new URL(page.url()).hash;
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Continue with Google', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
  await page.evaluate(value => { window.location.hash = value; }, hash);
}

test.beforeEach(async ({ request }) => {
  for (const user of ['alice', 'bob']) {
    const accessToken = await token(request, user);
    await request.delete('/api/watchlist/AAPL', { headers: { Authorization: `Bearer ${accessToken}` } });
  }
});

test('account creation entry, save, refresh, open analysis and persistent removal', async ({ page }) => {
  await page.goto('/#/analysis');
  await expect(page.getByText('Star a stock to add it here')).toBeVisible();
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Create an account' })).toBeVisible();
  await page.getByRole('button', { name: 'Continue with Google', exact: true }).click();
  await expect(page.getByText('Alice Example')).toBeVisible();
  await page.getByRole('link', { name: 'Analysis', exact: true }).click();
  const save = page.waitForResponse(response => response.url().endsWith('/api/watchlist') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Watchlist for AAPL', exact: true }).click();
  expect((await save).status()).toBe(201);
  await expect(page.getByRole('button', { name: 'Watchlist for AAPL' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toContainText('0.12%');
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' }).locator('.negative')).toBeVisible();
  // Drop all simulated SDK state: only the HttpOnly app cookie may restore login.
  await page.evaluate(() => sessionStorage.removeItem('stocksight:e2e-user'));
  let exchangedAfterRefresh = false;
  await page.route('**/api/test/identity?*', route => { exchangedAfterRefresh = true; return route.abort(); });
  await page.reload();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  expect(exchangedAfterRefresh).toBe(false);
  const cookie = (await page.context().cookies()).find(value => value.name === 'stocksight_session');
  expect(cookie.httpOnly).toBe(true);
  await page.getByRole('link', { name: 'Open AAPL analysis' }).click();
  await expect(page.getByRole('heading', { name: 'AAPL Apple Inc.' })).toBeVisible();
  await page.getByRole('button', { name: 'Watchlist for AAPL' }).click();
  await expect(page.getByText('Star a stock to add it here')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Watchlist for AAPL' })).toHaveAttribute('aria-pressed', 'false');
  await page.reload();
  await expect(page.getByText('Star a stock to add it here')).toBeVisible();
});

test('two users have isolated lists; sign-out removes private UI', async ({ page, browser, request }) => {
  await page.goto('/#/analysis');
  await signIn(page);
  await page.getByRole('button', { name: 'Watchlist for AAPL', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  const priorCookie = (await page.context().cookies()).find(cookie => cookie.name === 'stocksight_session');
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5175' });
  try {
    const bob = await context.newPage();
    await bob.addInitScript(() => sessionStorage.setItem('stocksight:e2e-next-user', 'bob'));
    await bob.goto('/#/analysis');
    await signIn(bob);
    await expect(bob.getByText('Bob Example')).toBeVisible();
    await expect(bob.getByText('Star a stock to add it here')).toBeVisible();
    const bobToken = await token(request, 'bob');
    expect((await request.delete('/api/watchlist/AAPL', { headers: { Authorization: `Bearer ${bobToken}` } })).status()).toBe(204);
    await page.reload();
    await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  } finally { await context.close(); }
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toHaveCount(0);
  await expect(page.getByText('Star a stock to add it here')).toBeVisible();
  expect((await request.get('/api/watchlist')).status()).toBe(401);
  expect((await request.get('/api/watchlist', { headers: { Cookie: `stocksight_session=${priorCookie.value}` } })).status()).toBe(401);
});

test('expired app session hides private data and rejects the attempted mutation', async ({ page, request }) => {
  await page.goto('/#/analysis');
  await signIn(page);
  await page.getByRole('button', { name: 'Watchlist for AAPL', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  await request.post('/api/test/expire?user=alice');
  await page.getByRole('button', { name: 'Watchlist for AAPL' }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toHaveCount(0);
  await expect(page.getByRole('alert')).toContainText('session expired');
  await signIn(page);
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
});

test('an existing tab detects an account switch without exposing the old list', async ({ page }) => {
  await page.goto('/#/analysis');
  await signIn(page);
  await page.getByRole('button', { name: 'Watchlist for AAPL', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  const other = await page.context().newPage();
  await other.goto('/#/analysis');
  await other.getByRole('button', { name: 'Sign out', exact: true }).click();
  await other.evaluate(() => sessionStorage.setItem('stocksight:e2e-next-user', 'bob'));
  await signIn(other);
  await expect(other.getByText('Bob Example')).toBeVisible();
  await page.bringToFront();
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toHaveCount(0);
  await expect(page.getByText('Star a stock to add it here')).toBeVisible();
  await other.close();
});

test('storage failure has a real retry path', async ({ page }) => {
  await page.route('**/api/watchlist', route => route.request().method() === 'GET' ? route.fulfill({ status: 503, json: { detail: { code: 'ACCOUNT_STORAGE_UNAVAILABLE' } } }) : route.continue());
  await page.goto('/#/analysis');
  await signIn(page);
  await expect(page.getByRole('alert')).toContainText('Your watchlist is unavailable. Try again.');
  await page.unroute('**/api/watchlist');
  await page.getByRole('button', { name: 'Retry watchlist' }).click();
  await expect(page.getByText('Star a stock to add it here')).toBeVisible();
});

test('expired Auth0 proof cannot establish an app session', async ({ page, request }) => {
  const expired = await token(request, 'alice', true);
  await page.route('**/api/test/identity?user=alice', route => route.fulfill({ json: { access_token: expired } }));
  await page.goto('/#/analysis');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await expect(page.getByRole('alert')).toContainText('Could not restore your session. Sign in again.');
  await page.unroute('**/api/test/identity?user=alice');
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await page.getByRole('link', { name: 'Analysis', exact: true }).click();
  await expect(page.getByText('Star a stock to add it here')).toBeVisible();
});

test('mobile account and saved-stock actions fit the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/#/analysis');
  await signIn(page);
  await page.getByRole('button', { name: 'Watchlist for AAPL', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Watchlist for AAPL' })).toBeVisible();
  await page.getByRole('button', { name: 'Open navigation' }).click();
  await page.getByRole('link', { name: 'Watchlist', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  if (process.env.STOCKSIGHT_VISUAL_QA === '1') await page.screenshot({ path: '../.local-data/accounts-mobile.png', fullPage: true });
});

test('mobile watchlist chips stay in one scrollable row and open the chosen stock', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  const symbols = ['MSFT', 'AMD', 'AMZN', 'NVDA', 'ORCL', 'AAPL'];
  await page.route('**/api/watchlist', route => route.request().method() === 'GET' ? route.fulfill({
    json: { items: symbols.map((symbol, index) => ({
      symbol, name: symbol, daily_change_pct: index === 1 ? null : index === 0 ? 1.25 : -0.12,
    })) },
  }) : route.continue());
  await page.goto('/#/analysis?symbol=MSFT');
  await signIn(page);
  const row = page.getByRole('list', { name: 'Saved stocks' });
  await expect(row.getByRole('link')).toHaveCount(symbols.length);
  await expect(row.getByRole('link', { name: /Open MSFT/ }).locator('.positive')).toHaveText('+1.25%');
  await expect(row.getByRole('link', { name: /Open AMD.*unavailable/ })).toContainText('—');
  expect(await row.evaluate(element => ({
    overflow: element.scrollWidth > element.clientWidth,
    rows: new Set([...element.children].map(chip => chip.offsetTop)).size,
  }))).toEqual({ overflow: true, rows: 1 });
  await row.getByRole('link', { name: /Open AAPL/ }).click();
  await expect(page.getByRole('heading', { name: 'AAPL Apple Inc.' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
});

test('official Auth0 SDK sends Google directly to authorization with PKCE', async ({ page }) => {
  let authorization;
  await page.route('https://e2e.auth0.test/authorize**', route => {
    authorization = new URL(route.request().url());
    return route.fulfill({ contentType: 'text/html', body: '<p>Test authorization boundary reached.</p>' });
  });
  // This server uses the actual Auth0 React SDK, without the test alias.
  await page.goto('http://127.0.0.1:5176');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await page.getByRole('button', { name: 'Continue with Google' }).click();
  await expect(page.getByText('Test authorization boundary reached.')).toBeVisible();
  expect(authorization.searchParams.get('audience')).toBe('https://stocksight-test-api');
  expect(authorization.searchParams.get('connection')).toBe('google-oauth2');
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

test('dashboard filters persisted stocks and opens analysis after refresh', async ({ page }) => {
  await page.goto('/#/analysis');
  await signIn(page);
  await page.getByRole('button', { name: 'Watchlist for AAPL', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  await page.getByRole('link', { name: 'Watchlist', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Watchlist', exact: true })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Your saved stocks' })).toBeVisible();
  await page.getByLabel('Filter saved stocks').fill('no-match');
  await expect(page.getByText('No saved stocks match “no-match”.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear filter' }).click();
  await page.getByLabel('Filter saved stocks').fill('apple');
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('table', { name: 'Your saved stocks' })).toBeVisible();
  await page.getByRole('link', { name: 'Open AAPL analysis' }).click();
  await expect(page.getByRole('heading', { name: 'AAPL Apple Inc.' })).toBeVisible();
  await page.getByRole('link', { name: 'Watchlist', exact: true }).click();
  await page.getByRole('button', { name: 'Remove AAPL' }).click();
  await expect(page.getByText('No saved stocks yet.')).toBeVisible();
  await page.reload();
  await expect(page.getByText('No saved stocks yet.')).toBeVisible();
});

test('dashboard loading, storage retry and sign-out preserve privacy', async ({ page }) => {
  await page.goto('/#/dashboard');
  await signIn(page);
  await page.getByRole('link', { name: 'Explore stocks', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Explore stocks', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Watchlist for AAPL', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Watchlist for AAPL', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.route('**/api/watchlist', route => route.request().method() === 'GET' ? route.fulfill({ status: 503, json: { detail: { code: 'ACCOUNT_STORAGE_UNAVAILABLE' } } }) : route.continue());
  await page.goto('/#/dashboard');
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Your watchlist is unavailable');
  await page.unroute('**/api/watchlist');
  await page.getByRole('button', { name: 'Retry watchlist' }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Open AAPL analysis' })).toHaveCount(0);
  await expect(page.getByText('Sign in to keep your saved stocks here.')).toBeVisible();
});
