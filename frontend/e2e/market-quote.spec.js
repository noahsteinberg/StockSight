import { test, expect } from '@playwright/test';
import { tradingViewSymbol } from '../src/tradingview-symbols.js';

const vendorScript = '**/external-embedding/embed-widget-single-quote.js';
const stubWidget = `
(() => {
  if (!document.currentScript.parentElement) return;
  const config = JSON.parse(document.currentScript.textContent);
  const frame = document.createElement('iframe');
  frame.dataset.symbol = config.symbol;
  frame.style.width = '100%';
  frame.style.height = '190px';
  frame.style.border = '0';
  frame.srcdoc = '<p>Provider fixture</p>';
  document.currentScript.parentElement.appendChild(frame);
})();
`;

test('widget stays separate from history and survives range changes', async ({ page }) => {
  let loads = 0;
  await page.route(vendorScript, route => {
    loads++;
    return route.fulfill({ contentType: 'text/javascript', body: stubWidget });
  });
  await page.goto('/#/analysis');
  const panel = page.getByRole('region', { name: 'Latest market price' });
  await expect(panel.locator('iframe')).toHaveCount(1);
  await expect(panel.locator('iframe')).toHaveAttribute('data-symbol', 'NASDAQ:AAPL');
  await expect(panel.locator('iframe')).toHaveAttribute('title', 'AAPL market price from TradingView');
  await expect(panel).toContainText('prices may be delayed');
  await expect(panel).toContainText('through 2017-02-16');
  const before = loads;
  await page.getByRole('button', { name: '1Y', exact: true }).click();
  await expect(page.getByText(/As of.*2017-02-16/)).toContainText('252 sessions');
  expect(loads).toBe(before);
  await expect(panel.getByRole('link')).toHaveAttribute('href', 'https://www.tradingview.com/symbols/NASDAQ-AAPL/');
});

test('ticker changes remove old embeds, map share classes and avoid guessing listings', async ({ page }) => {
  await page.route(vendorScript, route => route.fulfill({ contentType: 'text/javascript', body: stubWidget }));
  await page.goto('/#/analysis');
  for (const [symbol, listing] of [['MSFT', 'NASDAQ:MSFT'], ['AMZN', 'NASDAQ:AMZN'], ['BRK-B', 'NYSE:BRK.B'], ['BF-B', 'NYSE:BF.B'], ['CBOE', 'CBOE:CBOE']]) {
    await page.goto(`/#/analysis?symbol=${symbol}`);
    await expect(page.locator('.market-quote iframe')).toHaveCount(1);
    await expect(page.locator('.market-quote iframe')).toHaveAttribute('data-symbol', listing);
    await expect(page.locator('.market-quote iframe')).toHaveAttribute('title', `${symbol} market price from TradingView`);
  }
  expect(tradingViewSymbol('NOT-A-LISTING')).toBe(null);
  await page.goto('/#/analysis?symbol=ZZZZ');
  await expect(page.getByText('Market widget unavailable for ZZZZ.')).toBeVisible();
  await expect(page.locator('.market-quote iframe')).toHaveCount(0);
});

test('blocked script offers a retry while history stays usable', async ({ page }) => {
  await page.route(vendorScript, route => route.abort());
  await page.goto('/#/analysis');
  await expect(page.getByText('Market widget unavailable for AAPL.')).toBeVisible();
  await expect(page.getByText(/As of.*2017-02-16/)).toBeVisible();
  await page.unroute(vendorScript);
  await page.route(vendorScript, route => route.fulfill({ contentType: 'text/javascript', body: stubWidget }));
  await page.getByRole('button', { name: 'Retry market widget' }).click();
  await expect(page.locator('.market-quote iframe')).toHaveCount(1);
  await expect(page.getByText('Market widget unavailable for AAPL.')).toHaveCount(0);
});

test('market panel and attribution fit a 320px screen', async ({ page }) => {
  await page.route(vendorScript, route => route.fulfill({ contentType: 'text/javascript', body: stubWidget }));
  await page.setViewportSize({ width: 320, height: 780 });
  await page.goto('/#/analysis');
  await expect(page.locator('.market-quote iframe')).toBeVisible();
  await expect(page.getByRole('link', { name: 'AAPL by TradingView ↗' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('replay hides the present-day quote without reloading it', async ({ page }) => {
  let loads = 0;
  await page.route(vendorScript, route => {
    loads++;
    return route.fulfill({ contentType: 'text/javascript', body: stubWidget });
  });
  await page.goto('/#/analysis');
  const panel = page.getByRole('region', { name: 'Latest market price' });
  await expect(panel.locator('iframe')).toBeVisible();
  const before = loads;
  await page.getByRole('button', { name: 'Historical replay' }).click();
  await page.getByRole('button', { name: 'Start replay' }).click();
  await expect(panel.getByText('The latest quote is hidden while you replay past sessions. Exit replay to see it.')).toBeVisible();
  await expect(panel.locator('iframe')).toBeHidden();
  await page.getByRole('button', { name: 'Exit replay' }).click();
  await expect(panel.locator('iframe')).toBeVisible();
  expect(loads).toBe(before);
});

test('Analysis shows the reviewed company name and sector', async ({ page }) => {
  await page.route(vendorScript, route => route.abort());
  await page.goto('/#/analysis');
  const context = page.locator('.stock-context');
  await expect(context).toContainText('Apple Inc.');
  await expect(context).toContainText('Information Technology · Technology Hardware, Storage & Peripherals');
  await expect(context.getByRole('link', { name: 'Sector source' })).toHaveAttribute('href', '#/methodology');
});
