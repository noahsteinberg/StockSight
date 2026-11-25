import { useCallback, useEffect, useState } from 'react';
import { fetchExplorePage, fetchSectors } from './explore-api.js';

// Loads one Explore page. A newer query/page/sector/retry aborts the older request
// and results are keyed to their request, so a slow response never replaces newer
// rows. While the next page loads, the last settled rows stay visible and are marked busy.
export default function useExplore(query, page, sector) {
  const [retry, setRetry] = useState(0);
  const key = [query, page, sector, retry].join('\n');
  const [result, setResult] = useState({ key: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    fetchExplorePage({ query, page, sector }, controller.signal)
      .then(data => { if (active) setResult({ key, data }); })
      .catch(error => {
        if (active) setResult({ key, data: null, error: error.name === 'AbortError' ? 'Request timed out. Try again.' : error.message });
      })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [query, page, sector, key]);

  return {
    data: result.data,
    loading: result.key !== key,
    error: result.key === key ? result.error : null,
    retry: useCallback(() => setRetry(value => value + 1), []),
  };
}

// Sector counts and the metadata source load once per Explore visit. A failure
// leaves the filter usable with plain sector names and no counts.
export function useSectors() {
  const [state, setState] = useState({ data: null, error: false });
  useEffect(() => {
    const controller = new AbortController();
    fetchSectors(controller.signal)
      .then(data => setState({ data, error: false }))
      .catch(error => { if (error.name !== 'AbortError') setState({ data: null, error: true }); });
    return () => controller.abort();
  }, []);
  return state;
}
