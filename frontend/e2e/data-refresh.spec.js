import { test, expect } from '@playwright/test';

test('Refresh data reloads stored bars and indicators with matching dates', async ({ page }) => {
  let refreshed = false;
  let historyCalls = 0;
  const newDate = '2017-02-17';
  await page.route('**/api/stocks/AAPL/prices?*', async route => {
    historyCalls++;
    const response = await route.fetch();
    const data = await response.json();
    if (refreshed) {
      data.bars = [...data.bars.slice(1), { ...data.bars.at(-1), date: newDate, close: 136 }];
      Object.assign(data, { as_of: newDate, snapshot_id: 'test-refreshed-snapshot', mode: 'daily_history',
        last_refreshed_at: '2017-02-18T06:17:00Z', source: 'Yahoo test fixture' });
    }
    await route.fulfill({ response, json: data });
  });
  await page.route('**/api/stocks/AAPL/indicators?*', async route => {
    const response = await route.fetch();
    const data = await response.json();
    if (refreshed) {
      data.points = [...data.points.slice(1), { ...data.points.at(-1), date: newDate }];
      Object.assign(data, { as_of: newDate, snapshot_id: 'test-refreshed-snapshot', mode: 'daily_history',
        last_refreshed_at: '2017-02-18T06:17:00Z', source: 'Yahoo test fixture' });
    }
    await route.fulfill({ response, json: data });
  });
  await page.goto('/#/analysis?symbol=AAPL');
  await expect(page.getByText(/As of.*2017-02-16/)).toBeVisible();
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await expect(page.getByText('Loading indicators…')).toHaveCount(0);
  const before = historyCalls;
  refreshed = true;
  await page.getByRole('button', { name: 'Refresh data', exact: true }).click();
  await expect(page.getByText(/As of.*2017-02-17/)).toBeVisible();
  await expect(page.getByText('Prices and indicators came from different data snapshots. Reload both to continue.')).toHaveCount(0);
  await expect(page.getByText(/Stored data updated/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'SMA 20', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect(historyCalls).toBeGreaterThan(before);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download price CSV' }).click();
  expect((await download).suggestedFilename()).toContain('AAPL');
});
