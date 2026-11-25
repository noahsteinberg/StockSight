import { test, expect } from '@playwright/test';

// Runs in the accounts suite: a TEST-ONLY token issuer and a migrated SQLite backend.
async function token(request, user = 'alice') {
  return (await (await request.get(`/api/test/identity?user=${user}&expired=false`)).json()).access_token;
}

async function signIn(page) {
  const hash = new URL(page.url()).hash;
  await page.getByRole('button', { name: 'Sign in', exact: true }).first().click();
  await page.getByRole('button', { name: 'Continue with Google', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
  await page.evaluate(value => { window.location.hash = value; }, hash);
}

test.beforeEach(async ({ request }) => {
  for (const user of ['alice', 'bob']) {
    await request.delete('/api/me/preferences', { headers: { Authorization: `Bearer ${await token(request, user)}` } });
  }
});

test('guests can browse; preferences and matching need an account', async ({ page }) => {
  await page.goto('/#/preferences');
  await expect(page.getByRole('heading', { name: 'Research preferences' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Sign in to save preferences' })).toBeVisible();
  await page.goto('/#/explore?mine=1');
  await expect(page.getByText('Sign in to list stocks that match your saved preferences.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Use my preferences' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Show all stocks' }).click();
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(1);
});

test('save, explained matches, default range, reload persistence and reset', async ({ page }) => {
  await page.goto('/#/dashboard');
  await signIn(page);
  const invite = page.getByRole('complementary', { name: 'Optional: set research preferences' });
  await expect(invite).toBeVisible();
  await invite.getByRole('button', { name: 'Not now' }).click();
  await expect(invite).toHaveCount(0);
  await page.getByRole('link', { name: 'Preferences', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Research preferences' })).toBeVisible();
  await page.getByLabel('Compare choices').check();
  await page.getByLabel('Information Technology').check();
  await page.getByLabel('Months').check();
  await page.getByRole('radio', { name: '1Y', exact: true }).check();
  const fluctuation = page.getByRole('group', { name: 'Which historical fluctuation level would you like to explore?' });
  await expect(fluctuation).toHaveAttribute('disabled', '');
  await expect(fluctuation).toContainText('Unavailable until a reviewed measure of past price variability exists.');
  const saved = page.waitForResponse(response => response.url().endsWith('/api/me/preferences') && response.request().method() === 'PUT');
  await page.getByRole('button', { name: 'Save preferences' }).click();
  expect((await saved).status()).toBe(200);
  await expect(page.getByRole('status').filter({ hasText: 'Preferences saved.' })).toBeVisible();
  await page.getByRole('link', { name: 'See matching stocks ↗' }).click();
  await expect(page).toHaveURL(/#\/explore\?mine=1$/);
  await expect(page.getByRole('button', { name: 'Use my preferences' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByText(/1 stock matches your sectors \(Information Technology\)/)).toBeVisible();
  await expect(page.getByRole('table').locator('tbody tr').first()).toContainText('Matches your selected sector: Information Technology');
  await expect(page.getByLabel('Sector')).toBeDisabled();
  // The saved default chart window applies until a range is picked on the page.
  await page.goto('/#/analysis?symbol=AAPL');
  await expect(page.getByRole('button', { name: '1Y', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '3M', exact: true }).click();
  await expect(page.getByRole('button', { name: '3M', exact: true })).toHaveAttribute('aria-pressed', 'true');
  // Preferences live on the server, not in browser storage.
  expect(await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }))).not.toContain('Information Technology');
  await page.goto('/#/preferences');
  await page.reload();
  await expect(page.getByLabel('Information Technology')).toBeChecked();
  await expect(page.getByLabel('Compare choices')).toBeChecked();
  await page.getByRole('button', { name: 'Reset preferences' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Preferences reset.' })).toBeVisible();
  await expect(page.getByLabel('Information Technology')).not.toBeChecked();
  await page.goto('/#/explore?mine=1');
  await expect(page.getByText('You haven’t chosen any sectors yet, so nothing can match.')).toBeVisible();
  await page.goto('/#/analysis?symbol=AAPL');
  await expect(page.getByRole('button', { name: '3M', exact: true })).toHaveAttribute('aria-pressed', 'true');
});

test('another account never sees the first account’s preferences or matches', async ({ page, request }) => {
  const alice = await token(request, 'alice');
  const response = await request.put('/api/me/preferences', {
    headers: { Authorization: `Bearer ${alice}` },
    data: { purpose: 'learn', sectors: ['Information Technology'], horizon: null, default_range: '1mo' },
  });
  expect(response.status()).toBe(200);
  await page.addInitScript(() => sessionStorage.setItem('stocksight:e2e-next-user', 'bob'));
  await page.goto('/#/preferences');
  await signIn(page);
  await expect(page.getByText('Bob Example')).toBeVisible();
  await expect(page.getByLabel('Information Technology')).not.toBeChecked();
  await expect(page.getByRole('button', { name: 'Reset preferences' })).toHaveCount(0);
  await page.goto('/#/explore?mine=1');
  await expect(page.getByText('You haven’t chosen any sectors yet, so nothing can match.')).toBeVisible();
  await page.goto('/#/analysis?symbol=AAPL');
  await expect(page.getByRole('button', { name: '3M', exact: true })).toHaveAttribute('aria-pressed', 'true');
});

test('the preferences page fits a phone without page overflow', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto('/#/preferences');
  await signIn(page);
  await expect(page.getByLabel('Information Technology')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
