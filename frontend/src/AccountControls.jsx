import { useAccount } from './auth-context.js';

export default function AccountControls() {
  const account = useAccount();
  if (account.isLoading) return <span className="account-status" role="status">Checking sign-in…</span>;
  if (!account.configured) return <span className="account-status">Sign-in unavailable</span>;
  return (
    <div className="account-controls">
      {account.isAuthenticated ? <>
        <span className="account-name">{account.user?.name || account.user?.email || 'Your account'}</span>
        <a className="account-link" href="#/preferences">Preferences</a>
        <button type="button" disabled={account.pending} onClick={account.logout}>Sign out</button>
      </> : <>
        <button type="button" disabled={account.pending} onClick={() => account.login()}>Sign in</button>
        <button type="button" className="primary-button" disabled={account.pending} onClick={() => account.login(true)}>Create account</button>
      </>}
    </div>
  );
}
