import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';
import { useCallback, useMemo, useState } from 'react';
import { AccountContext } from './auth-context.js';

const domain = import.meta.env.VITE_AUTH0_DOMAIN?.trim();
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID?.trim();
const audience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim();
const configured = Boolean(domain && clientId && audience);
const unavailable = {
  configured: false, isAuthenticated: false, isLoading: false,
};

function Session({ children }) {
  const { isAuthenticated, isLoading, user, error, loginWithRedirect, logout, getAccessTokenSilently } = useAuth0();
  const [action, setAction] = useState(null);
  const [actionError, setActionError] = useState('');
  const login = useCallback(async (signup = false) => {
    setAction('login');
    setActionError('');
    try {
      await loginWithRedirect({ authorizationParams: signup ? { screen_hint: 'signup' } : {} });
    } catch {
      setActionError('Could not sign in. Try again.');
    } finally { setAction(null); }
  }, [loginWithRedirect]);
  const signOut = useCallback(async () => {
    setAction('logout');
    setActionError('');
    try {
      await logout({ logoutParams: { returnTo: window.location.origin } });
    } catch {
      setActionError('Could not sign out. Try again.');
    } finally { setAction(null); }
  }, [logout]);
  const authorizedFetch = useCallback(async (path, options = {}) => {
    // Tokens stay in the SDK's memory cache, never application storage.
    const token = await getAccessTokenSilently();
    return fetch(path, { ...options, cache: 'no-store', headers: { ...options.headers, Authorization: `Bearer ${token}` } });
  }, [getAccessTokenSilently]);
  const value = useMemo(() => ({
    configured: true, isAuthenticated: isAuthenticated && action !== 'logout',
    isLoading, user, login, logout: signOut, authorizedFetch,
    pending: Boolean(action), error: actionError || (error ? 'Sign-in did not finish. Try again.' : ''),
  }), [isAuthenticated, isLoading, user, login, signOut, authorizedFetch, action, actionError, error]);
  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export default function AuthProvider({ children }) {
  if (!configured) return <AccountContext.Provider value={unavailable}>{children}</AccountContext.Provider>;
  return (
    <Auth0Provider domain={domain} clientId={clientId} cacheLocation="memory"
      authorizationParams={{ redirect_uri: window.location.origin, audience, scope: 'openid profile email' }}
      onRedirectCallback={() => { window.history.replaceState({}, document.title, '/#watchlist'); }}>
      <Session>{children}</Session>
    </Auth0Provider>
  );
}
