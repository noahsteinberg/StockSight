import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const barsURL = '**/api/stocks/*/prices?*';
const latest = page => page.getByText(/As of.*2017-02-16/);

test('real API: ranges, keyboard inspection, and observations table', async ({ page }) => {
  await page.goto('/');
  await expect(latest(page)).toContainText('63 sessions');
  for (const [label, count] of [['1M',21], ['1Y',252], ['Max',506]]) {
    await page.getByRole('button', { name: label, exact: true }).click();
    await expect(latest(page)).toContainText(`${count} sessions`);
  }
  const slider = page.getByRole('slider');
  await slider.focus();
  await slider.press('Home');
  await expect(slider).toHaveAttribute('aria-valuetext', '2015-02-17, $127.83');
  await page.getByText('Price observations', { exact: true }).click();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('table').getByText('2015-02-17')).toBeVisible();
});

test('blank ticker gives feedback; unsupported ticker and normalized recovery', async ({ page }) => {
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  await page.getByLabel('Ticker', { exact: true }).fill('   ');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('Enter a ticker symbol or company name.');
  await expect(page.getByLabel('Ticker', { exact: true })).toHaveAttribute('aria-invalid','true');
  await page.getByLabel('Ticker', { exact: true }).fill('MSFT');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText(/No matching stocks/)).toBeVisible();
  await page.getByLabel('Ticker', { exact: true }).fill(' aapl ');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(latest(page)).toBeVisible();
  await page.getByRole('button', { name: 'AAPL Apple Inc.' }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('API failure recovers through Retry', async ({ page }) => {
  await page.route(barsURL, route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('price storage is unavailable');
  await page.unroute(barsURL);
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(latest(page)).toContainText('63 sessions');
});

test('empty response has a visible empty state', async ({ page }) => {
  await page.route(barsURL, route => route.fulfill({ json: { bars: [] } }));
  await page.goto('/');
  await expect(page.getByText('No observations in this range.')).toBeVisible();
  await expect(page.getByRole('img')).toHaveCount(0);
});

test('stalled request times out and Retry recovers', async ({ page }) => {
  await page.clock.install();
  let intercepted;
  const started = new Promise(resolve => { intercepted = resolve; });
  await page.route(barsURL, () => { intercepted(); });
  await page.goto('/');
  await started;
  await page.clock.runFor(10001);
  await expect(page.getByRole('alert')).toContainText('Request timed out. Try again.');
  await page.unroute(barsURL);
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(latest(page)).toBeVisible();
});

test('changing range cancels an older request and keeps the latest selection', async ({ page }) => {
  await page.goto('/');
  await expect(latest(page)).toContainText('63 sessions');
  let intercepted;
  const started = new Promise(resolve => { intercepted = resolve; });
  await page.route('**/prices?range=1mo', () => { intercepted(); });
  await page.getByRole('button', { name: '1M', exact: true }).click();
  await started;
  await page.getByRole('button', { name: '1Y', exact: true }).click();
  await expect(latest(page)).toContainText('252 sessions');
  await expect(page.getByRole('button', { name: '1Y', exact: true })).toHaveAttribute('aria-pressed','true');
});

test('mobile chart uses readable tick sizing and fits the page', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  const svg = page.getByRole('img');
  // The responsive viewBox width must follow CSS width so text is not scaled down.
  await expect.poll(async () => svg.evaluate(element => Math.abs(element.viewBox.baseVal.width - element.getBoundingClientRect().width))).toBeLessThan(2);
  const tick = svg.locator('text').first();
  expect(await tick.evaluate(element => element.getBoundingClientRect().height)).toBeGreaterThanOrEqual(10);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(latest(page)).toBeVisible();
});


test('company search selects a supported stock through the real API', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Ticker', { exact: true }).fill('apple');
  const search = page.waitForResponse(response => response.url().includes('/api/stocks?query=apple'));
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  expect((await search).status()).toBe(200);
  const history = page.waitForResponse(response => response.url().includes('/api/stocks/AAPL/prices'));
  await page.getByRole('button', { name: 'AAPL Apple Inc.' }).click();
  const data = await (await history).json();
  await expect(latest(page)).toContainText(data.source);
  await expect(latest(page)).toContainText(data.adjustment);
  await expect(page.getByRole('link', { name: `Source: ${data.source}` })).toHaveAttribute('href', data.source_url);
  await expect(page.getByRole('heading', { name: 'AAPL Apple Inc.' })).toBeVisible();
  await expect(page.getByRole('img')).toBeVisible();
});

test('search failure retries without hiding the current chart', async ({ page }) => {
  await page.route('**/api/stocks?query=*', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Could not search stocks');
  await expect(page.getByRole('img')).toBeVisible();
  await page.unroute('**/api/stocks?query=*');
  await page.getByRole('button', { name: 'Retry search', exact: true }).click();
  await expect(page.getByRole('button', { name: 'AAPL Apple Inc.' })).toBeVisible();
});

test('source labels and capped-history notice use the response', async ({ page }) => {
  await page.route(barsURL, async route => {
    const response = await route.fetch();
    const data = await response.json();
    await route.fulfill({ json: { ...data, source: 'Alternate historical source', adjustment: 'Documented test adjustment', has_earlier: true, session_limit: 2000 } });
  });
  await page.goto('/');
  await expect(page.getByRole('link', { name: 'Source: Alternate historical source' })).toBeVisible();
  await expect(page.getByText(/Documented test adjustment/)).toBeVisible();
  await expect(page.getByText(/Earlier stored sessions/)).toContainText('2');
});

test('new search cancels an older pending query', async ({ page }) => {
  await page.goto('/');
  let intercepted;
  const started = new Promise(resolve => { intercepted = resolve; });
  await page.route('**/api/stocks?query=old', () => { intercepted(); });
  await page.getByLabel('Ticker', { exact: true }).fill('old');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await started;
  await page.getByLabel('Ticker', { exact: true }).fill('apple');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByRole('button', { name: 'AAPL Apple Inc.' })).toBeVisible();
  await expect(page.getByText('Searching stocks.')).toHaveCount(0);
});

test('Escape dismisses a pending search and Clear keeps the current chart', async ({ page }) => {
  await page.goto('/');
  await expect(latest(page)).toBeVisible();
  let intercepted;
  const started = new Promise(resolve => { intercepted = resolve; });
  await page.route('**/api/stocks?query=pending', () => { intercepted(); });
  const ticker = page.getByLabel('Ticker', { exact: true });
  await ticker.fill('pending');
  await ticker.press('Enter');
  await started;
  const close = page.getByRole('button', { name: 'Close results' });
  await close.focus();
  await close.press('Escape');
  await expect(close).toHaveCount(0);
  await expect(ticker).toBeFocused();
  await page.getByRole('button', { name: 'Clear stock search' }).click();
  await expect(ticker).toHaveValue('');
  await expect(ticker).toBeFocused();
  await expect(latest(page)).toBeVisible();
});

test('the plot and session buttons inspect the same observations as the slider', async ({ page }) => {
  await page.goto('/');
  const slider = page.getByRole('slider');
  await expect(slider).toHaveAttribute('aria-valuetext', /^2017-02-16,/);
  await page.getByRole('button', { name: 'Previous session' }).click();
  await expect(slider).toHaveAttribute('aria-valuetext', /^2017-02-15,/);
  const next = page.getByRole('button', { name: 'Next session' });
  await next.press('Enter');
  await expect(next).toBeFocused();
  await expect(page.getByText('Latest stored close', { exact: false })).toBeVisible();

  const plot = page.locator('.plot-inspection-target');
  await plot.click({ position: { x: 1, y: 20 } });
  await expect(slider).toHaveValue('0');
  await expect(page.getByRole('button', { name: 'Previous session' })).toBeDisabled();
  await page.getByRole('button', { name: 'Latest', exact: true }).click();
  await expect(slider).toHaveValue('62');
  await expect(next).toBeDisabled();
});

test('CSV contains the raw OHLCV rows for the displayed range', async ({ page }) => {
  await page.goto('/');
  const response = page.waitForResponse('**/prices?range=1mo');
  await page.getByRole('button', { name: '1M', exact: true }).click();
  const { bars } = await (await response).json();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download price CSV' }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe('AAPL-historical-prices-1mo.csv');
  const contents = await readFile(await file.path(), 'utf8');
  expect(contents.split('\r\n')).toEqual([
    'Date,Open (USD),High (USD),Low (USD),Close (USD),Volume',
    ...bars.map(bar => [bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume].join(',')),
  ]);
});
