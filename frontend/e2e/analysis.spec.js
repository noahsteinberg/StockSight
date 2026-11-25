import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const barsURL = '**/api/stocks/*/prices?*';
const latest = page => page.getByText(/As of.*2017-02-16/);
// The fixture API stores only AAPL, so suggestion tests use a catalog of real
// supported tickers (names only; no prices are involved).
const catalog = [['AAPL', 'Apple Inc.'], ['ABT', 'Abbott Laboratories'], ['ADBE', 'Adobe Inc.'], ['AMD', 'Advanced Micro Devices'],
  ['AMZN', 'Amazon'], ['AVGO', 'Broadcom'], ['BA', 'Boeing'], ['BRK-B', 'Berkshire Hathaway'], ['COST', 'Costco'],
  ['DIS', 'Walt Disney Company'], ['GOOG', 'Alphabet Inc. (Class C)'], ['GS', 'Goldman Sachs'], ['IBM', 'IBM'],
  ['INTC', 'Intel'], ['JPM', 'JPMorgan Chase'], ['META', 'Meta Platforms'], ['MSFT', 'Microsoft'], ['NFLX', 'Netflix'],
  ['NVDA', 'Nvidia'], ['ORCL', 'Oracle Corporation'], ['PLTR', 'Palantir Technologies'], ['QCOM', 'Qualcomm'],
  ['TSLA', 'Tesla, Inc.'], ['V', 'Visa Inc.'], ['WMT', 'Walmart']].map(([symbol, name]) => ({ symbol, name }));
const mockCatalog = page => page.route('**/api/stocks?limit=*', route => route.fulfill({ json: catalog }));

test('real API: ranges, keyboard inspection, and observations table', async ({ page }) => {
  await page.goto('/#/analysis');
  await expect(latest(page)).toContainText('63 sessions');
  for (const [label, count] of [['1M',21], ['1Y',252], ['Max',506]]) {
    await page.getByRole('button', { name: label, exact: true }).click();
    await expect(latest(page)).toContainText(`${count} sessions`);
  }
  const inspection = page.getByRole('group', { name: 'Inspect historical observations' });
  await inspection.press('Home');
  await expect(page.locator('.inspection-readout')).toContainText('2015-02-17$127.83');
  await page.getByText('Price observations', { exact: true }).click();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('table').getByText('2015-02-17')).toBeVisible();
});

test('blank ticker gives feedback; unsupported ticker and normalized recovery', async ({ page }) => {
  await page.goto('/#/analysis');
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
  await page.goto('/#/analysis');
  await expect(page.getByRole('alert')).toContainText('price storage is unavailable');
  await page.unroute(barsURL);
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(latest(page)).toContainText('63 sessions');
});

test('empty response has a visible empty state', async ({ page }) => {
  await page.route(barsURL, route => route.fulfill({ json: { bars: [] } }));
  await page.goto('/#/analysis');
  await expect(page.getByText('No observations in this range.')).toBeVisible();
  await expect(page.getByRole('img')).toHaveCount(0);
});

test('stalled request times out and Retry recovers', async ({ page }) => {
  await page.clock.install();
  let intercepted;
  const started = new Promise(resolve => { intercepted = resolve; });
  await page.route(barsURL, () => { intercepted(); });
  await page.goto('/#/analysis');
  await started;
  await page.clock.runFor(10001);
  await expect(page.getByRole('alert')).toContainText('Request timed out. Try again.');
  await page.unroute(barsURL);
  await page.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(latest(page)).toBeVisible();
});

test('changing range cancels an older request and keeps the latest selection', async ({ page }) => {
  await page.goto('/#/analysis');
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
  await page.goto('/#/analysis');
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
  await page.goto('/#/analysis');
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
  await page.goto('/#/analysis');
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
  await page.goto('/#/analysis');
  await expect(page.getByRole('link', { name: 'Source: Alternate historical source' })).toBeVisible();
  await expect(page.getByText(/Documented test adjustment/)).toBeVisible();
  await expect(page.getByText(/Earlier stored sessions/)).toContainText('2');
});

