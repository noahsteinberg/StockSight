// Fetches and validates GET /api/compare. Errors carry the unknown symbols the API
// names so the page can offer to remove exactly those.

export const compareLimit = 4;
export const compareRanges = [['1mo', '1M'], ['3mo', '3M'], ['1y', '1Y'], ['all', 'Max']];

const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
const isNumber = value => typeof value === 'number' && Number.isFinite(value);
const nullable = check => value => value === null || check(value);
const statuses = new Set(['ok', 'insufficient_overlap', 'split_unadjusted']);

function validStock(stock, length) {
  return stock && typeof stock === 'object' &&
    typeof stock.symbol === 'string' && stock.symbol &&
    nullable(value => typeof value === 'string')(stock.name) &&
    isDate(stock.as_of) && isNumber(stock.last_close) &&
    typeof stock.series_revision === 'string' &&
    nullable(isNumber)(stock.start_close) && nullable(isNumber)(stock.end_close) &&
    nullable(isNumber)(stock.period_change_pct) &&
    statuses.has(stock.metric_status) &&
    Array.isArray(stock.split_events) &&
    stock.split_events.every(event => isDate(event.date) && isNumber(event.ratio) && typeof event.price_adjusted === 'boolean') &&
    Array.isArray(stock.indexed) && stock.indexed.length === length && stock.indexed.every(isNumber);
}

export function parseComparePage(body) {
  const valid = body && typeof body === 'object' &&
    compareRanges.some(([value]) => value === body.range) &&
    Number.isInteger(body.requested_sessions) && Number.isInteger(body.common_sessions) &&
    body.common_sessions <= body.requested_sessions &&
    nullable(isDate)(body.start) && nullable(isDate)(body.end) &&
    typeof body.aligned_to_shared_cutoff === 'boolean' &&
    Array.isArray(body.dates) && body.dates.length === body.common_sessions && body.dates.every(isDate) &&
    Array.isArray(body.stocks) && body.stocks.length >= 2 && body.stocks.length <= compareLimit &&
    body.stocks.every(stock => validStock(stock, body.dates.length));
  if (!valid) throw new Error('Comparison data was incomplete. Try again.');
  return body;
}

export class CompareError extends Error {
  constructor(message, unknown = []) {
    super(message);
    this.unknown = unknown;
  }
}

export async function fetchComparison({ symbols, range }, signal) {
  const params = new URLSearchParams({ symbols: symbols.join(','), range });
  const response = await fetch(`/api/compare?${params}`, { signal });
  if (response.ok) return parseComparePage(await response.json());
  const detail = await response.json().then(body => body?.detail, () => null);
  if (response.status === 404 && Array.isArray(detail?.symbols)) {
    throw new CompareError(`No stored history for ${detail.symbols.join(', ')}.`, detail.symbols);
  }
  if (response.status === 422) throw new CompareError('Choose 2 to 4 different supported ticker symbols.');
  if (response.status === 503) throw new CompareError('Stock data is temporarily unavailable. Try again.');
  throw new CompareError('Could not load the comparison. Check that the API is running.');
}
