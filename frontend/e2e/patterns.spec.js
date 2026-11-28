import { test, expect } from '@playwright/test';

const panel = page => page.getByRole('region', { name: 'Historical Pattern Explorer' });
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: 'wait' });
});
async function open(page) {
  await page.goto('/#/analysis?symbol=AAPL');
  const details = page.locator('.analysis-patterns');
  await expect(details).not.toHaveAttribute('open', '');
  await details.locator('summary').click();
  await expect(panel(page)).toContainText('12 matched periods');
}

test('patterns expand within Analysis, retain horizon and highlight examples', async ({ page }) => {
  await open(page);
  await expect(page).toHaveURL(/analysis.*patterns=1/);
  const five = panel(page).getByRole('button', { name: '5 sessions', exact: true });
  await five.click();
  await expect(five).toHaveAttribute('aria-pressed', 'true');
  await expect(five).toBeFocused();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
  await panel(page).locator('.pattern-examples summary').click();
  await panel(page).locator('tbody button').first().click();
  await expect(panel(page).getByRole('button', { name: 'Clear highlight' })).toBeVisible();
  await expect(panel(page).locator('tr[data-highlighted=true]')).toHaveCount(1);
  await page.reload();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
  await page.goto('/#/predictions?symbol=AAPL&horizon=21');
  await expect(page).toHaveURL(/analysis.*horizon=21.*patterns=1/);
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /21 stored sessions/);
});

test('replay hides current patterns; an unavailable horizon offers an explicit switch', async ({ page }) => {
  await page.goto('/#/analysis?symbol=AAPL');
  await page.getByRole('button', { name: 'Historical replay', exact: true }).click();
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  await expect(page.locator('.analysis-patterns')).toHaveCount(0);
  await page.getByRole('button', { name: 'Exit replay', exact: true }).click();
  await page.route('**/api/stocks/*/patterns?*', async route => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ json: { ...body, status: 'unavailable', reason: 'insufficient_history',
      matched_count: 0, summary: null, points: [], matches: [] } });
  });
  await page.goto('/#/analysis?symbol=AAPL&horizon=21&patterns=1');
  await expect(panel(page)).toContainText('too few stored sessions');
  const nextHorizon = page.waitForResponse(response => response.url().includes('/patterns?horizon_sessions=5'));
  await panel(page).getByRole('button', { name: 'Try 5 sessions' }).click();
  await nextHorizon;
  await expect(page).toHaveURL(/horizon=5/);
});

test('storage errors retry and mismatched snapshots hide results', async ({ page }) => {
  let failing = true;
  await page.route('**/api/stocks/*/patterns?*', route => failing
    ? route.fulfill({ status: 503, json: {} }) : route.continue());
  await page.goto('/#/analysis?symbol=AAPL&patterns=1');
  await expect(panel(page).getByRole('alert')).toContainText('temporarily unavailable');
  failing = false;
  await panel(page).getByRole('button', { name: 'Retry patterns' }).click();
  await expect(panel(page)).toContainText('12 matched periods');
  await page.unroute('**/api/stocks/*/patterns?*');
  await page.route('**/api/stocks/*/patterns?*', async route => {
    const response = await route.fetch();
    await route.fulfill({ json: { ...await response.json(), snapshot_id: 'changed-test-only' } });
  });
  await panel(page).getByRole('button', { name: 'Refresh matches' }).click();
  await expect(panel(page).getByRole('alert')).toContainText('stored history changed');
  await expect(panel(page).locator('.pattern-summary')).toHaveCount(0);
  await page.unroute('**/api/stocks/*/patterns?*');
  await panel(page).getByRole('button', { name: 'Refresh history and matches' }).click();
  await expect(panel(page)).toContainText('12 matched periods');
});

test('model stock picker is clickable beyond its panel', async ({ page }) => {
  await page.goto('/#/predictions?symbol=NOPE');
  const search = page.getByRole('combobox', { name: 'Choose a stock' });
  await search.fill('Apple');
  const option = page.getByRole('option', { name: /AAPL/ });
  await expect(option).toBeVisible();
  expect(await option.evaluate(element => {
    const r = element.getBoundingClientRect();
    return element.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
  })).toBe(true);
  await option.click();
  await expect(page.getByRole('heading', { name: 'AAPL', exact: true })).toBeVisible();
  await expect(page.getByText('No approved model signal is available.', { exact: true })).toBeVisible();
});

test('phone layout keeps patterns and examples inside the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await open(page);
  await panel(page).locator('.pattern-examples summary').click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
