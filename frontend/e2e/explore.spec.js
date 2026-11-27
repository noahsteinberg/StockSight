import { test, expect } from '@playwright/test';

// Mocked responses use obviously synthetic TST symbols so multi-page behaviour can
// be tested against the one-stock fixture API. They are test data, not market data.
function syntheticPage(url, total = 60) {
  const params = new URL(url).searchParams;
  const query = (params.get('query') || '').trim().toUpperCase();
  const page = Number(params.get('page'));
  const size = Number(params.get('page_size'));
  const all = Array.from({ length: total }, (_, index) => ({
    symbol: `TST${String(index).padStart(3, '0')}`,
    name: index % 2 ? null : `Test Company ${index}`,
    exchange: null,
    sector: index % 4 === 3 ? null : 'Industrials',
    sub_industry: index % 4 === 3 ? null : 'Test Sub-Industry',
    last_close: 10 + index,
    as_of: index === 1 ? '2026-11-20' : '2026-11-23',
    daily_change_pct: index === 2 ? null : (index % 3 - 1) * 1.5,
    series_revision: 'f'.repeat(64),
  }));
  const sector = params.get('sector');
  const matching = all.filter(stock => (!query || stock.symbol.includes(query)) && (!sector || stock.sector === sector));
  return { query, sector, page, page_size: size, total_supported: total, total_matching: matching.length, latest_session: '2026-11-23', items: matching.slice((page - 1) * size, page * size) };
}

async function mockExplore(page, total = 60) {
  const requests = [];
  await page.route('**/api/explore?*', route => {
    requests.push(new URL(route.request().url()).searchParams);
    return route.fulfill({ json: syntheticPage(route.request().url(), total) });
  });
  return requests;
}

const rows = page => page.getByRole('table').locator('tbody tr');

test('Explore lists the real fixture stock with its stored close', async ({ page, request }) => {
  const api = await (await request.get('/api/explore')).json();
  const aapl = api.items[0];
  await page.goto('/#/explore');
  await expect(page.getByRole('heading', { name: 'Explore stocks', exact: true })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'supported stock' })).toContainText(`1 supported stock · showing 1–1 · latest stored session ${api.latest_session}`);
  await expect(rows(page)).toHaveCount(1);
  const row = rows(page).first();
  await expect(row).toContainText('AAPL');
  await expect(row).toContainText('Apple Inc.');
  await expect(row).toContainText(`$${aapl.last_close.toFixed(2)}`);
  await expect(row).toContainText(aapl.as_of);
  await expect(page.getByRole('navigation', { name: 'Stock list pages' })).toHaveCount(0);
  await page.getByRole('link', { name: 'AAPL Apple Inc.', exact: true }).click();
  await expect(page).toHaveURL(/#\/analysis\?symbol=AAPL$/);
  await expect(page.getByLabel('Ticker', { exact: true })).toHaveValue('AAPL');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Explore stocks', exact: true })).toBeVisible();
});

test('pages through results with URL state, browser history and honest unknown values', async ({ page }) => {
  await mockExplore(page);
  await page.goto('/#/explore');
  await expect(page.getByText('60 supported stocks · showing 1–25 · latest stored session 2026-11-23')).toBeVisible();
  await expect(rows(page)).toHaveCount(25);
  const pages = page.getByRole('navigation', { name: 'Stock list pages' });
  await expect(pages).toContainText('Page 1 of 3');
  await expect(pages.getByRole('button', { name: 'Previous' })).toBeDisabled();
  await expect(rows(page).nth(0)).toContainText('Test Company 0');
  await expect(rows(page).nth(1)).toContainText('Name not yet available');
  await expect(rows(page).nth(1)).toContainText('2026-11-20 · earlier session');
  await expect(rows(page).nth(2).locator('td').nth(1)).toHaveText('—Unavailable');
  await expect(rows(page).nth(3)).toContainText('-1.50%');
  await expect(rows(page).nth(5)).toContainText('+1.50%');
  await pages.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/#\/explore\?page=2$/);
  await expect(rows(page).first()).toContainText('TST025');
  await pages.getByRole('button', { name: 'Next' }).click();
  await expect(rows(page)).toHaveCount(10);
  await expect(pages.getByRole('button', { name: 'Next' })).toBeDisabled();
  await page.goBack();
  await expect(rows(page).first()).toContainText('TST025');
  await page.reload();
  await expect(pages).toContainText('Page 2 of 3');
  await page.goto('/#/explore?page=9');
  await expect(page.getByText('Page 9 is past the end of these results.')).toBeVisible();
  await page.getByRole('button', { name: 'Go to page 3' }).click();
  await expect(rows(page).first()).toContainText('TST050');
});

