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

test('ideas follow the stock list, share dropdown styling, and page through ranks', async ({ page }) => {
  await page.route('**/api/research-ideas?*', route => {
    const params = new URL(route.request().url()).searchParams;
    const current = Number(params.get('page'));
    const method = params.get('method');
    const all = Array.from({ length: 14 }, (_, i) => ({
      symbol: `TEST${i}`, name: `Synthetic ${i}`, sector: null,
      metric_pct: method === 'momentum' ? 14 - i : i,
      as_of: '2026-11-25', series_revision: 'test-only', reason: 'Synthetic metric for pagination test.',
    }));
    return route.fulfill({ json: {
      calculation_version: 'research-ideas-v1', method, query: '', sectors: [],
      latest_session: '2026-11-25', matching_count: 14, eligible_count: 14,
      page: current, page_size: 6, items: all.slice((current - 1) * 6, current * 6),
    } });
  });
  await page.goto('/#/explore');
  const panel = page.getByRole('region', { name: 'Research ideas', exact: true });
  await expect(panel).toContainText('Showing 1–6 of 14 research candidates');
  const style = locator => locator.evaluate(element => {
    const css = getComputedStyle(element);
    return [css.fontFamily, css.fontSize, css.minHeight, css.borderRadius];
  });
  expect(await style(panel.getByLabel('Find candidates by'))).toEqual(await style(page.getByLabel('Sector')));
  const table = await page.getByRole('table').boundingBox();
  expect((await panel.boundingBox()).y).toBeGreaterThan(table.y + table.height);
  const nav = panel.getByRole('navigation', { name: 'Research idea pages' });
  await nav.getByRole('button', { name: /Next ideas/ }).click();
  await expect(panel).toContainText('Showing 7–12 of 14');
  await expect(panel).toContainText('Rank 7 by recent momentum');
  await nav.getByRole('button', { name: /Next ideas/ }).click();
  await expect(panel).toContainText('Showing 13–14 of 14');
  await expect(nav.getByRole('button', { name: /Next ideas/ })).toBeDisabled();
  await panel.getByLabel('Find candidates by').selectOption('variability');
  await expect(panel).toContainText('Showing 1–6 of 14');
  await expect(panel).toContainText('Rank 1 by lower variability');
});
