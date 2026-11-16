/* eslint-disable react-refresh/only-export-components -- Test-only SDK boundary. */
// Only aliased by `vite serve --mode e2e-accounts`; forbidden in production builds.
import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const FixtureContext = createContext(null);

export function Auth0Provider({ children }) {
  const [identity, setIdentity] = useState(() => sessionStorage.getItem('stocksight:e2e-user'));
  const loginWithRedirect = useCallback(async options => {
    const next = sessionStorage.getItem('stocksight:e2e-next-user') || 'alice';
    sessionStorage.setItem('stocksight:e2e-user', next);
    sessionStorage.setItem('stocksight:e2e-signup', String(options.authorizationParams?.screen_hint === 'signup'));
    setIdentity(next);
  }, []);
  const logout = useCallback(async () => {
    sessionStorage.removeItem('stocksight:e2e-user');
    setIdentity(null);
  }, []);
  const getAccessTokenSilently = useCallback(async () => {
    const response = await fetch(`/api/test/identity?user=${identity}`);
    if (!response.ok) throw new Error('Test identity unavailable');
    return (await response.json()).access_token;
  }, [identity]);
  const value = useMemo(() => ({
    isLoading: false, isAuthenticated: Boolean(identity),
    user: identity ? { sub: `auth0|${identity}`, name: identity === 'alice' ? 'Alice Example' : 'Bob Example' } : undefined,
    loginWithRedirect, logout, getAccessTokenSilently,
  }), [identity, loginWithRedirect, logout, getAccessTokenSilently]);
  return <FixtureContext.Provider value={value}>{children}</FixtureContext.Provider>;
}

export function useAuth0() { return useContext(FixtureContext); }
