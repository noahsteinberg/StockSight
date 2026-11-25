import { useAccount } from './auth-context.js';
import { useState } from 'react';
import { CompareToggle } from './CompareTray.jsx';

export default function Watchlist({ watchlist, selection, onOpen }) {
  const account = useAccount();
  const signedIn = account.isAuthenticated;
  const [filter, setFilter] = useState({ owner: null, value: '' });
  const query = filter.owner === account.user?.sub ? filter.value : '';
  const matches = watchlist.items.filter(stock => `${stock.symbol} ${stock.name}`.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <section id="watchlist" className="watchlist" aria-labelledby="watchlist-title">
      <div className="section-heading"><h2 id="watchlist-title">Your watchlist</h2><span>{signedIn ? `${watchlist.items.length} / 100` : 'Private'}</span></div>
      {account.isLoading ? <p role="status">Checking sign-in…</p> : !account.configured ?
        <p className="watchlist-empty">Sign-in is being set up. Stock analysis is available.</p> : !signedIn ?
          <div className="watchlist-empty"><p>Sign in to keep your saved stocks here.</p><button type="button" onClick={() => account.login()} disabled={account.pending}>Sign in to your watchlist</button></div> : <>
            {watchlist.loading && <p role="status">Loading your watchlist…</p>}
            {watchlist.error && <div role="alert" className="watchlist-feedback"><p>{watchlist.error}</p><button type="button" onClick={watchlist.retry}>Retry watchlist</button><button type="button" onClick={() => account.login()}>Sign in again</button></div>}
            {!watchlist.loading && !watchlist.error && watchlist.items.length === 0 && <div className="watchlist-empty"><p>No saved stocks yet.</p><a href="#/explore">Explore stocks to save ↑</a></div>}
            {watchlist.items.length > 0 && <><div className="watchlist-filter"><label htmlFor="saved-filter">Filter saved stocks</label><input id="saved-filter" value={query} onChange={event => setFilter({ owner: account.user?.sub, value: event.target.value })} placeholder="Ticker or company name" type="search" maxLength={40} /><span role="status">{matches.length} of {watchlist.items.length} stocks</span></div>{matches.length === 0 ? <div className="watchlist-empty"><p>No saved stocks match “{query}”.</p><button type="button" onClick={() => setFilter({ owner: account.user?.sub, value: '' })}>Clear filter</button></div> : <div className="table-scroll dashboard-table"><table><caption className="sr-only">Your saved stocks</caption><thead><tr><th scope="col">Stock</th><th scope="col">Saved · UTC</th><th scope="col">Actions</th></tr></thead><tbody>{matches.map(stock => <tr key={stock.symbol}><th scope="row"><a href={`#/analysis?symbol=${encodeURIComponent(stock.symbol)}`} onClick={() => onOpen(stock.symbol)} aria-label={`Open ${stock.symbol} analysis`}><strong>{stock.symbol}</strong><span>{stock.name}</span></a></th><td>{new Date(stock.added_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })}</td><td><div className="row-actions">{selection && <CompareToggle symbol={stock.symbol} selection={selection} />}<button type="button" disabled={watchlist.mutation.busy} onClick={() => watchlist.remove(stock.symbol)} aria-label={`Remove ${stock.symbol}`}>Remove</button></div></td></tr>)}</tbody></table></div>}</>}
            <a className="text-link" href="#/analysis">Back to stock analysis ↑</a>
          </>}
      {watchlist.mutation.error && <p role="alert" className="watchlist-feedback">{watchlist.mutation.error}</p>}
      {watchlist.mutation.success && <p role="status" className="watchlist-feedback">{watchlist.mutation.success}</p>}
    </section>
  );
}
