import { test, expect } from '@playwright/test';

test('sidebar settings remembers chart defaults and can restore them', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/#/analysis');
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  const settings = nav.getByRole('link', { name: 'Settings', exact: true });
  const position = await settings.boundingBox();
  expect(position.height).toBe(48);
  expect(900 - (position.y + position.height)).toBeLessThan(30);
  await settings.click();
  await expect(settings).toHaveAttribute('aria-current', 'page');
  await expect(page).toHaveTitle('Settings | StockSight');
  await expect(page.locator('main')).toBeFocused();

  const sma = page.getByRole('switch', { name: 'Show SMA 20 by default' });
  const rsi = page.getByRole('switch', { name: 'Show RSI 14 by default' });
  await sma.check();
  await rsi.check();
  await page.reload();
  await expect(sma).toBeChecked();
  await expect(rsi).toBeChecked();

  const analysis = nav.getByRole('link', { name: 'Analysis', exact: true });
  const smaButton = page.getByRole('button', { name: 'SMA 20', exact: true });
  const rsiButton = page.getByRole('button', { name: 'RSI 14', exact: true });
  await analysis.click();
  await expect(smaButton).toHaveAttribute('aria-pressed', 'true');
  await expect(rsiButton).toHaveAttribute('aria-pressed', 'true');
  await smaButton.click();
  await settings.click();
  await expect(sma).toBeChecked();
  await page.getByRole('button', { name: 'Reset chart defaults' }).click();
  await analysis.click();
  await expect(smaButton).toHaveAttribute('aria-pressed', 'false');
  await expect(rsiButton).toHaveAttribute('aria-pressed', 'false');
});

test('navigation supports refresh, browser history, active state and page focus', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Dashboard', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page).toHaveTitle('Dashboard | StockSight');
  await page.getByRole('link', { name: 'Explore stocks', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Explore stocks', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Explore', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page).toHaveTitle('Explore | StockSight');
  await page.getByRole('link', { name: 'StockSight home', exact: true }).click();
  await expect(page).toHaveURL(/#\/dashboard$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Dashboard', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(page.locator('main')).toBeFocused();
  await expect(page.getByRole('link', { name: /^Predictions/ })).toHaveCount(0);
  await page.reload();
  await expect(page).toHaveTitle('Dashboard | StockSight');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Explore stocks', exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading', { level: 1, name: 'Dashboard', exact: true })).toBeVisible();
});

