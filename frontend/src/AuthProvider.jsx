import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AccountContext } from './auth-context.js';

const domain = import.meta.env.VITE_AUTH0_DOMAIN?.trim();
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID?.trim();
const audience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim();
const configured = Boolean(domain && clientId && audience);
const unavailable = {
  configured: false, isAuthenticated: false, isLoading: false,
};
const guest = { status: 'guest', authenticated: false };

async function sessionRequest(options = {}) {
  const response = await fetch('/api/auth/session', { credentials: 'same-origin', cache: 'no-store', ...options });
  if (!response.ok) throw new Error('Could not restore your session. Sign in again.');
  const data = await response.json();
  return { ...data, status: data.authenticated ? 'authenticated' : 'guest' };
}

function Session({ children }) {
  const { isAuthenticated: sdkAuthenticated, isLoading: sdkLoading, user: sdkUser,
    error: sdkError, loginWithRedirect, logout, getAccessTokenSilently } = useAuth0();
  const [session, setSession] = useState({ status: 'loading', authenticated: false });
  const sessionUserId = session.user?.id;
  const sessionSubject = session.user?.sub;
  const [callback] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.has('state') && (params.has('code') || params.has('error'));
  });
  const [expired, setExpired] = useState(false);
  const [action, setAction] = useState(null);
  const [actionError, setActionError] = useState('');
  const exchange = useRef(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    sessionRequest({ signal: controller.signal }).then(data => {
      if (active) setSession(data);
    }).catch(() => {
      if (active) setSession({ ...guest, status: 'error', error: 'Could not restore your session. Sign in again.' });
    }).finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, []);

  useEffect(() => {
    if (!sdkAuthenticated || !sdkUser?.sub || expired || action || session.status === 'loading' || session.status === 'error') return;
    if (session.authenticated && (!callback || session.user.sub === sdkUser.sub)) return;
    let active = true;
    if (!exchange.current) {
      exchange.current = (async () => {
        const token = await getAccessTokenSilently();
        return sessionRequest({ method: 'POST', headers: { Authorization: `Bearer ${token}` } });
      })();
    }
    exchange.current.then(data => {
      if (active) setSession(data);
    }).catch(() => {
      if (active) setSession({ ...guest, status: 'error', error: 'Could not restore your session. Sign in again.' });
    });
    return () => { active = false; };
  }, [sdkAuthenticated, sdkUser?.sub, expired, action, callback, session.status, session.authenticated, session.user?.sub, getAccessTokenSilently]);

  useEffect(() => {
    if (!session.authenticated) return;
    const timer = setTimeout(() => {
      setExpired(true);
      setSession(guest);
      setActionError('Your session expired. Sign in again.');
    }, Math.max(0, new Date(session.expires_at).getTime() - Date.now()));
    return () => clearTimeout(timer);
  }, [session.authenticated, session.expires_at]);

  useEffect(() => {
    if (!session.authenticated) return;
    let active = true;
    async function recheck() {
      if (document.visibilityState === 'hidden') return;
      try {
        const next = await sessionRequest();
        if (!active) return;
        if (!next.authenticated) {
          setExpired(true);
          setSession(guest);
          setActionError('Your session ended. Sign in again.');
        } else if (next.user.id !== sessionUserId) {
          setSession(next);
        }
      } catch { /* A transient outage must not manufacture a new identity. */ }
    }
    window.addEventListener('focus', recheck);
    document.addEventListener('visibilitychange', recheck);
    return () => {
      active = false;
      window.removeEventListener('focus', recheck);
      document.removeEventListener('visibilitychange', recheck);
    };
  }, [session.authenticated, sessionUserId]);
  const login = useCallback(async (signup = false) => {
    setAction('login');
    setActionError('');
    setExpired(false);
    exchange.current = null;
    setSession(guest);
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
      const response = await fetch('/api/auth/logout', {
        method: 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: { 'X-CSRF-Token': session.csrf_token, 'X-Session-User': sessionUserId },
      });
      if (!response.ok) throw new Error('Session revocation failed');
      setExpired(true);
      setSession(guest);
      try { await logout({ logoutParams: { returnTo: window.location.origin } }); }
      catch { setActionError('Signed out of StockSight. Auth0 sign-out did not finish.'); }
    } catch {
      setActionError('Could not sign out. Try again.');
    } finally { setAction(null); }
  }, [logout, session.csrf_token, sessionUserId]);
  const authorizedFetch = useCallback(async (path, options = {}) => {
    if (!path.startsWith('/api/') || !session.authenticated) throw new Error('Your session expired. Sign in again.');
    const response = await fetch(path, {
      ...options, credentials: 'same-origin', cache: 'no-store',
      headers: { ...options.headers, 'X-CSRF-Token': session.csrf_token, 'X-Session-User': sessionUserId },
    });
    if (response.status === 401) {
      setExpired(true);
      setSession(guest);
      setActionError('Your session expired or your account changed. Sign in again.');
    }
    return response;
  }, [session.authenticated, session.csrf_token, sessionUserId]);
  const authenticated = session.authenticated && action !== 'logout'
    && (!callback || (!sdkLoading && sdkAuthenticated && sdkUser?.sub === session.user.sub));
  const restoring = session.status === 'loading' || (callback && sdkLoading)
    || (sdkAuthenticated && !session.authenticated && !expired && !action && session.status !== 'error');
  const displayUser = useMemo(() => !authenticated ? undefined :
    sdkUser?.sub === sessionSubject ? sdkUser : { sub: sessionSubject, name: 'Your account' },
  [authenticated, sdkUser, sessionSubject]);
  const value = useMemo(() => ({
    configured: true, isAuthenticated: Boolean(authenticated), isLoading: Boolean(restoring),
    user: displayUser, login, logout: signOut, authorizedFetch,
    pending: Boolean(action), error: actionError || session.error || (!authenticated && sdkError ? 'Sign-in did not finish. Try again.' : ''),
  }), [authenticated, restoring, displayUser, login, signOut, authorizedFetch, action, actionError, session.error, sdkError]);
  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export default function AuthProvider({ children }) {
  if (!configured) return <AccountContext.Provider value={unavailable}>{children}</AccountContext.Provider>;
  return (
    <Auth0Provider domain={domain} clientId={clientId} cacheLocation="memory"
      authorizationParams={{ redirect_uri: window.location.origin, audience, scope: 'openid profile email' }}
      onRedirectCallback={() => {
        window.history.replaceState({}, document.title, '/#/dashboard');
        window.dispatchEvent(new HashChangeEvent('hashchange'));
      }}>
      <Session>{children}</Session>
    </Auth0Provider>
  );
}
