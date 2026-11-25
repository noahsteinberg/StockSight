import { useCallback, useEffect, useState } from 'react';
import { explorePageSize, fetchExplorePage, fetchSectors } from './explore-api.js';
import { fetchDiscoveryPage } from './preferences-api.js';

// Loads one Explore page. A newer query/page/sector/retry aborts the older request
// and results are keyed to their request, so a slow response never replaces newer
// rows. While the next page loads, the last settled rows stay visible and are marked busy.
// `personal` ({ owner, authorizedFetch }) switches to the private discovery list; the
// owner is part of the key, so another account's late response is never shown.
export default function useExplore(query, page, sector, personal = null) {
  const [retry, setRetry] = useState(0);
  const owner = personal?.owner ?? null;
  const authorizedFetch = personal?.authorizedFetch ?? null;
  const key = [query, page, sector, owner, retry].join('\n');
  const [result, setResult] = useState({ key: null, owner: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    const request = authorizedFetch
      ? fetchDiscoveryPage({ query, page, pageSize: explorePageSize }, authorizedFetch, controller.signal)
      : fetchExplorePage({ query, page, sector }, controller.signal);
    request
      .then(data => { if (active) setResult({ key, owner, data }); })
      .catch(error => {
        if (active) setResult({ key, owner, data: null, error: error.name === 'AbortError' ? 'Request timed out. Try again.' : error.message });
      })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [query, page, sector, owner, authorizedFetch, key]);

  return {
    // Older rows stay visible while the next page loads, but only for the same list
    // and account: public and private results never stand in for each other.
    data: result.key === key || result.owner === owner ? result.data : null,
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
