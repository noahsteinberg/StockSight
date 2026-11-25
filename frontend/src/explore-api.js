// Fetches and validates one Explore page from GET /api/explore.
// Validation keeps a malformed response from rendering as if it were real data.

export const explorePageSize = 25;

const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
const isNumber = value => typeof value === 'number' && Number.isFinite(value);
const nullable = check => value => value === null || check(value);
const isText = value => typeof value === 'string' && value.length > 0;
const isCount = value => Number.isInteger(value) && value >= 0;

function validItem(item) {
  return item && typeof item === 'object' &&
    isText(item.symbol) &&
    nullable(isText)(item.name) &&
    nullable(isText)(item.exchange) &&
    nullable(isNumber)(item.last_close) &&
    nullable(isDate)(item.as_of) &&
    nullable(isNumber)(item.daily_change_pct) &&
    isText(item.series_revision);
}

export function parseExplorePage(body) {
  const valid = body && typeof body === 'object' &&
    typeof body.query === 'string' &&
    Number.isInteger(body.page) && body.page >= 1 &&
    Number.isInteger(body.page_size) && body.page_size >= 1 &&
    isCount(body.total_supported) && isCount(body.total_matching) &&
    body.total_matching <= body.total_supported &&
    nullable(isDate)(body.latest_session) &&
    Array.isArray(body.items) && body.items.length <= body.page_size &&
    body.items.every(validItem);
  if (!valid) throw new Error('Stock list data was incomplete. Try again.');
  return body;
}

export function exploreErrorMessage(status) {
  if (status === 503) return 'Stock data is temporarily unavailable. Try again.';
  if (status === 422) return 'Invalid search or page. Clear the search and try again.';
  return 'Could not load stocks. Check that the API is running.';
}

export async function fetchExplorePage({ query, page }, signal) {
  const params = new URLSearchParams({ query, page: String(page), page_size: String(explorePageSize) });
  const response = await fetch(`/api/explore?${params}`, { signal });
  if (!response.ok) throw new Error(exploreErrorMessage(response.status));
  return parseExplorePage(await response.json());
}
