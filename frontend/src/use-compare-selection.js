import { useCallback, useState } from 'react';
import { compareLimit } from './compare-api.js';

// The stocks picked for comparison from Explore, Watchlist or Analysis. Only public
// ticker symbols are kept, in this tab's sessionStorage, so it is safe for guests.
const storageKey = 'stocksight:compare-selection';
const symbolPattern = /^[A-Z][A-Z0-9.^=-]{0,15}$/;

function readSaved() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || '[]');
    return Array.isArray(saved) ? saved.filter(symbol => symbolPattern.test(symbol)).slice(0, compareLimit) : [];
  } catch {
    return [];
  }
}

export default function useCompareSelection() {
  const [symbols, setSymbols] = useState(readSaved);
  const replace = useCallback(next => {
    const cleaned = [...new Set(next)].filter(symbol => symbolPattern.test(symbol)).slice(0, compareLimit);
    setSymbols(cleaned);
    try { sessionStorage.setItem(storageKey, JSON.stringify(cleaned)); }
    catch { /* The selection still works for this page view without storage. */ }
  }, []);
  const toggle = useCallback(symbol => {
    replace(symbols.includes(symbol) ? symbols.filter(item => item !== symbol) : [...symbols, symbol]);
  }, [symbols, replace]);
  return { symbols, full: symbols.length >= compareLimit, toggle, replace, clear: () => replace([]) };
}

export function compareHash(symbols, range) {
  const params = new URLSearchParams();
  if (symbols.length) params.set('symbols', symbols.join(','));
  if (range && range !== '1y') params.set('range', range);
  const search = params.toString().replaceAll('%2C', ',');
  return `#/compare${search ? `?${search}` : ''}`;
}
