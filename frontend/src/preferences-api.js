// Private research preferences (GET/PUT/DELETE /api/me/preferences) and the
// discovery list they explain (GET /api/me/discovery). Every call goes through
// authorizedFetch, so ownership comes from the signed-in account, never the URL.
import { sectorNames, validExploreItem } from './explore-api.js';

export const purposeOptions = [['learn', 'Learn about stocks'], ['compare', 'Compare choices'], ['track', 'Track a shortlist']];
export const horizonOptions = [['weeks', 'Weeks'], ['months', 'Months'], ['years', 'Years']];
export const rangeOptions = [['1mo', '1M'], ['3mo', '3M'], ['1y', '1Y'], ['all', 'Max']];

const values = options => options.map(([value]) => value);
const optional = allowed => value => value === null || allowed.includes(value);
const isCount = value => Number.isInteger(value) && value >= 0;

export function parsePreferences(body) {
  const valid = body && typeof body === 'object' &&
    typeof body.saved === 'boolean' &&
    optional(values(purposeOptions))(body.purpose) &&
    optional(values(horizonOptions))(body.horizon) &&
    optional(values(rangeOptions))(body.default_range) &&
    Array.isArray(body.sectors) && body.sectors.every(sector => sectorNames.includes(sector)) &&
    (body.updated_at === null || typeof body.updated_at === 'string');
  if (!valid) throw new Error('Preferences data was incomplete. Try again.');
  return body;
}

export function parseDiscoveryPage(body) {
  const valid = body && typeof body === 'object' &&
    typeof body.query === 'string' &&
    Array.isArray(body.preference_sectors) && body.preference_sectors.every(sector => sectorNames.includes(sector)) &&
    Number.isInteger(body.page) && body.page >= 1 &&
    Number.isInteger(body.page_size) && body.page_size >= 1 &&
    isCount(body.total_supported) && isCount(body.total_matching) &&
    body.total_matching <= body.total_supported &&
    Array.isArray(body.items) && body.items.length <= body.page_size &&
    body.items.every(item => validExploreItem(item) && typeof item.match_reason === 'string' && item.match_reason.length > 0);
  if (!valid) throw new Error('Matching stocks were incomplete. Try again.');
  // Shaped like an Explore page so the same list renders it.
  return { ...body, sector: null, latest_session: body.latest_session ?? null };
}

const messages = {
  401: 'Your session expired. Sign in again.',
  403: 'Your session expired. Sign in again.',
  422: 'Some choices were invalid. Review them and try again.',
  503: 'Your preferences are unavailable. Try again.',
};

async function checked(response) {
  if (response.ok) return response.status === 204 ? null : response.json();
  throw new Error(messages[response.status] || 'Could not reach your preferences. Try again.');
}

export async function fetchPreferences(authorizedFetch, signal) {
  return parsePreferences(await checked(await authorizedFetch('/api/me/preferences', { signal })));
}

export async function savePreferences(authorizedFetch, preferences, signal) {
  const body = JSON.stringify({
    purpose: preferences.purpose, sectors: preferences.sectors,
    horizon: preferences.horizon, default_range: preferences.default_range,
  });
  return parsePreferences(await checked(await authorizedFetch('/api/me/preferences', {
    method: 'PUT', signal, headers: { 'Content-Type': 'application/json' }, body,
  })));
}

export async function resetPreferences(authorizedFetch, signal) {
  await checked(await authorizedFetch('/api/me/preferences', { method: 'DELETE', signal }));
}

export async function fetchDiscoveryPage({ query, page, pageSize }, authorizedFetch, signal) {
  const params = new URLSearchParams({ query, page: String(page), page_size: String(pageSize) });
  return parseDiscoveryPage(await checked(await authorizedFetch(`/api/me/discovery?${params}`, { signal })));
}
