import { test, expect } from '@playwright/test';

// The fixture API stores only AAPL, so comparisons use obviously synthetic TST
// responses. They exercise the UI contract; they are not market data.
const sessions = { '1mo': 21, '3mo': 63, '1y': 252, all: 300 };

function isoDay(index) {
  return new Date(Date.UTC(2025, 0, 1) + index * 86400000).toISOString().slice(0, 10);
}

function syntheticComparison(url, change = {}) {
  const params = new URL(url).searchParams;
  const symbols = params.get('symbols').split(',');
  const range = params.get('range');
  const count = sessions[range];
  const dates = Array.from({ length: count }, (_, index) => isoDay(index));
  const stocks = symbols.map((symbol, position) => {
    const slope = (position % 2 ? -1 : 1) * (position + 1) * 10;
    const indexed = dates.map((_, index) => 100 + slope * index / Math.max(1, count - 1));
    return {
      symbol, name: position === 0 ? 'Test Company A' : null, as_of: dates.at(-1), last_close: 50 + position,
      series_revision: 'e'.repeat(64), start_close: 40, end_close: 40 * indexed.at(-1) / 100,
      period_change_pct: indexed.at(-1) - 100, metric_status: 'ok', split_events: [], indexed,
    };
  });
  const body = { range, requested_sessions: count, common_sessions: count, start: dates[0], end: dates.at(-1), aligned_to_shared_cutoff: false, dates, stocks };
  return typeof change === 'function' ? change(body) : { ...body, ...change };
}

function syntheticExplore(url) {
  const params = new URL(url).searchParams;
  const page = Number(params.get('page'));
  const pageSize = Number(params.get('page_size'));
  const items = Array.from({ length: 6 }, (_, index) => ({
    symbol: `TST00${index}`, name: null, exchange: null, sector: null, sub_industry: null, last_close: 10 + index, as_of: '2025-03-01',
    daily_change_pct: 1, series_revision: 'f'.repeat(64),
  }));
  return { query: '', sector: null, page, page_size: pageSize, total_supported: 6, total_matching: 6, latest_session: '2025-03-01', items: items.slice((page - 1) * pageSize, page * pageSize) };
}

async function mockApis(page, change) {
  const requests = [];
  await page.route('**/api/explore?*', route => route.fulfill({ json: syntheticExplore(route.request().url()) }));
  await page.route('**/api/compare?*', route => {
    requests.push(new URL(route.request().url()).searchParams);
    return route.fulfill({ json: syntheticComparison(route.request().url(), change) });
  });
  return requests;
}

