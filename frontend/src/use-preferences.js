import { useCallback, useEffect, useState } from 'react';
import { useAccount } from './auth-context.js';
import { fetchPreferences, resetPreferences, savePreferences } from './preferences-api.js';

// Account-scoped preferences. Results are keyed to the signed-in owner, so after a
// sign-out or account switch nothing from the previous account is returned, even
// when its request finishes late. Nothing is cached in browser storage.
export default function usePreferences() {
  const { isAuthenticated, user, authorizedFetch } = useAccount();
  const owner = isAuthenticated ? user?.sub : null;
  const [resource, setResource] = useState({ owner: null });
  const [revision, setRevision] = useState(0);
  const [mutation, setMutation] = useState({ owner: null });

  useEffect(() => {
    if (!owner) return undefined;
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    fetchPreferences(authorizedFetch, controller.signal)
      .then(data => { if (active) setResource({ owner, revision, data }); })
      .catch(error => {
        if (active) setResource({ owner, revision, error: error.name === 'AbortError' ? 'Preferences timed out. Try again.' : error.message });
      })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [owner, revision, authorizedFetch]);

  const run = useCallback(async (action, success) => {
    if (!owner) return false;
    setMutation({ owner, busy: true });
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const data = await action(controller.signal);
      setResource(current => ({ owner, revision: current.revision, data }));
      setMutation({ owner, success });
      return true;
    } catch (error) {
      setMutation({ owner, error: error.name === 'AbortError' ? 'The request timed out. Try again.' : error.message });
      return false;
    } finally { clearTimeout(timeout); }
  }, [owner]);

  const save = useCallback(values => run(signal => savePreferences(authorizedFetch, values, signal), 'Preferences saved.'), [run, authorizedFetch]);
  const reset = useCallback(() => run(async signal => {
    await resetPreferences(authorizedFetch, signal);
    return { saved: false, purpose: null, sectors: [], horizon: null, default_range: null, updated_at: null };
  }, 'Preferences reset. Pages use their usual defaults again.'), [run, authorizedFetch]);

  const current = owner && resource.owner === owner ? resource : null;
  return {
    owner,
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: Boolean(owner && (!current || current.revision !== revision)),
    mutation: owner && mutation.owner === owner ? mutation : {},
    defaultRange: current?.data?.default_range ?? null,
    save,
    reset,
    retry: useCallback(() => setRevision(value => value + 1), []),
  };
}
