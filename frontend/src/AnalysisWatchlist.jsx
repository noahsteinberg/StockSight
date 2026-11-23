import { useAccount } from './auth-context.js';

const percent = new Intl.NumberFormat('en-US', {
  style: 'percent', signDisplay: 'exceptZero', minimumFractionDigits: 2, maximumFractionDigits: 2,
});

export function WatchlistStar({ symbol, watchlist }) {
  const account = useAccount();
  const saved = watchlist.items.some(stock => stock.symbol === symbol);
  const disabled = !account.configured || account.isLoading || account.pending ||
    watchlist.loading || Boolean(watchlist.error) || watchlist.mutation.busy;
  const action = saved ? `Remove ${symbol} from watchlist` : `Save ${symbol} to watchlist`;
  const label = account.isAuthenticated ? `Watchlist for ${symbol}` :
    account.configured ? `Sign in to save ${symbol}` : 'Sign-in unavailable';

  return <button type="button" className="watchlist-star" aria-pressed={account.isAuthenticated ? saved : undefined}
    aria-label={label} title={account.isAuthenticated ? action : label} disabled={disabled}
    onClick={() => {
      if (!account.isAuthenticated) account.login();
      else if (saved) watchlist.remove(symbol);
      else watchlist.save(symbol);
    }}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.76 5.59 6.17.9-4.47 4.35 1.06 6.15L12 17.09l-5.52 2.9 1.06-6.15-4.47-4.35 6.17-.9L12 3Z" /></svg>
  </button>;
}

export default function AnalysisWatchlist({ symbol, watchlist, onOpen }) {
  return <section className="analysis-watchlist" aria-label="Watchlist">
    {watchlist.items.length > 0 ? <ul className="watchlist-chips" aria-label="Saved stocks">
      {watchlist.items.map(stock => {
        const change = stock.daily_change_pct;
        const display = change == null ? '—' : percent.format(change / 100);
        const direction = change > 0 ? 'positive' : change < 0 ? 'negative' : 'muted';
        return <li key={stock.symbol}>
          <a href={`#/analysis?symbol=${encodeURIComponent(stock.symbol)}`}
            aria-current={stock.symbol === symbol ? 'true' : undefined}
            aria-label={`Open ${stock.symbol} analysis, daily change ${change == null ? 'unavailable' : display}`}
            title="Change between the latest two stored closes"
            onClick={event => {
              if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
              event.preventDefault();
              onOpen(stock.symbol);
            }}>
            <strong>{stock.symbol}</strong><span className={direction}>{display}</span>
          </a>
        </li>;
      })}
    </ul> : !watchlist.error && <p className="watchlist-hint">
      {watchlist.loading ? 'Loading your watchlist…' : 'Star a stock to add it here'}
    </p>}
    {watchlist.error && <div role="alert" className="watchlist-feedback">
      <p>{watchlist.error}</p><button type="button" onClick={watchlist.retry}>Retry watchlist</button>
    </div>}
    {watchlist.mutation.error && <p role="alert" className="watchlist-feedback">{watchlist.mutation.error}</p>}
    <span className="sr-only" role="status">{watchlist.mutation.success || ''}</span>
  </section>;
}