test('Explore selections fill the tray, persist in the tab and open a comparison', async ({ page }) => {
  const requests = await mockApis(page);
  await page.goto('/#/explore');
  const tray = page.getByRole('region', { name: 'Stocks selected for comparison' });
  await expect(tray).toHaveCount(0);
  await page.getByRole('button', { name: 'Compare TST000' }).click();
  await expect(tray).toContainText('Compare (1 of 4)');
  await expect(tray).toContainText('Add one more stock to compare');
  for (const symbol of ['TST001', 'TST002', 'TST003']) await page.getByRole('button', { name: `Compare ${symbol}` }).click();
  await expect(tray).toContainText('Compare (4 of 4)');
  await expect(page.getByRole('button', { name: 'Compare TST000' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('button', { name: 'Compare TST004' })).toBeDisabled();
  await page.reload();
  await expect(tray).toContainText('Compare (4 of 4)');
  await tray.getByRole('button', { name: 'Remove TST003 from comparison' }).click();
  await tray.getByRole('button', { name: 'Remove TST002 from comparison' }).click();
  await tray.getByRole('link', { name: 'Compare 2 stocks' }).click();
  await expect(page).toHaveURL(/#\/compare\?symbols=TST000,TST001$/);
  await expect(page.getByRole('heading', { name: 'Compare stocks', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Compare', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page).toHaveTitle('Compare | StockSight');
  expect(requests.at(-1).get('symbols')).toBe('TST000,TST001');
  expect(requests.at(-1).get('range')).toBe('1y');
  await expect(page.getByRole('img', { name: /Price change indexed to 100 from 2025-01-01/ })).toBeVisible();
  const table = page.getByRole('table', { name: /Comparison summary/ });
  await expect(table.locator('tbody tr')).toHaveCount(2);
  await expect(table.locator('tbody tr').first()).toContainText('Test Company A');
  await expect(table.locator('tbody tr').first()).toContainText('+10.00%');
  await expect(table.locator('tbody tr').nth(1)).toContainText('Name not yet available');
  await expect(table.locator('tbody tr').nth(1)).toContainText('-20.00%');
  await expect(page.getByText('Indexed to 100 on 2025-01-01. Uses the 252 trading days all selected stocks share.')).toBeVisible();
  await expect(page.getByText('Closes exclude dividends, so this is price change, not total return.')).toBeVisible();
});

test('the comparison can be edited by ticker, chip and range, all reflected in the URL', async ({ page }) => {
  const requests = await mockApis(page);
  await page.goto('/#/compare?symbols=TST000,TST001');
  await expect(page.getByRole('table', { name: /Comparison summary/ }).locator('tbody tr')).toHaveCount(2);
  const add = page.getByLabel('Add a ticker to the comparison');
  await add.fill('tst000');
  await add.press('Enter');
  await expect(page.getByRole('alert')).toContainText('TST000 is already in this comparison.');
  await add.fill('$$');
  await add.press('Enter');
  await expect(page.getByRole('alert')).toContainText('Enter a ticker symbol, such as MSFT.');
  await add.fill('tst002');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await expect(page).toHaveURL(/symbols=TST000,TST001,TST002$/);
  await expect(page.getByRole('table', { name: /Comparison summary/ }).locator('tbody tr')).toHaveCount(3);
  await page.getByRole('button', { name: '3M', exact: true }).click();
  await expect(page).toHaveURL(/symbols=TST000,TST001,TST002&range=3mo$/);
  await expect(page.getByText('Uses the 63 trading days')).toBeVisible();
  expect(requests.at(-1).get('range')).toBe('3mo');
  await page.getByRole('button', { name: 'Remove TST001 from comparison' }).click();
  await expect(page).toHaveURL(/symbols=TST000,TST002&range=3mo$/);
  await page.goBack();
  await expect(page.getByRole('table', { name: /Comparison summary/ }).locator('tbody tr')).toHaveCount(3);
  await page.goto('/#/compare?symbols=TST000');
  await expect(page.getByRole('heading', { name: 'Add at least two stocks to compare' })).toBeVisible();
  await page.goto('/#/compare?symbols=TST000,TST001,TST002,TST003,TST004');
  await expect(page.getByText('only the first 4 from the link are shown')).toBeVisible();
  await expect(page.getByRole('table', { name: /Comparison summary/ }).locator('tbody tr')).toHaveCount(4);
  expect(requests.at(-1).get('symbols')).toBe('TST000,TST001,TST002,TST003');
});

test('the chart reads values by keyboard and pointer', async ({ page }) => {
  await mockApis(page);
  await page.goto('/#/compare?symbols=TST000,TST001&range=1mo');
  const chart = page.getByRole('img', { name: /Price change indexed to 100/ });
  const readout = page.locator('.compare-readout');
  // Before any selection the readout shows the latest date, in the same space it
  // keeps while hovering, so the chart never moves under the pointer.
  await expect(readout).toContainText('2025-01-21 TST000 110.0 TST001 80.0');
  await expect(readout).toContainText('Latest');
  await page.evaluate(() => document.fonts.ready);
  const before = await chart.boundingBox();
  await chart.focus();
  await chart.press('End');
  await expect(readout).toContainText('2025-01-21 TST000 110.0 TST001 80.0');
  await chart.press('ArrowLeft');
  await expect(readout).toContainText('2025-01-20');
  await chart.press('Home');
  await expect(readout).toContainText('2025-01-01 TST000 100.0 TST001 100.0');
  expect((await chart.boundingBox()).y).toBe(before.y);
  await chart.press('Escape');
  await expect(readout).toContainText('Latest');
  const box = await chart.boundingBox();
  await page.mouse.move(box.x + box.width * .5, box.y + box.height * .5);
  await expect(readout).toContainText('2025-01-1');
  expect((await chart.boundingBox()).y).toBe(before.y);
  // The line samples stay small (a chart-wide rule used to stretch them).
  for (const swatch of await readout.locator('.series-swatch').all()) expect((await swatch.boundingBox()).width).toBeLessThanOrEqual(24);
});

test('shared cutoffs, short overlap and splits are disclosed instead of hidden', async ({ page }) => {
  await mockApis(page, body => {
    const [first, second] = body.stocks;
    return {
      ...body, requested_sessions: 252, aligned_to_shared_cutoff: true,
      stocks: [
        { ...first, as_of: '2026-01-05', split_events: [{ date: body.dates[5], ratio: 4, price_adjusted: true }] },
        { ...second, metric_status: 'split_unadjusted', period_change_pct: null, split_events: [{ date: body.dates[8], ratio: 2, price_adjusted: false }] },
      ],
    };
  });
  await page.goto('/#/compare?symbols=TST000,TST001&range=1mo');
  await expect(page.getByText('(fewer than the 252 requested, because at least one stock has a shorter stored history)')).toBeVisible();
  await expect(page.getByText('Ends on 2025-01-21, the latest date every stock has stored. TST000 has data through 2026-01-05.')).toBeVisible();
  await expect(page.getByText('TST000 split 4-for-1 on 2025-01-06. Stored prices are already split-adjusted')).toBeVisible();
  await expect(page.getByText('TST001 split 2-for-1 on 2025-01-09. Stored prices look unadjusted')).toBeVisible();
  const second = page.getByRole('table', { name: /Comparison summary/ }).locator('tbody tr').nth(1);
  await expect(second).toContainText('UnavailableSplit inside window');
});

test('too little shared history is an explicit state', async ({ page }) => {
  await mockApis(page, body => ({
    ...body, common_sessions: 0, start: null, end: null, dates: [],
    stocks: body.stocks.map(stock => ({ ...stock, indexed: [], start_close: null, end_close: null, period_change_pct: null, metric_status: 'insufficient_overlap' })),
  }));
  await page.goto('/#/compare?symbols=TST000,TST001');
  await expect(page.getByRole('heading', { name: 'These stocks can’t be compared yet' })).toBeVisible();
  await expect(page.getByRole('img', { name: /Price change indexed/ })).toHaveCount(0);
});

test('unknown symbols, storage failure and malformed data each recover', async ({ page }) => {
  let mode = 'unknown';
  await page.route('**/api/compare?*', route => {
    const url = route.request().url();
    if (mode === 'unknown' && url.includes('NOPE')) return route.fulfill({ status: 404, json: { detail: { code: 'UNSUPPORTED_SYMBOL', symbols: ['NOPE'] } } });
    if (mode === 'down') return route.fulfill({ status: 503, json: { detail: { code: 'DATA_UNAVAILABLE' } } });
    if (mode === 'broken') return route.fulfill({ json: { ...syntheticComparison(url), common_sessions: 3 } });
    return route.fulfill({ json: syntheticComparison(url) });
  });
  await page.goto('/#/compare?symbols=TST000,NOPE,TST001');
  await expect(page.getByRole('alert')).toContainText('No stored history for NOPE.');
  await page.getByRole('button', { name: 'Remove NOPE', exact: true }).click();
  await expect(page).toHaveURL(/symbols=TST000,TST001$/);
  await expect(page.getByRole('table', { name: /Comparison summary/ })).toBeVisible();
  mode = 'down';
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Stock data is temporarily unavailable. Try again.');
  mode = 'ok';
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('table', { name: /Comparison summary/ })).toBeVisible();
  mode = 'broken';
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Comparison data was incomplete. Try again.');
});

test('the real fixture API names the stock it cannot compare', async ({ page }) => {
  await page.goto('/#/compare?symbols=AAPL,MSFT');
  await expect(page.getByRole('alert')).toContainText('No stored history for MSFT.');
  await expect(page.getByRole('button', { name: 'Remove MSFT', exact: true })).toBeVisible();
});

test('Analysis and Watchlist pages can add the current stock to the comparison', async ({ page }) => {
  await page.goto('/#/analysis?symbol=AAPL');
  await page.getByRole('button', { name: 'Add AAPL to comparison' }).click();
  await expect(page.getByRole('button', { name: 'Remove AAPL from comparison' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('link', { name: /Compare \d stocks/ })).toHaveCount(0);
  await page.getByRole('link', { name: 'Dashboard', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Stocks selected for comparison' })).toContainText('AAPL');
  await expect(page.getByRole('link', { name: 'Compare', exact: true })).toHaveAttribute('href', '#/compare?symbols=AAPL');
});

test('Compare and the Explore tray fit phone and desktop widths', async ({ page }) => {
  await mockApis(page);
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/#/explore');
    await page.getByRole('button', { name: 'Compare TST000' }).click();
    await page.getByRole('button', { name: 'Compare TST001' }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('link', { name: 'Compare 2 stocks' }).click();
    await expect(page.getByRole('img', { name: /Price change indexed/ })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `../.local-data/compare-${width}.png`, fullPage: true });
    await page.evaluate(() => sessionStorage.clear());
    await page.goto('about:blank');
  }
});

test('research signals are listed separately from the price comparison', async ({ page }) => {
  await mockApis(page);
  // Synthetic TST tickers: one typed "unavailable" and one unsupported (real API 404).
  await page.route('**/api/stocks/TST000/signals?*', route => route.fulfill({ json: {
    schema_version: '1', ticker: 'TST000', status: 'unavailable', unavailable_reason: 'model_not_approved',
    message: 'No approved model signal is available.', target_kind: null, horizon_sessions: 1, as_of_session: null,
    target_session: null, published_at: null, direction: null, raw_score: null, probability: null, signal_strength: null,
    universe_percentile: null, risk_level: null, model_version: null, data_snapshot: null, provenance: null,
  } }));
  await page.goto('/#/compare?symbols=TST000,TST001');
  const panel = page.getByRole('region', { name: 'Research signals' });
  await expect(panel.getByRole('listitem').filter({ hasText: 'TST000' })).toHaveText('TST000 no approved model');
  await expect(panel.getByRole('listitem').filter({ hasText: 'TST001' })).toHaveText('TST001 not supported');
  // Shown in the chart header, so it is visible together with the chart.
  const chart = page.getByRole('img', { name: /Price change indexed to 100/ });
  expect((await panel.boundingBox()).y).toBeLessThan((await chart.boundingBox()).y);
});

test('the Add box suggests supported stocks and adds the one picked', async ({ page }) => {
  await mockApis(page);
  // Synthetic catalog for the suggestion list (the fixture API stores only AAPL).
  await page.route('**/api/stocks?limit=*', route => route.fulfill({ json: [
    { symbol: 'TST000', name: 'Test Company 0' }, { symbol: 'TST001', name: 'Test Company 1' },
    { symbol: 'TST002', name: 'Test Company 2' }, { symbol: 'TST003', name: 'Other Test Corp' },
  ] }));
  await page.goto('/#/compare?symbols=TST000,TST001');
  const add = page.getByRole('combobox', { name: 'Add a ticker to the comparison' });
  await add.focus();
  const list = page.getByRole('listbox', { name: 'Stock suggestions' });
  // Stocks already compared are left out of the list.
  await expect(list.getByRole('option')).toHaveText(['TST002Test Company 2', 'TST003Other Test Corp']);
  await add.fill('other');
  await expect(list.getByRole('option')).toHaveText(['TST003Other Test Corp']);
  await list.getByRole('option', { name: /TST003/ }).click();
  await expect(page).toHaveURL(/symbols=TST000,TST001,TST003$/);
  await expect(add).toHaveValue('');
});
