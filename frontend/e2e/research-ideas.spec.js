import { test, expect } from '@playwright/test';

test('ideas supplement the full list and use the existing comparison tray', async ({ page }) => {
  await page.goto('/#/explore');
  const panel = page.getByRole('region', { name: 'Research ideas', exact: true });
  await expect(panel.getByRole('link', { name: 'Research candidate AAPL Apple Inc.' })).toBeVisible();
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(1);
  await panel.getByLabel('Find candidates by').selectOption('variability');
  await expect(panel).toContainText('daily variability over the last 20 stored changes');
  await panel.getByRole('button', { name: 'Research idea: Compare AAPL' }).click();
  await expect(page.getByRole('region', { name: 'Stocks selected for comparison' })).toContainText('AAPL');
  await page.getByLabel('Search ticker or company').fill('NOPE');
  await expect(panel).toContainText('No candidates meet these filters');
  await expect(page.getByRole('table')).toHaveCount(0);
  await page.getByRole('button', { name: 'Reset filters' }).last().click();
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(1);
  await panel.getByRole('link', { name: 'View analysis', exact: true }).click();
  await expect(page).toHaveURL(/analysis\?symbol=AAPL/);
});

test('idea failures recover without hiding the full stock list', async ({ page }) => {
  let fail = true;
  await page.route('**/api/research-ideas?*', route => fail
    ? route.fulfill({ status: 503, json: {} }) : route.continue());
  await page.goto('/#/explore');
  const panel = page.getByRole('region', { name: 'Research ideas', exact: true });
  await expect(panel.getByRole('alert')).toContainText('temporarily unavailable');
  await expect(page.getByRole('table').locator('tbody tr')).toHaveCount(1);
  fail = false;
  await panel.getByRole('button', { name: 'Retry research ideas' }).click();
  await expect(panel.getByRole('link', { name: /Research candidate AAPL/ })).toBeVisible();
  await page.setViewportSize({ width: 320, height: 780 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
