// Fetches and validates one Explore page from GET /api/explore.
// Validation keeps a malformed response from rendering as if it were real data.

export const explorePageSize = 10;
export const exploreSortOptions = [
  ['ticker', 'Ticker A–Z'],
  ['change_desc', 'Daily change: high to low'],
  ['change_asc', 'Daily change: low to high'],
];

export function normalizeExploreSort(sort) {
  return exploreSortOptions.some(([key]) => key === sort) ? sort : 'ticker';
}

// The fixed GICS sector names used by the reviewed metadata (see GET /api/sectors).
export const sectorNames = ['Communication Services', 'Consumer Discretionary', 'Consumer Staples', 'Energy',
  'Financials', 'Health Care', 'Industrials', 'Information Technology', 'Materials', 'Real Estate', 'Utilities'];

const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
const isNumber = value => typeof value === 'number' && Number.isFinite(value);
const nullable = check => value => value === null || check(value);
const isText = value => typeof value === 'string' && value.length > 0;
const isCount = value => Number.isInteger(value) && value >= 0;

export function validExploreItem(item) {
  return item && typeof item === 'object' &&
    isText(item.symbol) &&
    nullable(isText)(item.name) &&
    nullable(isText)(item.exchange) &&
    nullable(isText)(item.sector) &&
    nullable(isText)(item.sub_industry) &&
    nullable(isNumber)(item.last_close) &&
    nullable(isDate)(item.as_of) &&
    nullable(isNumber)(item.daily_change_pct) &&
    isText(item.series_revision);
}

export function parseExplorePage(body) {
  const valid = body && typeof body === 'object' &&
    typeof body.query === 'string' &&
    nullable(isText)(body.sector) &&
    Number.isInteger(body.page) && body.page >= 1 &&
    Number.isInteger(body.page_size) && body.page_size >= 1 &&
    isCount(body.total_supported) && isCount(body.total_matching) &&
    body.total_matching <= body.total_supported &&
    nullable(isDate)(body.latest_session) &&
    Array.isArray(body.items) && body.items.length <= body.page_size &&
    body.items.every(validExploreItem);
  if (!valid) throw new Error('Stock list data was incomplete. Try again.');
  return body;
}

export function exploreErrorMessage(status) {
  if (status === 503) return 'Stock data is temporarily unavailable. Try again.';
  if (status === 422) return 'Invalid search or page. Clear the search and try again.';
  return 'Could not load stocks. Check that the API is running.';
}

export async function fetchExplorePage({ query, page, sector, sort }, signal) {
  const params = new URLSearchParams({ query, page: String(page), page_size: String(explorePageSize) });
  if (sector) params.set('sector', sector);
  if (sort !== 'ticker') params.set('sort', sort);
  const response = await fetch(`/api/explore?${params}`, { signal });
  if (!response.ok) throw new Error(exploreErrorMessage(response.status));
  return parseExplorePage(await response.json());
}

// GET /api/sectors: per-sector counts over supported stocks plus the metadata source.
export function parseSectorList(body) {
  const source = body?.source;
  const valid = body && typeof body === 'object' &&
    isCount(body.total_supported) && isCount(body.unknown) &&
    source && isText(source.name) && isText(source.url) && /^https:\/\//.test(source.url) &&
    isDate(source.revision_date) && isDate(source.retrieved) && isText(source.taxonomy) && isText(source.license) &&
    Array.isArray(body.sectors) &&
    body.sectors.every(sector => sectorNames.includes(sector?.name) && isCount(sector.count));
  if (!valid) throw new Error('Sector data was incomplete.');
  return body;
}

export async function fetchSectors(signal) {
  const response = await fetch('/api/sectors', { signal });
  if (!response.ok) throw new Error('Sectors are unavailable.');
  return parseSectorList(await response.json());
}
