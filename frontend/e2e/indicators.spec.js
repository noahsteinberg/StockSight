import { test, expect } from '@playwright/test';

const indicatorURL = '**/api/stocks/*/indicators?*';
const latest = page => page.getByText(/As of.*2017-02-16/);

test('real indicator API renders overlays and keeps values stable across ranges', async ({ page }) => {
  await page.goto('/');
  await expect(latest(page)).toContainText('63 sessions');
  const response = page.waitForResponse(value => value.url().includes('/indicators?range=3mo'));
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  const data = await (await response).json();
  const last = data.points.at(-1);
  await expect(page.locator('.indicator-values')).toContainText(new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(last.sma_20));
  await page.getByRole('button', { name: 'RSI 14', exact: true }).click();
  await expect(page.getByRole('img', { name: /relative strength index/ })).toBeVisible();
  await expect(page.locator('.indicator-values')).toContainText(last.rsi_14.toFixed(2));
  await page.getByRole('button', { name: '1M', exact: true }).click();
  await expect(latest(page)).toContainText('21 sessions');
  await expect(page.locator('.indicator-values')).toContainText(last.rsi_14.toFixed(2));
  await expect(page.locator('.sma-line')).toBeVisible();
  await page.getByRole('button', { name: 'RSI 14', exact: true }).click();
  await expect(page.getByRole('img', { name: /relative strength index/ })).toHaveCount(0);
});

test('indicator failure retries independently while preserving the chart', async ({ page }) => {
  await page.route(indicatorURL, route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Indicators are unavailable');
  await expect(page.getByRole('img', { name: /Closing price/ })).toBeVisible();
  await page.unroute(indicatorURL);
  await page.getByRole('button', { name: 'Retry indicators' }).click();
  await expect(page.locator('.sma-line')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('mismatched snapshot cannot overlay unrelated indicators', async ({ page }) => {
  await page.route(indicatorURL, async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.points[0].date = '1900-01-01';
    await route.fulfill({ json: data });
  });
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('dates or sources differ');
  await expect(page.locator('.sma-line')).toHaveCount(0);
  await expect(page.getByRole('img', { name: /Closing price/ })).toBeVisible();
  await page.unroute(indicatorURL);
  await page.getByRole('button', { name: 'Reload prices & indicators' }).click();
  await expect(page.locator('.sma-line')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('null warm-up values stay unavailable and date selection updates indicator values', async ({ page }) => {
  await page.route(indicatorURL, async route => {
    const response = await route.fetch();
    const data = await response.json();
    data.points[0].sma_20 = null;
    data.points[0].rsi_14 = null;
    await route.fulfill({ json: data });
  });
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await page.getByRole('button', { name: 'RSI 14', exact: true }).click();
  await expect(page.locator('.sma-line')).toBeVisible();
  await page.getByRole('slider').focus();
  await page.getByRole('slider').press('Home');
  await expect(page.locator('.indicator-values')).toContainText('20 observations required');
  await expect(page.locator('.indicator-values')).toContainText('15 observations required');
  await page.getByRole('button', { name: '1M', exact: true }).click();
  await expect(page.getByRole('slider')).toHaveAttribute('aria-valuetext', '2017-02-16, $135.35');
});

test('superseded indicator requests cannot replace the current range', async ({ page }) => {
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  let started;
  const waiting = new Promise(resolve => { started = resolve; });
  await page.route('**/indicators?range=3mo', () => started());
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await waiting;
  await page.getByRole('button', { name: '1Y', exact: true }).click();
  await expect(latest(page)).toContainText('252 sessions');
  await expect(page.locator('.sma-line')).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('short histories retain nulls without drawing fabricated indicator lines', async ({ page }) => {
  await page.route('**/api/stocks/*/prices?*', async route => {
    const data = await (await route.fetch()).json();
    await route.fulfill({ json: { ...data, bars: data.bars.slice(-10) } });
  });
  await page.route(indicatorURL, async route => {
    const data = await (await route.fetch()).json();
    await route.fulfill({ json: { ...data, points: data.points.slice(-10).map(point => ({ ...point, sma_20: null, rsi_14: null })) } });
  });
  await page.goto('/');
  await expect(latest(page)).toContainText('10 sessions');
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await page.getByRole('button', { name: 'RSI 14', exact: true }).click();
  await expect(page.locator('.indicator-values')).toContainText('20 observations required');
  await expect(page.locator('.indicator-values')).toContainText('15 observations required');
  await expect(page.locator('.sma-line')).toHaveAttribute('d', /^\s*$/);
  await expect(page.locator('.rsi-line')).toHaveAttribute('d', /^\s*$/);
});

test('indicator timeout recovers without reloading prices', async ({ page }) => {
  await page.clock.install();
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  let started;
  const waiting = new Promise(resolve => { started = resolve; });
  await page.route(indicatorURL, () => started());
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await waiting;
  await page.clock.runFor(10001);
  await expect(page.getByRole('alert')).toContainText('Indicators timed out');
  await expect(page.getByRole('img', { name: /Closing price/ })).toBeVisible();
  await page.unroute(indicatorURL);
  await page.getByRole('button', { name: 'Retry indicators' }).click();
  await expect(page.locator('.sma-line')).toBeVisible();
});

test('desktop and mobile research workspace remain readable with indicators enabled', async ({ page }) => {
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await page.getByRole('button', { name: 'RSI 14', exact: true }).click();
  await expect(page.getByRole('img', { name: /relative strength index/ })).toBeVisible();
  for (const [label, width, height] of [['desktop', 1440, 1040], ['mobile', 390, 844], ['small-mobile', 320, 740]]) {
    await page.setViewportSize({ width, height });
    await expect.poll(() => page.locator('.price-plot').evaluate(element => Math.abs(element.viewBox.baseVal.width - element.getBoundingClientRect().width))).toBeLessThan(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `../.local-data/redesign-${label}.png`, fullPage: true });
  }
});
