import { test, expect } from '@playwright/test';

const signals = '**/api/stocks/*/signals?*';
const unavailable = symbol => ({
  schema_version: '1', ticker: symbol, status: 'unavailable', unavailable_reason: 'model_not_approved',
  message: 'No approved model signal is available.', target_kind: null, horizon_sessions: 1, as_of_session: null,
  target_session: null, published_at: null, direction: null, raw_score: null, probability: null, signal_strength: null,
  universe_percentile: null, risk_level: null, model_version: null, data_snapshot: null, provenance: null,
});

test('Analysis and Predictions read the real typed unavailable signal', async ({ page }) => {
  const requests = [];
  page.on('request', request => { if (request.url().includes('/signals')) requests.push(new URL(request.url())); });
  await page.goto('/#/analysis?symbol=AAPL');
  // The compact status sits in the chart header, next to the price, not below the chart.
  const compact = page.getByRole('group', { name: 'Model signal for AAPL' });
  await expect(compact).toContainText('No approved model signal is available');
  const chart = page.getByRole('img', { name: /price/i }).first();
  expect((await compact.boundingBox()).y).toBeLessThan((await chart.boundingBox()).y);
  expect(requests.at(-1).searchParams.get('horizon_sessions')).toBe('1');
  await compact.getByRole('link', { name: 'Research signal for AAPL' }).click();
  await expect(page).toHaveURL(/#\/predictions\?symbol=AAPL$/);
  await page.locator('.model-details summary').click();
  const full = page.getByRole('region', { name: 'Research signal · AAPL' });
  await expect(full).toContainText('Nothing is generated when you open this page');
  await expect(full.getByText(/\d+%/)).toHaveCount(0);
});

test('an unsupported stock shows no signal panel at all', async ({ page }) => {
  await page.goto('/#/predictions?symbol=MSFT');
  await expect(page.getByRole('heading', { name: 'MSFT', exact: true })).toBeVisible();
  await page.locator('.model-details summary').click();
  await expect(page.getByText('Prediction history is unavailable', { exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: /Research signal/ })).toHaveCount(0);
});

test('inconsistent responses are rejected and failures retry', async ({ page }) => {
  // "Unavailable" with a probability is contradictory, so nothing may render.
  await page.route(signals, route => route.fulfill({ json: { ...unavailable('AAPL'), probability: 0.5 } }));
  await page.goto('/#/predictions?symbol=AAPL');
  await page.locator('.model-details summary').click();
  const panel = page.getByRole('region', { name: 'Research signal · AAPL' });
  await expect(panel).toContainText('The signal response was incomplete or inconsistent, so nothing is shown.');
  await expect(panel).not.toContainText('50%');
  await page.unroute(signals);
  // A flag, not a one-shot counter: React StrictMode repeats the first request.
  let failing = true;
  await page.route(signals, route => failing
    ? route.fulfill({ status: 503, json: { detail: { code: 'DATA_UNAVAILABLE' } } })
    : route.continue());
  await page.reload();
  await page.locator('.model-details summary').click();
  await expect(panel).toContainText('Signal status is temporarily unavailable. Try again.');
  failing = false;
  await panel.getByRole('button', { name: 'Retry signal check' }).click();
  await expect(panel).toContainText('No approved model signal is available.');
});

test('a TEST-FIXTURE available signal renders only its validated, dated fields', async ({ page }) => {
  // Synthetic contract fixture from FRONTEND_ML_INTEGRATION_SPEC.md; the API never serves it.
  await page.route(signals, route => route.fulfill({ json: {
    ...unavailable('AAPL'), status: 'available', unavailable_reason: null, message: null, target_kind: 'relative_return',
    as_of_session: '2026-11-16', target_session: '2026-11-17', published_at: '2026-11-17T11:30:00Z', raw_score: 0.0012,
    universe_percentile: 79, model_version: 'test-fixture-only', data_snapshot: 'test-fixture-only', provenance: 'test_fixture',
  } }));
  await page.goto('/#/predictions?symbol=AAPL');
  await page.locator('.model-details summary').click();
  const panel = page.getByRole('region', { name: 'Research signal · AAPL' });
  await expect(panel).toContainText('relative return over 1 session · for 2026-11-17');
  await expect(panel).toContainText('79th percentile among supported stocks (a ranking, not a probability)');
  await expect(panel).toContainText('test-fixture-only');
  await expect(panel.getByText('Probability', { exact: true })).toHaveCount(0);
  await expect(panel).not.toContainText('0.0012');
});
