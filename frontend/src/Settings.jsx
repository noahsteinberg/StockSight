import { useRef, useState } from 'react';
import { useAccount } from './auth-context.js';
import { defaultChartSettings } from './chart-defaults.js';

function PasswordRecovery({ resetPassword, disabled }) {
  const submitting = useRef(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState(null);

  async function sendReset(event) {
    event.preventDefault();
    if (submitting.current || disabled) return;
    const form = event.currentTarget;
    const email = String(new FormData(form).get('email')).trim();
    submitting.current = true;
    setPending(true);
    setNotice(null);
    try {
      await resetPassword(email);
      form.reset();
      setNotice({ text: 'If the address matches an account, Auth0 will email a reset link.' });
    } catch (error) {
      setNotice({ error: true, text: error instanceof Error && error.message ? error.message : 'Could not send the reset email. Try again.' });
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  return <div className="settings-row">
    <h3>Security &amp; recovery</h3>
    <details className="settings-recovery">
      <summary>Reset password</summary>
      <p>Use the recovery email you added at signup. If you skipped it, contact your StockSight administrator for help.</p>
      <form onSubmit={sendReset} aria-busy={pending}>
        <label htmlFor="settings-recovery-email">Recovery email</label>
        <input id="settings-recovery-email" name="email" type="email" autoComplete="email"
          autoCapitalize="none" maxLength={254} required disabled={pending || disabled} />
        <button type="submit" disabled={pending || disabled}>{pending ? 'Sending…' : 'Send password reset email'}</button>
      </form>
      {notice && <p role={notice.error ? 'alert' : 'status'} className={notice.error ? 'settings-error' : undefined}>{notice.text}</p>}
    </details>
  </div>;
}

function AccountSettings() {
  const account = useAccount();
  const user = account.user;
  const provider = user?.sub?.split('|')[0];
  const passwordAccount = provider === 'auth0';
  const signInMethod = passwordAccount ? 'StockSight password' : provider === 'google-oauth2' ? 'Google' : 'Unavailable';

  return <section className="page-panel settings-panel" aria-labelledby="account-settings-title">
    <div className="panel-heading"><h2 id="account-settings-title">Account</h2></div>
    {account.isAuthenticated ? <>
      <div className="settings-row">
        <h3>Profile</h3>
        <dl className="settings-profile">
          <div><dt>Name</dt><dd>{user?.preferred_username || user?.name || user?.email || 'Your account'}</dd></div>
          <div><dt>Sign-in method</dt><dd>{signInMethod}</dd></div>
        </dl>
      </div>
      {passwordAccount && <PasswordRecovery key={user.sub} resetPassword={account.resetPassword} disabled={account.pending} />}
      <div className="settings-row settings-action">
        <h3>Session</h3>
        <button type="button" onClick={account.logout} disabled={account.pending}>Sign out</button>
      </div>
    </> : <div className="settings-row settings-action">
      <p role="status">{account.isLoading ? 'Checking your session…' : account.configured ? 'Sign in to manage your account.' : 'Sign-in is unavailable in this environment.'}</p>
      {account.configured && !account.isLoading && <a href="#/login" className="button-link">Sign in</a>}
    </div>}
  </section>;
}

export default function Settings({ chartDefaults, onChartDefaultsChange }) {
  return <section className="app-page settings-page">
    <h1>Settings</h1>
    <div className="settings-grid">
      <section className="page-panel settings-panel" aria-labelledby="chart-defaults-title">
        <div className="panel-heading">
          <h2 id="chart-defaults-title">Chart defaults</h2>
          <p>Applied when you open Analysis. Saved on this browser.</p>
        </div>
        {[['showSma', 'SMA 20'], ['showRsi', 'RSI 14']].map(([key, label]) => (
          <label key={key} className="settings-row settings-action settings-switch">
            <span>Show {label} by default</span>
            <input type="checkbox" role="switch" checked={chartDefaults[key]}
              onChange={event => onChartDefaultsChange({ ...chartDefaults, [key]: event.target.checked })} />
          </label>
        ))}
        <div className="settings-row">
          <button type="button" disabled={!chartDefaults.showSma && !chartDefaults.showRsi}
            onClick={() => onChartDefaultsChange(defaultChartSettings)}>Reset chart defaults</button>
        </div>
      </section>
      <AccountSettings />
    </div>
  </section>;
}