test('search is debounced, keeps focus and typed text, and syncs with the URL', async ({ page }) => {
  const requests = await mockExplore(page);
  await page.goto('/#/explore?page=2');
  await expect(rows(page).first()).toContainText('TST025');
  const search = page.getByLabel('Search ticker or company');
  await search.pressSequentially('tst01 ', { delay: 40 });
  await expect(page).toHaveURL(/#\/explore\?q=tst01$/);
  await expect(search).toBeFocused();
  await expect(search).toHaveValue('tst01 ');
  await expect(page.getByText('60 supported stocks · 10 matches for “tst01” · showing 1–10')).toBeVisible();
  // One request for the initial page and one after typing paused, not one per key.
  expect(requests.filter(params => params.get('query') !== '').map(params => params.get('query'))).toEqual(['tst01']);
  await page.goBack();
  await expect(search).toHaveValue('');
  await expect(rows(page).first()).toContainText('TST025');
  await page.goForward();
  await expect(search).toHaveValue(/^tst01 ?$/);
  await page.getByRole('button', { name: 'Clear', exact: true }).click();
  await expect(page).toHaveURL(/#\/explore$/);
  await expect(search).toBeFocused();
  await expect(rows(page)).toHaveCount(25);
  await search.fill('tst05');
  await search.press('Enter');
  await expect(page).toHaveURL(/#\/explore\?q=tst05$/);
  await expect(page.getByText('10 matches for “tst05”')).toBeVisible();
});

test('changing sort retains the sector, returns to page one and follows the next page', async ({ page }) => {
  const requests = await mockExplore(page);
  await page.goto('/#/explore?sector=Industrials&page=2');
  const pages = page.getByRole('navigation', { name: 'Stock list pages' });
  await expect(pages).toContainText('Page 2 of 2');
  await page.getByLabel('Sort by').selectOption('change_desc');
  await expect(pages).toContainText('Page 1 of 2');
  await expect.poll(() => requests.at(-1).get('sort')).toBe('change_desc');
  expect(requests.at(-1).get('sector')).toBe('Industrials');
  expect(requests.at(-1).get('page')).toBe('1');
  await pages.getByRole('button', { name: 'Next' }).click();
  await expect.poll(() => requests.at(-1).get('page')).toBe('2');
  expect(requests.at(-1).get('sort')).toBe('change_desc');
  await page.reload();
  await expect(page.getByLabel('Sort by')).toHaveValue('change_desc');
  await expect(pages).toContainText('Page 2 of 2');
});

test('empty, failed and malformed responses show distinct recoverable states', async ({ page }) => {
  await mockExplore(page);
  await page.goto('/#/explore?q=zzz');
  await expect(page.getByText('No supported stocks match “zzz”. Try another ticker or company name.')).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters' }).last().click();
  await expect(rows(page)).toHaveCount(25);

  await page.unroute('**/api/explore?*');
  let failing = true;
  await page.route('**/api/explore?*', route => failing
    ? route.fulfill({ status: 503, json: { detail: { code: 'DATA_UNAVAILABLE' } } })
    : route.fulfill({ json: syntheticPage(route.request().url()) }));
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Stock data is temporarily unavailable. Try again.');
  await expect(page.getByRole('table')).toHaveCount(0);
  failing = false;
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(rows(page)).toHaveCount(25);

  await page.unroute('**/api/explore?*');
  await page.route('**/api/explore?*', route => route.fulfill({ json: { ...syntheticPage(route.request().url()), total_matching: 'many' } }));
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Stock list data was incomplete. Try again.');
});

test('a slow earlier search never replaces newer results', async ({ page }) => {
  await page.route('**/api/explore?*', async route => {
    const url = route.request().url();
    if (new URL(url).searchParams.get('query') === 'tst00') await new Promise(resolve => setTimeout(resolve, 1500));
    await route.fulfill({ json: syntheticPage(url) }).catch(() => {});
  });
  await page.goto('/#/explore?q=tst00');
  await page.goto('/#/explore?q=tst05');
  await expect(rows(page).first()).toContainText('TST050');
  await page.waitForTimeout(1800);
  await expect(rows(page).first()).toContainText('TST050');
  await expect(rows(page)).toHaveCount(10);
});

test('Explore fits phone and desktop widths without page overflow', async ({ page }) => {
  await mockExplore(page);
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/#/explore');
    await expect(rows(page)).toHaveCount(25);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // Every column, including Save, must be reachable without sideways table scrolling.
    const star = rows(page).nth(1).getByRole('button', { name: /^Compare TST/ });
    expect((await star.boundingBox()).x + (await star.boundingBox()).width).toBeLessThanOrEqual(width);
    expect(await page.locator('.explore-table').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.screenshot({ path: `../.local-data/explore-${width}.png` });
  }
});

test('filters by sector with URL state, real counts, unknown sectors and a reset', async ({ page }) => {
  const requests = await mockExplore(page, 12);
  await page.goto('/#/explore');
  const sector = page.getByLabel('Sector');
  // Counts come from the real fixture API's GET /api/sectors.
  await expect(sector.locator('option', { hasText: 'Information Technology (1)' })).toHaveCount(1);
  await expect(rows(page).nth(3)).toContainText('Sector unknown');
  await sector.selectOption('Industrials');
  await expect(page).toHaveURL(/#\/explore\?sector=Industrials$/);
  await expect(page.getByText('12 supported stocks · 9 matches in Industrials')).toBeVisible();
  expect(requests.at(-1).get('sector')).toBe('Industrials');
  await expect(rows(page)).toHaveCount(9);
  await expect(rows(page).filter({ hasText: 'Sector unknown' })).toHaveCount(0);
  await page.getByLabel('Search ticker or company').fill('TST00');
  await expect(page).toHaveURL(/#\/explore\?q=TST00&sector=Industrials$/);
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await expect(page).toHaveURL(/#\/explore$/);
  await expect(sector).toHaveValue('');
  await expect(page.getByLabel('Search ticker or company')).toHaveValue('');
  await page.goBack();
  await expect(sector).toHaveValue('Industrials');
});

test('an empty sector result is reported, not broadened', async ({ page }) => {
  await page.goto('/#/explore?sector=Energy');
  await expect(page.getByText('No supported stocks match in Energy. Try another ticker or company name, or choose All sectors.')).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
  await page.getByRole('button', { name: 'Reset filters' }).first().click();
  await expect(rows(page)).toHaveCount(1);
  await expect(rows(page).first()).toContainText('Information Technology');
  await expect(page.getByRole('link', { name: 'List of S&P 500 companies' })).toHaveAttribute('href', /oldid=1384572480/);
});
