import { useEffect, useRef, useState } from 'react';
import Analysis from './Analysis.jsx';
import AccountControls from './AccountControls.jsx';
import Watchlist from './Watchlist.jsx';
import { Dashboard, Methodology, ModelPerformance, Predictions } from './Pages.jsx';
import { useAccount } from './auth-context.js';
import useWatchlist from './use-watchlist.js';
import usePageRoute from './use-page-route.js';

const pages = [
  ['dashboard', 'Dashboard'], ['analysis', 'Analysis'], ['predictions', 'Predictions'],
  ['performance', 'Model performance'], ['methodology', 'Methodology'],
];

export default function App() {
  const route = usePageRoute();
  const main = useRef(null);
  const [selectedSymbol, setSelectedSymbol] = useState(() => {
    const saved = new URLSearchParams(window.location.hash.split('?')[1]).get('symbol')?.trim().toUpperCase() || sessionStorage.getItem('stocksight:selected-symbol');
    return saved && /^[A-Z][A-Z0-9.^=-]{0,15}$/.test(saved) ? saved : 'AAPL';
  });
  const symbol = route.symbol || selectedSymbol;
  const account = useAccount();
  const watchlist = useWatchlist();
  useEffect(() => {
    document.title = `${pages.find(([page]) => page === route.page)?.[1] || 'Page not found'} | StockSight`;
    main.current?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [route.hash, route.page]);
  function rememberStock(value) {
    setSelectedSymbol(value);
    sessionStorage.setItem('stocksight:selected-symbol', value);
  }
  function selectStock(value) {
    rememberStock(value);
    window.location.hash = `/analysis?symbol=${encodeURIComponent(value)}`;
  }
  return <>
    <a className="skip-link" href="#main" onClick={event => { event.preventDefault(); main.current?.focus(); }}>Skip to content</a>
    <header className="masthead">
      <div className="masthead-inner wrap">
        <a className="brand" href="#/dashboard" onClick={() => rememberStock(symbol)} aria-label="StockSight home">
          <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 23V9M5 23h22M10 19l6-7 5 3 7-9" /></svg>
          StockSight<span className="brand-divider" aria-hidden="true" /><span className="brand-school">UCONN</span>
        </a>
        <AccountControls />
      </div>
    </header>
    <div className="navigation-bar">
      <nav className="wrap" aria-label="Main navigation">
        {pages.map(([page, label]) => <a key={page} onClick={() => rememberStock(symbol)} href={`#/${page}${page === 'analysis' || page === 'predictions' ? `?symbol=${encodeURIComponent(symbol)}` : ''}`} aria-current={route.page === page ? 'page' : undefined}>{label}</a>)}
      </nav>
    </div>
    <main ref={main} id="main" className="wrap" tabIndex="-1">
      {account.error && <div role="alert" className="account-error">{account.error}</div>}
      {route.page === 'analysis' && <div className="workspace">
        <Analysis symbol={symbol} onSelectSymbol={selectStock} watchlist={watchlist} />
        <aside className="workspace-sidebar"><Watchlist watchlist={watchlist} onOpen={selectStock} selectedSymbol={symbol} /></aside>
      </div>}
      {route.page === 'dashboard' && <Dashboard watchlist={watchlist} onOpen={selectStock} symbol={symbol} />}
      {route.page === 'predictions' && <Predictions symbol={symbol} />}
      {route.page === 'performance' && <ModelPerformance />}
      {route.page === 'methodology' && <Methodology />}
      {route.page === 'not-found' && <section className="app-page"><h1>Page not found</h1><div className="page-panel unavailable-state"><p>This page is unavailable.</p><a className="button-link" href="#/analysis">Go to stock analysis</a></div></section>}
    </main>
    <footer className="footer wrap"><span>StockSight <span className="footer-dot">/</span> UConn</span><p>For education and research. Not financial advice.</p><a href="#/methodology" onClick={() => rememberStock(symbol)}>Data & methodology</a></footer>
  </>;
}
