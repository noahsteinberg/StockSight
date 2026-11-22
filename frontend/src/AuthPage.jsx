import { useEffect, useRef, useState } from 'react';
import { useAccount } from './auth-context.js';
import StockBackdrop from './StockBackdrop.jsx';
import './AuthPage.css';

function GoogleIcon() {
  return <svg className="google-icon" viewBox="0 0 48 48" aria-hidden="true">
    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6C44.4 38.03 46.98 31.85 46.98 24.55z"/>
    <path fill="#FBBC05" d="M10.53 28.59A14.4 14.4 0 0 1 9.75 24c0-1.59.27-3.13.76-4.59l-7.98-6.19A23.87 23.87 0 0 0 0 24c0 3.87.93 7.52 2.56 10.78l7.97-6.19z"/>
    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.91-5.8l-7.73-6c-2.15 1.45-4.92 2.3-8.18 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
  </svg>;
}

export default function AuthPage({ mode }) {
  const account = useAccount();
  const heading = useRef(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const submitting = useRef(false);
  const mounted = useRef(false);
  const signup = mode === 'signup';
  const reset = mode === 'reset-password';
  const title = reset ? 'Reset password' : signup ? 'Create an account' : 'Log in';
  const busy = pending || account.pending || account.isLoading;
  const unavailable = !account.configured;

  useEffect(() => {
    mounted.current = true;
    heading.current?.focus();
    return () => { mounted.current = false; };
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (busy || unavailable || submitting.current) return;
    submitting.current = true;
    setPending(true);
    setError('');
    setNotice('');
    const form = event.currentTarget;
    const fields = new FormData(form);
    try {
      if (reset) {
        await account.resetPassword(String(fields.get('email')).trim());
        if (mounted.current) setNotice('If an account has this recovery email, Auth0 will send a password reset link.');
      } else if (signup) {
        await account.signup({ username: String(fields.get('username')).trim(), password: fields.get('password'), email: String(fields.get('email') || '').trim() });
        if (mounted.current) setNotice('Account created. You can now log in. If Auth0 requires email verification, check your inbox.');
      } else {
        await account.loginWithPassword(String(fields.get('username')).trim(), fields.get('password'));
      }
    } catch (error) {
      if (mounted.current) setError(error instanceof Error && error.message ? error.message : 'Could not finish. Try again.');
    } finally {
      // Do not retain passwords after either success or failure.
      if (form.elements.password) form.elements.password.value = '';
      fields.delete('password');
      submitting.current = false;
      if (mounted.current) setPending(false);
    }
  }

  return <div className="ss-page">
    <div className="ss-shell">
      <StockBackdrop />
      <main className="ss-main" id="main">
        <a className="ss-header" href="#/dashboard" aria-label="StockSight home">
          <svg className="ss-logo" viewBox="0 0 32 32" aria-hidden="true"><path d="M5 23V9M5 23h22M10 19l6-7 5 3 7-9"/></svg>
          <span className="ss-brand">StockSight</span>
        </a>
        <section className="ss-auth" aria-labelledby="account-title">
          <div className="auth-card">
            <h1 id="account-title" ref={heading} tabIndex="-1">{title}</h1>
            <p className="subtitle">{reset ? 'Use the recovery email on your account.' : 'Continue to StockSight.'}</p>
            {unavailable && <p className="auth-status" role="status">Sign-in is not configured for this environment.</p>}
            {account.isLoading && <p className="auth-status" role="status">Checking your session…</p>}
            {(error || account.error) &&
              <p className="auth-status auth-error" role="alert">{error || account.error}</p>
            }
            {notice && <p className="auth-status" role="status">{notice} {signup && <a href="#/login">Log in</a>}</p>}
            <form onSubmit={submit} aria-busy={Boolean(busy)}>
              {!reset && <div className="auth-field">
                <label htmlFor="username">Username</label>
                <input id="username" name="username" autoComplete="username" autoCapitalize="none" spellCheck="false" required maxLength="128" placeholder="Your username" disabled={busy || unavailable}/>
              </div>}
              {(signup || reset) && <div className="auth-field">
                <label htmlFor="email">{reset ? 'Recovery email' : 'Email address (optional)'}</label>
                <input id="email" name="email" type="email" autoComplete="email" autoCapitalize="none" required={reset} maxLength="254" placeholder="you@example.com" disabled={busy || unavailable}/>
              </div>}
              {!reset && <div className="auth-field">
                <label htmlFor="password">Password</label>
                <div className="password-control">
                  <input id="password" name="password" type={showPassword ? 'text' : 'password'} autoComplete={signup ? 'new-password' : 'current-password'} required maxLength="128" placeholder="Enter your password" disabled={busy || unavailable}/>
                  <button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword} disabled={busy || unavailable} onClick={() => setShowPassword(value => !value)}>{showPassword ? 'Hide' : 'Show'}</button>
                </div>
              </div>}
              {!signup && !reset && <a className="auth-help" href="#/reset-password">Forgot password?</a>}
              <button className="primary" type="submit" disabled={busy || unavailable}>{busy ? 'Please wait…' : reset ? 'Send reset link' : signup ? 'Create account' : 'Continue'}</button>
            </form>
            {!reset && <>
              <p className="switch">{signup ? <>Already have an account? <a href="#/login">Log in</a></> : <>New to StockSight? <a href="#/signup">Create an account</a></>}</p>
              <div className="preview-divider">or</div>
              <button className="secondary" type="button" disabled={busy || unavailable} onClick={() => account.loginHosted('google')}><GoogleIcon/>Continue with Google</button>
            </>}
            {!signup && !reset && !unavailable && <details className="auth-recovery" open={Boolean(error || account.error)}>
              <summary>Trouble signing in?</summary>
              <p>Use Auth0 if your browser blocks password sign-in or your account needs verification.</p>
              <button className="secondary" type="button" disabled={busy} onClick={() => account.loginHosted('password')}>Continue on Auth0</button>
            </details>}
            {reset && <p className="switch"><a href="#/login">Back to log in</a></p>}
          </div>
        </section>
      </main>
      <footer className="ss-footer"><p>For education and research. Not financial advice.</p><a className="ss-back" href="#/analysis">Back to stock analysis</a></footer>
    </div>
  </div>;
}
