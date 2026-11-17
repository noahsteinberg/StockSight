// Only the Auth0 browser SDK handles login transactions/state/nonce validation.
// Passwords go directly to Auth0; StockSight receives only a verified API token.
const domain = import.meta.env.VITE_AUTH0_DOMAIN?.trim();
const clientID = import.meta.env.VITE_AUTH0_CLIENT_ID?.trim();
const audience = import.meta.env.VITE_AUTH0_AUDIENCE?.trim();
const connection = import.meta.env.VITE_AUTH0_DATABASE_CONNECTION?.trim() || 'Username-Password-Authentication';
let client;

async function webAuth() {
  if (!client) client = import('auth0-js').then(({ default: auth0 }) => new auth0.WebAuth({
    domain, clientID, audience, redirectUri: window.location.origin,
    responseType: 'token id_token', scope: 'openid profile email',
  }));
  return client;
}

export function embeddedCallback(hash = window.location.hash) {
  if (hash.startsWith('#/')) return false;
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  return params.has('access_token') || params.has('id_token') || (params.has('error') && params.has('state'));
}

export function authMessage(error, operation = 'login') {
  const code = error?.code || error?.error;
  if (['too_many_attempts', 'too_many_requests'].includes(code)) return 'Too many attempts. Wait a few minutes before trying again.';
  if (['password_strength_error', 'invalid_password', 'password_dictionary_error', 'password_no_user_info_error'].includes(code)) return 'Choose a stronger password with upper and lowercase letters, a number, and a symbol.';
  if (code === 'password_leaked') return 'This password was found in a data breach. Reset your password before signing in.';
  if (['mfa_required', 'requires_verification', 'unauthorized_client', 'unsupported_credential_type', 'blocked_user', 'login_required'].includes(code)) return 'Additional verification is needed. Continue with Auth0 sign-in below.';
  if (operation === 'signup') return 'Could not create the account. Check your details and password, or try signing in if you already have an account.';
  if (operation === 'reset') return 'Could not send the reset email. Try again in a moment.';
  if (['access_denied', 'invalid_grant'].includes(code)) return 'Check your username and password, or continue with Auth0 sign-in if verification is required.';
  return 'Sign-in could not finish. Try again, or use Auth0 sign-in if your browser blocks embedded login.';
}

export async function passwordLogin(username, password) {
  const auth = await webAuth();
  return new Promise((resolve, reject) => {
    // Successful cross-origin login navigates to the callback. Never use ROPG.
    auth.login({ realm: connection, username, password }, error => error ? reject(new Error(authMessage(error))) : resolve());
  });
}

export async function signup({ username, password, email }) {
  // The tenant permits username-only accounts. Auth0.js's older signup wrapper
  // requires email, so use Auth0's public signup endpoint for flexible identifiers.
  const response = await fetch(`https://${domain}/dbconnections/signup`, {
    method: 'POST', credentials: 'omit', signal: AbortSignal.timeout(15000),
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ client_id: clientID, connection, username, password, ...(email ? { email } : {}) }),
  }).catch(() => { throw new Error(authMessage(null, 'signup')); });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(authMessage(error, 'signup'));
  }
}

export async function resetPassword(email) {
  const auth = await webAuth();
  return new Promise((resolve, reject) => auth.changePassword({ connection, email }, error =>
    error ? reject(new Error(authMessage(error, 'reset'))) : resolve()));
}

export async function completeEmbeddedLogin(hash) {
  const auth = await webAuth();
  const result = await new Promise((resolve, reject) => auth.parseHash({ hash }, (error, result) => {
    if (error || !result?.accessToken) reject(new Error('Sign-in could not be verified. Start again.'));
    else resolve(result);
  }));
  // The backend independently verifies signature, issuer, audience and expiry.
  // Tokens never enter application storage or a user-controlled identity field.
  const response = await fetch('/api/auth/session', {
    method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: AbortSignal.timeout(15000),
    headers: { Authorization: `Bearer ${result.accessToken}` },
  });
  if (!response.ok) throw new Error('Could not restore your session. Sign in again.');
  const session = await response.json();
  if (!session.authenticated) throw new Error('Sign-in could not be verified. Start again.');
  return { ...session, status: 'authenticated' };
}
