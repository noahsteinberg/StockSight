import { useSyncExternalStore } from 'react';
import { normalizeExploreSort, sectorNames } from './explore-api.js';

function subscribe(listener) {
  window.addEventListener('hashchange', listener);
  return () => window.removeEventListener('hashchange', listener);
}

const snapshot = () => window.location.hash;
const knownPages = new Set(['explore', 'analysis', 'compare', 'dashboard', 'preferences', 'settings', 'predictions', 'performance', 'methodology', 'login', 'signup', 'reset-password']);
const aliases = { watchlist: 'dashboard', project: 'methodology', main: 'analysis' };

export default function usePageRoute() {
  const hash = useSyncExternalStore(subscribe, snapshot);
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const page = aliases[path] || path || 'dashboard';
  const params = new URLSearchParams(query);
  const requestedSymbol = params.get('symbol');
  const symbol = requestedSymbol?.trim().toUpperCase();
  const requestedPage = Number(params.get('page'));
  return {
    page: knownPages.has(page) ? page : 'not-found',
    symbol: symbol && /^[A-Z][A-Z0-9.^=-]{0,15}$/.test(symbol) ? symbol : null,
    // Explore list state lives in the URL so back/forward and shared links work.
    explore: {
      query: (params.get('q') || '').trim().slice(0, 40),
      page: Number.isInteger(requestedPage) && requestedPage >= 1 && requestedPage <= 1000 ? requestedPage : 1,
      sector: sectorNames.includes(params.get('sector')) ? params.get('sector') : null,
      sort: normalizeExploreSort(params.get('sort')),
      // mine=1 lists stocks matching the signed-in account's saved sectors.
      mine: params.get('mine') === '1',
    },
    // Up to 10 are parsed so the Compare page can say when a link held more than 4.
    compare: {
      symbols: [...new Set((params.get('symbols') || '').split(',').map(value => value.trim().toUpperCase()))]
        .filter(value => /^[A-Z][A-Z0-9.^=-]{0,15}$/.test(value)).slice(0, 10),
      // null when absent, so a saved default range can apply.
      range: ['1mo', '3mo', '1y', 'all'].includes(params.get('range')) ? params.get('range') : null,
    },
    hash,
  };
}

export function exploreHash({ query = '', page = 1, sector = null, sort = 'ticker', mine = false }) {
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  if (mine) params.set('mine', '1');
  else if (sector) params.set('sector', sector);
  if (sort !== 'ticker') params.set('sort', sort);
  if (page > 1) params.set('page', String(page));
  const search = params.toString();
  return `#/explore${search ? `?${search}` : ''}`;
}
