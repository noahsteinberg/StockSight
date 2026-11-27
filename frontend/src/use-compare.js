import { useCallback, useEffect, useState } from 'react';
import { fetchComparison } from './compare-api.js';

// Loads one comparison; superseded requests are aborted and keyed out, so a slow
// earlier selection or range can never replace the current chart.
export default function useCompare(symbols, range) {
  const [retry, setRetry] = useState(0);
  const symbolKey = symbols.join(',');
  const enabled = symbols.length >= 2;
  const key = `${symbolKey}\n${range}\n${retry}`;
  const [result, setResult] = useState({ key: null, data: null });

  useEffect(() => {
    if (!enabled) return undefined;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    let active = true;
    fetchComparison({ symbols: symbolKey.split(','), range }, controller.signal)
      .then(data => { if (active) setResult({ key, data }); })
      .catch(error => {
        if (!active) return;
        setResult({
          key, data: null,
          error: error.name === 'AbortError' ? 'Request timed out. Try again.' : error.message,
          unknown: error.unknown || [],
        });
      })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [enabled, symbolKey, range, key]);

  const current = result.key === key;
  return {
    data: enabled && current ? result.data : null,
    loading: enabled && !current,
    error: enabled && current ? result.error : null,
    unknown: enabled && current ? result.unknown || [] : [],
    retry: useCallback(() => setRetry(value => value + 1), []),
  };
}
