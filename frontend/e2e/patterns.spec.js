import { test, expect } from '@playwright/test';

const patternRoute = '**/api/stocks/*/patterns?*';
const panel = page => page.getByRole('region', { name: 'Historical Pattern Explorer' });

async function open(page) {
  await page.goto('/#/analysis?symbol=AAPL');
  await panel(page).getByRole('button', { name: 'Find similar periods' }).click();
  await expect(panel(page)).toContainText('12 matched periods');
}

test('real fixture examples switch horizons, highlight and hide during replay', async ({ page }) => {
  await open(page);
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /21 stored sessions/);
  await panel(page).getByRole('button', { name: '5 sessions', exact: true }).click();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
  await panel(page).locator('.pattern-examples summary').click();
  await panel(page).locator('tbody button').first().click();
  await expect(panel(page).getByRole('button', { name: 'Clear highlight' })).toBeVisible();
  await expect(panel(page).locator('tr[data-highlighted=true]')).toHaveCount(1);
  await page.getByRole('button', { name: 'Historical replay', exact: true }).click();
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  await expect(panel(page)).toBeHidden();
});

test('storage errors retry, snapshot mismatch never renders outcome cards', async ({ page }) => {
  let failing = true;
  await page.route(patternRoute, route => failing ? route.fulfill({ status: 503, json: {} }) : route.continue());
  await page.goto('/#/analysis?symbol=AAPL');
  await panel(page).getByRole('button', { name: 'Find similar periods' }).click();
  await expect(panel(page).getByRole('alert')).toContainText('temporarily unavailable');
  failing = false;
  await panel(page).getByRole('button', { name: 'Retry patterns' }).click();
  await expect(panel(page)).toContainText('12 matched periods');
  await page.unroute(patternRoute);
  await page.route(patternRoute, async route => {
    const response = await route.fetch();
    await route.fulfill({ json: { ...await response.json(), snapshot_id: 'changed-test-only' } });
  });
  await panel(page).getByRole('button', { name: 'Refresh matches' }).click();
  await expect(panel(page).getByRole('alert')).toContainText('stored history changed');
  await expect(panel(page).locator('.pattern-summary')).toHaveCount(0);
});

test('small screen keeps overflow inside the example table and supports keyboard controls', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await open(page);
  const five = panel(page).getByRole('button', { name: '5 sessions', exact: true });
  await five.focus(); await page.keyboard.press('Enter');
  await expect(five).toHaveAttribute('aria-pressed', 'true');
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
  await panel(page).locator('.pattern-examples summary').click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
