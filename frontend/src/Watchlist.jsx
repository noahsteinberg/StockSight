import { useAccount } from './auth-context.js';

export default function Watchlist({ watchlist, onOpen }) {
  const account = useAccount();
  const signedIn = account.isAuthenticated;
  return (
    <section id="watchlist" className="watchlist" aria-labelledby="watchlist-title">
      <div className="section-heading"><h2 id="watchlist-title">Your watchlist</h2><span>{signedIn ? `${watchlist.items.length} / 100 stocks` : 'Personal dashboard'}</span></div>
      {account.isLoading ? <p role="status">Checking sign-in…</p> : !account.configured ?
        <p className="watchlist-empty">Sign-in is being set up. Stock analysis is available.</p> : !signedIn ?
          <div className="watchlist-empty"><p>Sign in to keep your saved stocks here.</p><button type="button" onClick={() => account.login()} disabled={account.pending}>Sign in to your watchlist</button></div> : <>
            {watchlist.loading && <p role="status">Loading your watchlist…</p>}
            {watchlist.error && <div role="alert" className="watchlist-feedback"><p>{watchlist.error}</p><button type="button" onClick={watchlist.retry}>Retry watchlist</button><button type="button" onClick={() => account.login()}>Sign in again</button></div>}
            {!watchlist.loading && !watchlist.error && watchlist.items.length === 0 && <div className="watchlist-empty"><p>No saved stocks yet.</p><a href="#analysis">Find a stock to save ↑</a></div>}
            {watchlist.items.length > 0 && <ul className="saved-stocks">{watchlist.items.map(stock => <li key={stock.symbol}>
              <a href="#analysis" onClick={() => onOpen(stock.symbol)} aria-label={`Open ${stock.symbol} analysis`}><strong>{stock.symbol}</strong><span>{stock.name}</span><span aria-hidden="true">↗</span></a>
              <button type="button" disabled={watchlist.mutation.busy} onClick={() => watchlist.remove(stock.symbol)} aria-label={`Remove ${stock.symbol}`}>Remove</button>
            </li>)}</ul>}
            <a className="text-link" href="#analysis">Back to stock analysis ↑</a>
          </>}
      {watchlist.mutation.error && <p role="alert" className="watchlist-feedback">{watchlist.mutation.error}</p>}
      {watchlist.mutation.success && <p role="status" className="watchlist-feedback">{watchlist.mutation.success}</p>}
    </section>
  );
}