test('predictions preserve stock context and never call an absent ML service', async ({ page }) => {
  const calls = [];
  page.on('request', request => { if (/\/api\/(predictions|evaluation|performance)/.test(request.url())) calls.push(request.url()); });
  await page.goto('/#/analysis?symbol=AAPL');
  await page.getByRole('link', { name: 'Research signal for AAPL' }).click();
  await expect(page.getByRole('heading', { name: 'AAPL', exact: true })).toBeVisible();
  // The typed signal API answers "unavailable"; no disabled generate button remains.
  await expect(page.getByRole('region', { name: 'Research signal · AAPL' })).toContainText('No approved model signal is available.');
  await expect(page.getByRole('button', { name: 'Generate prediction' })).toHaveCount(0);
  await expect(page.getByText('Prediction history is unavailable', { exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Model performance', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'No evaluated model is available' })).toBeVisible();
  expect(calls).toEqual([]);
});

test('methodology and legacy links resolve; unknown pages recover', async ({ page }) => {
  await page.goto('/#project');
  await expect(page.getByRole('heading', { name: 'Data & methodology', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Historical data' })).toBeVisible();
  await page.goto('/#watchlist');
  await expect(page.getByRole('heading', { level: 1, name: 'Dashboard', exact: true })).toBeVisible();
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
    for (const [route, heading] of [['explore', 'Explore stocks'], ['dashboard', 'Dashboard'], ['predictions', 'Predictions'], ['performance', 'Model performance'], ['methodology', 'Data & methodology']]) {
      await page.goto(`/#/${route}`);
      await expect(page.getByRole('heading', { level: 1, name: heading, exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (width !== 320) await page.screenshot({ path: `../.local-data/pages-${route}-${width}.png`, fullPage: true });
    }
  }
});

test('the desktop rail expands from icons, resizes the content, and stays fixed on scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 600 });
  await page.goto('/#/analysis');
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  const active = nav.getByRole('link', { name: 'Analysis', exact: true });
  const label = active.locator('span');
  await expect(active).toHaveAttribute('aria-current', 'page');
  await expect(nav.locator('a svg')).toHaveCount(6);
  await expect(label).toHaveCSS('opacity', '0');
  const before = await page.locator('main').boundingBox();
  const rail = await nav.boundingBox();
  await nav.hover({ position: { x: 26, y: 30 } });
  await expect(label).toHaveCSS('opacity', '1');
  await expect.poll(async () => (await page.locator('main').boundingBox()).x).toBeGreaterThan(before.x + 100);
  await expect.poll(async () => {
    const panel = await page.locator('main').boundingBox();
    return Math.abs(panel.x + panel.width - before.x - before.width);
  }).toBeLessThan(2);
  await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'instant' }));
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
  expect((await nav.boundingBox()).y).toBe(rail.y);
  await page.mouse.move(600, 200);
  await expect(label).toHaveCSS('opacity', '0');
  await active.focus();
  await expect(label).toHaveCSS('opacity', '1');
});

async function sampleSidebarMove(nav, href) {
  return nav.evaluate(async (element, destination) => {
    const pill = element.querySelector('.sidebar-active-pill');
    const target = element.querySelector(`a[href="${destination}"]`);
    const start = pill.getBoundingClientRect().toJSON();
    const end = target.getBoundingClientRect().toJSON();
    const frames = [];
    const startTime = performance.now();
    window.location.hash = target.hash;
    await new Promise(resolve => {
      function sample() {
        const time = performance.now() - startTime;
        if (target.getAttribute('aria-current') === 'page') {
          const { top, bottom } = pill.getBoundingClientRect();
          frames.push({ top, bottom });
        }
        if (time < 650) requestAnimationFrame(sample);
        else resolve();
      }
      requestAnimationFrame(sample);
    });
    return { start, end, frames, samePill: pill === element.querySelector('.sidebar-active-pill') };
  }, href);
}

function expectPillSettled({ end, frames, samePill }) {
  expect(samePill).toBe(true);
  expect(frames.length).toBeGreaterThan(0);
  expect(Math.abs(frames.at(-1).top - end.top)).toBeLessThan(1);
  expect(Math.abs(frames.at(-1).bottom - end.bottom)).toBeLessThan(1);
}

test('the sidebar pill stretches with the bottom leading down and the top leading up', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/#/analysis?symbol=AAPL');
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await expect(nav.locator('.sidebar-active-pill')).toBeVisible();
  for (const [href, leading, trailing] of [
    ['#/methodology', 'bottom', 'top'],
    ['#/analysis?symbol=AAPL', 'top', 'bottom'],
  ]) {
    const move = await sampleSidebarMove(nav, href);
    expectPillSettled(move);
    const { start, frames } = move;
    expect(frames.some(frame =>
      Math.abs(frame[leading] - start[leading]) > Math.abs(frame[trailing] - start[trailing]) + 4,
    )).toBe(true);
    expect(frames.some(frame => frame.bottom - frame.top > start.height + 10)).toBe(true);
    await expect(nav.locator('.sidebar-active-pill')).toHaveCount(1);
  }
});

test('the sidebar pill switches instantly when reduced motion is enabled', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.goto('/#/analysis?symbol=AAPL');
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  await expect(nav.locator('.sidebar-active-pill')).toBeVisible();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const move = await sampleSidebarMove(nav, '#/methodology');
  expectPillSettled(move);
  const { end, frames } = move;
  expect(frames.every(frame => Math.abs(frame.top - end.top) < 1 && Math.abs(frame.bottom - end.bottom) < 1)).toBe(true);
  await expect(nav.getByRole('link', { name: 'Methodology', exact: true })).toHaveAttribute('aria-current', 'page');
});

test('the mobile hamburger reveals the current page, supports Escape, and closes on navigation', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto('/#/methodology');
  const nav = page.locator('#site-navigation');
  const toggle = page.getByRole('button', { name: 'Open navigation' });
  await expect(nav).toBeHidden();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.click();
  const active = nav.getByRole('link', { name: 'Methodology', exact: true });
  await expect(active).toBeFocused();
  await expect(active).toHaveAttribute('aria-current', 'page');
  await expect(active.locator('span')).toHaveCSS('opacity', '1');
  await active.press('Escape');
  await expect(nav).toBeHidden();
  await expect(toggle).toBeFocused();
  await toggle.click();
  await nav.getByRole('link', { name: 'Analysis', exact: true }).click();
  await expect(nav).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Stock analysis' })).toBeVisible();
  await expect(page.locator('main')).toBeFocused();
  await toggle.click();
  await expect(nav.getByRole('link', { name: 'Analysis', exact: true })).toHaveAttribute('aria-current', 'page');
  await page.mouse.click(317, 420);
  await expect(nav).toBeHidden();
  await toggle.click();
  await nav.getByRole('link', { name: 'Settings' }).click();
  await expect(nav).toBeHidden();
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
});
