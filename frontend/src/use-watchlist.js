import { useCallback, useEffect, useState } from 'react';
import { useAccount } from './auth-context.js';

async function checked(response) {
  if (response.ok) return response.status === 204 ? null : response.json();
  const messages = {
    401: 'Your session expired. Sign in again.',
    404: 'This stock is unavailable.',
    409: 'Your watchlist is full. Remove a stock before saving another.',
    503: 'Your watchlist is unavailable. Try again.',
  };
  throw new Error(messages[response.status] || 'Could not update your watchlist. Try again.');
}

export default function useWatchlist() {
  const { isAuthenticated, user, authorizedFetch } = useAccount();
  const owner = isAuthenticated ? user?.sub : null;
  const [resource, setResource] = useState({ owner: null, items: [] });
  const [revision, setRevision] = useState(0);
  const [mutation, setMutation] = useState({ owner: null });

  useEffect(() => {
    if (!owner) return;
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    async function load() {
      try {
        const data = await checked(await authorizedFetch('/api/watchlist', { signal: controller.signal }));
        if (active) setResource({ owner, revision, items: data.items });
      } catch (error) {
        if (active) setResource({ owner, revision, items: [], error: error.message === 'Your watchlist is unavailable. Try again.' ? error.message : 'Could not load your watchlist. Sign in again or retry.' });
      } finally { clearTimeout(timeout); }
    }
    load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [owner, revision, authorizedFetch]);

  const update = useCallback(async (symbol, remove = false) => {
    if (!owner) return;
    setMutation({ owner, busy: true, symbol });
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      await checked(await authorizedFetch(remove ? `/api/watchlist/${encodeURIComponent(symbol)}` : '/api/watchlist', {
        method: remove ? 'DELETE' : 'POST', signal: controller.signal,
        ...(remove ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ symbol }) }),
      }));
      setRevision(value => value + 1);
      setMutation({ owner, success: remove ? `${symbol} removed.` : `${symbol} saved.` });
    } catch (error) {
      setMutation({ owner, error: error.message.startsWith('Your ') || error.message === 'This stock is unavailable.' ? error.message : 'Could not update your watchlist. Sign in again or retry.' });
    } finally { clearTimeout(timeout); }
  }, [owner, authorizedFetch]);

  const retry = useCallback(() => setRevision(value => value + 1), []);

  return {
    items: owner && resource.owner === owner ? resource.items : [],
    loading: Boolean(owner && (resource.owner !== owner || resource.revision !== revision)),
    error: owner && resource.owner === owner ? resource.error : null,
    mutation: owner && mutation.owner === owner ? mutation : {},
    save: symbol => update(symbol), remove: symbol => update(symbol, true),
    retry,
  };
}
