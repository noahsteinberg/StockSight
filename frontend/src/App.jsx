import { useState } from 'react';
import Analysis from './Analysis.jsx';
import AccountControls from './AccountControls.jsx';
import Watchlist from './Watchlist.jsx';
import { useAccount } from './auth-context.js';
import useWatchlist from './use-watchlist.js';

const repo = 'https://github.com/noahsteinberg/StockSight';

export default function App() {
  const [symbol, setSymbol] = useState(() => {
    const saved = sessionStorage.getItem('stocksight:selected-symbol');
    return saved && /^[A-Z][A-Z0-9.^=-]{0,15}$/.test(saved) ? saved : 'AAPL';
  });
  const account = useAccount();
  const watchlist = useWatchlist();
  function selectStock(value) {
    setSymbol(value);
    sessionStorage.setItem('stocksight:selected-symbol', value);
  }
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="masthead">
      <div className="masthead-inner wrap">
        <a className="brand" href="#analysis" aria-label="StockSight home">
          <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 23V9M5 23h22M10 19l6-7 5 3 7-9" /></svg>
          StockSight<span className="brand-divider" aria-hidden="true" /><span className="brand-school">UCONN</span>
        </a>
        <AccountControls />
      </div>
    </header>
    <div className="navigation-bar">
      <nav className="wrap" aria-label="Main navigation">
        <a href="#analysis">Analysis</a><a href="#watchlist">Watchlist</a><a href="#project">About</a>
        <span className="navigation-context">Historical research</span>
      </nav>
    </div>
    <main id="main" className="wrap" tabIndex="-1">
      {account.error && <div role="alert" className="account-error">{account.error}</div>}
      <div className="workspace">
        <Analysis symbol={symbol} onSelectSymbol={selectStock} watchlist={watchlist} />
        <aside className="workspace-sidebar"><Watchlist watchlist={watchlist} onOpen={selectStock} selectedSymbol={symbol} /></aside>
      </div>
      <details id="project" className="project">
        <summary>About StockSight <span>UConn · CSE 4095</span></summary>
        <div className="project-copy"><p>An educational stock research project by Noah Steinberg, Gavin Javier Pino, Parth Sachdev, and Vladislav Lagutin.</p><p>Search historical prices, inspect technical indicators, and keep a private watchlist. Predictions and model evaluation are in development.</p><a href={repo}>GitHub ↗</a><a href={`${repo}/blob/main/SPECIFICATION.md`}>Project specification ↗</a></div>
      </details>
    </main>
    <footer className="footer wrap"><span>StockSight <span className="footer-dot">/</span> UConn</span><p>For education and research. Not financial advice.</p><a href="#analysis">Back to top ↑</a></footer>
  </>;
}