test('new search cancels an older pending query', async ({ page }) => {
  await page.goto('/#/analysis');
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
  await page.goto('/#/analysis');
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

test('focus lists every stock in a bounded scrolling box and typing narrows it', async ({ page }) => {
  await mockCatalog(page);
  await page.goto('/#/analysis');
  await expect(latest(page)).toBeVisible();
  const input = page.getByRole('combobox', { name: 'Ticker' });
  const list = page.getByRole('listbox', { name: 'Stock suggestions' });
  await input.fill('');
  await expect(list.getByRole('option')).toHaveCount(catalog.length);
  await expect(list.getByRole('option').first()).toContainText('AAPL');
  const box = await list.evaluate(element => ({ height: element.clientHeight, scroll: element.scrollHeight, page: innerHeight }));
  expect(box.height).toBeLessThanOrEqual(Math.min(370, box.page * .5));
  expect(box.scroll).toBeGreaterThan(box.height);
  await input.fill('MS');
  await expect(list.getByRole('option').first()).toContainText('MSFT');
  await input.fill('A');
  // Ticker prefixes rank before names that merely contain the letter.
  await expect(list.getByRole('option').first()).toContainText('AAPL');
  await expect(list.getByRole('option').nth(5)).toContainText('AVGO');
  await expect(input).toHaveAttribute('aria-autocomplete', 'list');
  await expect(input).toHaveAttribute('aria-controls', await list.getAttribute('id'));
});

test('typed company names and light typos suggest the stock for keyboard selection', async ({ page }) => {
  await mockCatalog(page);
  await page.goto('/#/analysis');
  const input = page.getByRole('combobox', { name: 'Ticker' });
  const list = page.getByRole('listbox', { name: 'Stock suggestions' });
  await input.fill('a');
  const options = list.getByRole('option');
  await expect(options.first()).toContainText('AAPL');
  await input.press('ArrowDown');
  await expect(options.first()).toHaveAttribute('aria-selected', 'true');
  await input.press('ArrowDown');
  await expect(options.nth(1)).toHaveAttribute('aria-selected', 'true');
  await input.press('ArrowUp');
  await expect(input).toHaveAttribute('aria-activedescendant', await options.first().getAttribute('id'));
  await expect(input).toBeFocused();

  await input.fill('aPLe');
  await expect(options.first()).toHaveText('AAPLApple Inc.');
  await input.press('ArrowDown');
  await expect(options.first()).toHaveAttribute('aria-selected', 'true');
  const prices = page.waitForResponse('**/api/stocks/AAPL/prices?*');
  await input.press('Enter');
  expect((await prices).status()).toBe(200);
  await expect(input).toHaveValue('AAPL');
  await expect(input).toHaveAttribute('aria-expanded', 'false');
  await expect(list).toBeHidden();
  await expect(page).toHaveURL(/#\/analysis\?symbol=AAPL$/);
  await expect(latest(page)).toBeVisible();
});

test('Escape and outside clicks dismiss suggestions and empty matches are non-selectable', async ({ page }) => {
  await mockCatalog(page);
  await page.goto('/#/analysis');
  const input = page.getByRole('combobox', { name: 'Ticker' });
  const list = page.getByRole('listbox', { name: 'Stock suggestions' });
  await input.fill('zzzz-not-a-stock');
  await expect(list.getByRole('option', { name: 'No matches' })).toHaveAttribute('aria-disabled', 'true');
  await input.press('ArrowDown');
  await expect(input).not.toHaveAttribute('aria-activedescendant');
  await input.press('Escape');
  await expect(input).toBeFocused();
  await expect(input).toHaveValue('zzzz-not-a-stock');
  await expect(list).toBeHidden();
  await input.fill('MICROsoft');
  await expect(list.getByRole('option', { name: /MSFT Microsoft/ })).toBeVisible();
  await page.getByRole('heading', { name: 'Stock analysis' }).click();
  await expect(list).toBeHidden();
});

test.describe('touch autocomplete', () => {
  test.use({ hasTouch: true, viewport: { width: 320, height: 720 } });

  test('tapping a suggestion fills the field and loads its symbol', async ({ page }) => {
    await page.goto('/#/analysis');
    await expect(latest(page)).toBeVisible();
    const input = page.getByRole('combobox', { name: 'Ticker' });
    await input.fill('apple');
    const option = page.getByRole('option', { name: /AAPL Apple Inc/ });
    const response = page.waitForResponse('**/api/stocks/AAPL/prices?*');
    await option.tap();
    expect((await response).status()).toBe(200);
    await expect(input).toHaveValue('AAPL');
    await expect(page.getByRole('listbox', { name: 'Stock suggestions' })).toBeHidden();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  });
});

test('hover previews a session, clicking pins it, and keyboard inspection clears cleanly', async ({ page, request }) => {
  const response = await request.get('/api/stocks/AAPL/prices?range=3mo');
  const { bars } = await response.json();
  await page.goto('/#/analysis');
  const plot = page.locator('.plot-inspection-target');
  const readout = page.locator('.inspection-readout');
  await plot.hover({ position: { x: 1, y: 20 } });
  await expect(readout).toContainText('Preview');
  await expect(readout.locator('time')).toHaveText(bars[0].date);
  await page.getByRole('heading', { name: 'Stock analysis' }).hover();
  await expect(readout).toHaveCount(0);

  await plot.click({ position: { x: 1, y: 20 } });
  await expect(readout).toContainText('Pinned');
  await page.getByRole('heading', { name: 'Stock analysis' }).hover();
  await expect(readout.locator('time')).toHaveText(bars[0].date);

  const inspection = page.getByRole('group', { name: 'Inspect historical observations' });
  await inspection.press('ArrowRight');
  await expect(readout.locator('time')).toHaveText(bars[1].date);
  const stats = page.locator('.observation-stats');
  const movement = new Intl.NumberFormat('en-US', { style: 'percent', signDisplay: 'exceptZero', maximumFractionDigits: 2 });
  await expect(stats).toContainText(movement.format(bars[1].close / bars[0].close - 1));
  await expect(stats).toContainText('1-session avg');

  await page.getByRole('button', { name: 'Latest', exact: true }).click();
  await expect(inspection).toBeFocused();
  await expect(readout).toHaveCount(0);
  await inspection.press('ArrowLeft');
  await expect(readout.locator('time')).toHaveText(bars.at(-2).date);
  await inspection.press('Escape');
  await expect(readout).toHaveCount(0);
  await expect(page.getByRole('slider')).toHaveCount(0);
});

test.describe('touch chart', () => {
  test.use({ hasTouch: true, viewport: { width: 390, height: 844 } });

  test('a tap pins a point without hovering', async ({ page }) => {
    await page.goto('/#/analysis');
    await page.locator('.plot-inspection-target').tap({ position: { x: 1, y: 20 } });
    await expect(page.locator('.inspection-readout')).toContainText('Pinned');
    await expect(page.locator('.inspection-readout time')).toHaveText('2016-11-16');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
});

test('replay reveals one session at a time across the chart, indicators, table, and CSV', async ({ page, request }) => {
  const response = await request.get('/api/stocks/AAPL/prices?range=3mo');
  const { bars } = await response.json();
  await page.goto('/#/analysis');
  const start = bars.length - 3;
  const startDate = bars[start].date;
  const nextDate = bars[start + 1].date;
  const finalDate = bars.at(-1).date;
  await page.getByRole('button', { name: 'SMA 20', exact: true }).click();
  await expect(page.locator('.sma-line')).toBeVisible();
  await page.getByRole('button', { name: 'Historical replay', exact: true }).click();
  await page.getByLabel('Start session').selectOption(String(start));
  await page.getByRole('button', { name: 'Start replay', exact: true }).click();
  const next = page.getByRole('button', { name: 'Next session' });
  await expect(next).toBeFocused();
  await expect(page.locator('.quote-date')).toContainText(startDate);
  await expect(page.locator('.volume-bar')).toHaveCount(start + 1);
  const smaBefore = await page.locator('.sma-line').getAttribute('d');

  await page.getByText('Price observations', { exact: true }).click();
  const table = page.getByRole('table');
  await expect(table.getByText(nextDate, { exact: true })).toHaveCount(0);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download price CSV' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toContain(`through-${startDate}`);
  const csv = await readFile(await download.path(), 'utf8');
  expect(csv).toContain(startDate);
  expect(csv).not.toContain(nextDate);

  await next.click();
  await expect(page.locator('.quote-date')).toContainText(nextDate);
  await expect(page.locator('.volume-bar')).toHaveCount(start + 2);
  await expect(page.locator('.sma-line')).not.toHaveAttribute('d', smaBefore);
  await expect(table.getByText(finalDate, { exact: true })).toHaveCount(0);
  await next.click();
  await expect(next).toBeDisabled();
  await expect(page.locator('.quote-date')).toContainText(finalDate);
  await page.getByRole('button', { name: 'Restart', exact: true }).click();
  await expect(page.locator('.quote-date')).toContainText(startDate);
  await page.getByRole('button', { name: 'Exit replay', exact: true }).click();
  await expect(latest(page)).toContainText('63 sessions');
});

test('CSV contains the raw OHLCV rows for the displayed range', async ({ page }) => {
  await page.goto('/#/analysis');
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
