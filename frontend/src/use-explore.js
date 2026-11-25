import { useCallback, useEffect, useState } from 'react';
import { fetchExplorePage } from './explore-api.js';

// Loads one Explore page. A newer query/page/retry aborts the older request and
// results are keyed to their request, so a slow response never replaces newer rows.
// While the next page loads, the last settled rows stay visible and are marked busy.
export default function useExplore(query, page) {
  const [retry, setRetry] = useState(0);
  const key = `${query}\n${page}\n${retry}`;
  const [result, setResult] = useState({ key: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    fetchExplorePage({ query, page }, controller.signal)
      .then(data => { if (active) setResult({ key, data }); })
      .catch(error => {
        if (active) setResult({ key, data: null, error: error.name === 'AbortError' ? 'Request timed out. Try again.' : error.message });
      })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [query, page, key]);

  return {
    data: result.data,
    loading: result.key !== key,
    error: result.key === key ? result.error : null,
    retry: useCallback(() => setRetry(value => value + 1), []),
  };
}
