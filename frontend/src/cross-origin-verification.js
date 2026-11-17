import { webAuth } from './embedded-auth.js';

const domain = import.meta.env.VITE_AUTH0_DOMAIN?.trim();
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID?.trim();
const expectedOrigin = domain ? `https://${domain}` : null;
const requestedOrigin = new URLSearchParams(window.location.hash.slice(1)).get('origin');

// No React app, login form or session exchange belongs in this iframe. Only the
// configured Auth0 origin may perform the SDK's one-time verifier handshake.
if (clientId && expectedOrigin && requestedOrigin === expectedOrigin && window.parent !== window) {
  window.addEventListener('message', event => {
    if (event.origin !== expectedOrigin || event.source !== window.parent) event.stopImmediatePropagation();
  });
  webAuth().then(auth => auth.crossOriginVerification()).catch(() => {
    document.getElementById('verification-status').textContent = 'Sign-in verification is unavailable. Return to StockSight and try again.';
  });
}
