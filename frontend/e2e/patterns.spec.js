import { test, expect } from '@playwright/test';

const patternRoute = '**/api/stocks/*/patterns?*';
const panel = page => page.getByRole('region', { name: 'Historical Pattern Explorer' });

async function open(page) {
  await page.goto('/#/analysis?symbol=AAPL');
  await page.getByRole('link', { name: '21 sessions', exact: true }).click();
  await expect(page).toHaveURL(/#\/predictions\?symbol=AAPL&horizon=21$/);
  await expect(panel(page)).toContainText('12 matched periods');
}

test('Analysis links to full Predictions results with shareable horizons and clickable examples', async ({ page }) => {
  await open(page);
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /21 stored sessions/);
  await panel(page).getByRole('button', { name: '5 sessions', exact: true }).click();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
  await expect(page).toHaveURL(/horizon=5$/);
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Predictions', exact: true }).click();
  await expect(page).toHaveURL(/horizon=5$/);
  await panel(page).locator('.pattern-examples summary').click();
  await panel(page).locator('tbody button').first().click();
  await expect(panel(page).getByRole('button', { name: 'Clear highlight' })).toBeVisible();
  await expect(panel(page).locator('tr[data-highlighted=true]')).toHaveCount(1);
  await page.goBack();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /21 stored sessions/);
  await page.getByRole('link', { name: 'View AAPL analysis' }).click();
  const links = page.getByRole('region', { name: 'What happened after similar periods?' });
  await links.getByRole('link', { name: '5 sessions', exact: true }).click();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
  await page.reload();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
});

test('current-data links are hidden during historical replay', async ({ page }) => {
  await page.goto('/#/analysis?symbol=AAPL');
  await page.getByRole('button', { name: 'Historical replay', exact: true }).click();
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  await expect(page.getByRole('region', { name: 'What happened after similar periods?' })).toBeHidden();
});

test('storage errors retry, snapshot mismatch never renders outcome cards', async ({ page }) => {
  let failing = true;
  await page.route(patternRoute, route => failing ? route.fulfill({ status: 503, json: {} }) : route.continue());
  await page.goto('/#/predictions?symbol=AAPL&horizon=21');
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
  await page.unroute(patternRoute);
  await panel(page).getByRole('button', { name: 'Refresh history and matches' }).click();
  await expect(panel(page)).toContainText('12 matched periods');
});

test('unsupported history is recoverable through the standalone stock picker', async ({ page }) => {
  await page.goto('/#/predictions?symbol=NOPE&horizon=5');
  await expect(page.getByRole('alert')).toContainText('Symbol unavailable');
  await page.getByRole('combobox', { name: 'Choose a stock' }).fill('Apple');
  const option = page.getByRole('option', { name: /AAPL/ });
  await expect(option).toBeVisible();
  expect(await option.evaluate(element => {
    const rect = element.getBoundingClientRect();
    return element.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2));
  })).toBe(true);
  await page.getByRole('option', { name: /AAPL/ }).click();
  await expect(page).toHaveURL(/symbol=AAPL&horizon=5$/);
  await expect(panel(page)).toContainText('12 matched periods');
});

test('small screen keeps overflow inside the example table and supports keyboard controls', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await open(page);
  const five = panel(page).getByRole('button', { name: '5 sessions', exact: true });
  await five.focus(); await page.keyboard.press('Enter');
  await expect(five).toHaveAttribute('aria-pressed', 'true');
  await expect(five).toBeFocused();
  await expect(panel(page).getByRole('img')).toHaveAttribute('aria-label', /5 stored sessions/);
  await panel(page).locator('.pattern-examples summary').click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
