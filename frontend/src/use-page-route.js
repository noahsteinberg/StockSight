import { useSyncExternalStore } from 'react';

function subscribe(listener) {
  window.addEventListener('hashchange', listener);
  return () => window.removeEventListener('hashchange', listener);
}

const snapshot = () => window.location.hash;
const knownPages = new Set(['analysis', 'dashboard', 'predictions', 'performance', 'methodology', 'settings', 'login', 'signup', 'reset-password']);
const aliases = { watchlist: 'dashboard', project: 'methodology', main: 'analysis' };

export default function usePageRoute() {
  const hash = useSyncExternalStore(subscribe, snapshot);
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const page = aliases[path] || path || 'analysis';
  const requestedSymbol = new URLSearchParams(query).get('symbol');
  const symbol = requestedSymbol?.trim().toUpperCase();
  return {
    page: knownPages.has(page) ? page : 'not-found',
    symbol: symbol && /^[A-Z][A-Z0-9.^=-]{0,15}$/.test(symbol) ? symbol : null,
    hash,
  };
}
