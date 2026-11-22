import { test, expect } from '@playwright/test';

test('navigation supports refresh, browser history, active state and page focus', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Stock analysis', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My dashboard' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('main')).toBeFocused();
  await page.getByRole('link', { name: 'Predictions', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Predictions', exact: true })).toBeVisible();
  await page.reload();
  await expect(page).toHaveTitle('Predictions | StockSight');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'My dashboard' })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading', { name: 'Predictions', exact: true })).toBeVisible();
});

test('predictions preserve stock context and never call an absent ML service', async ({ page }) => {
  const calls = [];
  page.on('request', request => { if (/\/api\/(predictions|evaluation|performance)/.test(request.url())) calls.push(request.url()); });
  await page.goto('/#/analysis?symbol=AAPL');
  await page.getByRole('link', { name: 'Predictions for AAPL' }).click();
  await expect(page.getByRole('heading', { name: 'AAPL', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Generate prediction' })).toBeDisabled();
  await expect(page.getByText('Prediction history is unavailable', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Model performance', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'No evaluated model is available' })).toBeVisible();
  expect(calls).toEqual([]);
});

test('methodology and legacy links resolve; unknown pages recover', async ({ page }) => {
  await page.goto('/#project');
  await expect(page.getByRole('heading', { name: 'Data & methodology', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Historical data' })).toBeVisible();
  await page.goto('/#watchlist');
  await expect(page.getByRole('heading', { name: 'My dashboard' })).toBeVisible();
  await page.goto('/#/does-not-exist');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await page.getByRole('link', { name: 'Go to stock analysis' }).click();
  await expect(page.getByRole('heading', { name: 'Stock analysis', exact: true })).toBeVisible();
});

test('skip link focuses the current page without changing routes', async ({ page }) => {
  await page.goto('/#/performance');
  await page.getByRole('link', { name: 'Skip to content' }).focus();
  await page.getByRole('link', { name: 'Skip to content' }).press('Enter');
  await expect(page.locator('main')).toBeFocused();
  await expect(page).toHaveURL(/#\/performance$/);
});

test('deep-linked prediction symbol survives refresh and opens its analysis', async ({ page }) => {
  await page.goto('/#/predictions?symbol=MSFT');
  await expect(page.getByRole('heading', { name: 'MSFT', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'MSFT', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'View MSFT analysis' }).click();
  await expect(page.getByLabel('Ticker', { exact: true })).toHaveValue('MSFT');
  await expect(page.getByRole('alert')).toContainText('Symbol unavailable');
});

test('navigation remembers the stock selected through browser history', async ({ page }) => {
  await page.goto('/#/predictions?symbol=AAPL');
  await page.goto('/#/predictions?symbol=MSFT');
  await expect(page.getByRole('heading', { name: 'MSFT', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await page.getByRole('link', { name: 'Analysis', exact: true }).click();
  await expect(page.getByLabel('Ticker', { exact: true })).toHaveValue('MSFT');
});

test('new pages fit desktop and mobile viewports', async ({ page }) => {
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [route, heading] of [['dashboard', 'My dashboard'], ['predictions', 'Predictions'], ['performance', 'Model performance'], ['methodology', 'Data & methodology']]) {
      await page.goto(`/#/${route}`);
      await expect(page.getByRole('heading', { level: 1, name: heading, exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (width !== 320) await page.screenshot({ path: `../.local-data/pages-${route}-${width}.png`, fullPage: true });
    }
  }
});

test('compact navigation reveals the active tab on a mobile deep link', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto('/#/methodology');
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  const active = nav.getByRole('link', { name: 'Methodology', exact: true });
  await expect(active).toHaveAttribute('aria-current', 'page');
  await expect.poll(() => active.evaluate(element => {
    const tab = element.getBoundingClientRect();
    const container = element.closest('nav').getBoundingClientRect();
    return tab.left >= container.left && tab.right <= container.right + 1;
  })).toBe(true);
});
