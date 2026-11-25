import { useSyncExternalStore } from 'react';

function subscribe(listener) {
  window.addEventListener('hashchange', listener);
  return () => window.removeEventListener('hashchange', listener);
}

const snapshot = () => window.location.hash;
const knownPages = new Set(['explore', 'analysis', 'dashboard', 'predictions', 'performance', 'methodology', 'login', 'signup', 'reset-password']);
const aliases = { watchlist: 'dashboard', project: 'methodology', main: 'analysis' };

export default function usePageRoute() {
  const hash = useSyncExternalStore(subscribe, snapshot);
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const page = aliases[path] || path || 'explore';
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
    },
    hash,
  };
}

export function exploreHash({ query = '', page = 1 }) {
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  if (page > 1) params.set('page', String(page));
  const search = params.toString();
  return `#/explore${search ? `?${search}` : ''}`;
}
