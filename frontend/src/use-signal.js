import { useCallback, useEffect, useState } from 'react';
import { fetchSignal } from './signal-api.js';

// Keyed to the symbol and retry count, so a slow answer for the previous stock is
// never shown; 10-second timeout, like the other read hooks.
export default function useSignal(symbol) {
  const [retry, setRetry] = useState(0);
  const key = `${symbol}\n${retry}`;
  const [result, setResult] = useState({ key: null });
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    fetchSignal(symbol, controller.signal)
      .then(data => { if (active) setResult({ key, data }); })
      .catch(error => { if (active) setResult({ key, error: error.name === 'AbortError' ? 'The signal check timed out. Try again.' : error.message }); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [symbol, key]);
  const current = result.key === key ? result : { loading: true };
  return { ...current, retry: useCallback(() => setRetry(value => value + 1), []) };
}
