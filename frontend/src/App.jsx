import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import Analysis from './Analysis.jsx';
import AuthPage from './AuthPage.jsx';
import AccountControls from './AccountControls.jsx';
import Compare from './Compare.jsx';
import Explore from './Explore.jsx';
import Preferences from './Preferences.jsx';
import Settings from './Settings.jsx';
import { readChartDefaults, saveChartDefaults } from './chart-defaults.js';
import SidebarHighlight from './SidebarHighlight.jsx';
import { Dashboard, Methodology, ModelPerformance, Predictions } from './Pages.jsx';
import { useAccount } from './auth-context.js';
import useCompareSelection, { compareHash } from './use-compare-selection.js';
import useWatchlist from './use-watchlist.js';
import usePreferences from './use-preferences.js';
import usePageRoute from './use-page-route.js';

// Predictions and Model performance stay reachable by link but leave the sidebar
// until an approved model exists (issue #19, Phase 0 decision).
const pages = [
  ['dashboard', 'Dashboard', 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z'],
  ['explore', 'Explore', 'M17 10.5a6.5 6.5 0 1 1-13 0a6.5 6.5 0 0 1 13 0M20 20l-4.9-4.9'],
  ['analysis', 'Analysis', 'M4 4v16h16M7 15l4-5 4 2 5-6'],
  ['compare', 'Compare', 'M4 20V10M10 20V4M16 20v-7M22 20H2'],
  ['methodology', 'Methodology', 'M6 4h9l3 3v13H6zM14 4v4h4M9 12h6m-6 4h6'],
];
const pageTitles = {
  ...Object.fromEntries(pages.map(([page, label]) => [page, label])),
  predictions: 'Predictions', performance: 'Model performance', preferences: 'Research preferences',
  settings: 'Settings',
  login: 'Log in', signup: 'Create an account', 'reset-password': 'Reset password',
};
const selectedSymbolKey = 'stocksight:selected-symbol';
const sidebarItemHeight = 48;
const sidebarItemGap = 5;
const reducedMotionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');

function subscribeToMotionPreference(listener) {
  reducedMotionPreference.addEventListener('change', listener);
  return () => reducedMotionPreference.removeEventListener('change', listener);
}

function getSavedSymbol() {
  try { return sessionStorage.getItem(selectedSymbolKey); }
  catch { return null; }
}

export default function App() {
  const route = usePageRoute();
  const activeIndex = pages.findIndex(([page]) => page === route.page);
  const reduceMotion = useSyncExternalStore(subscribeToMotionPreference, () => reducedMotionPreference.matches);
  const main = useRef(null);
  const navigation = useRef(null);
  const menuButton = useRef(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [chartDefaults, setChartDefaults] = useState(readChartDefaults);
  const [selectedSymbol, setSelectedSymbol] = useState(() => {
    const saved = route.symbol || getSavedSymbol();
    return saved && /^[A-Z][A-Z0-9.^=-]{0,15}$/.test(saved) ? saved : 'AAPL';
  });
  const symbol = route.symbol || selectedSymbol;
  const account = useAccount();
  const watchlist = useWatchlist();
  const preferences = usePreferences();
  const [inviteDismissed, setInviteDismissed] = useState(false);
  const compareSelection = useCompareSelection();
  const refreshWatchlist = watchlist.retry;
  const watchlistError = watchlist.error;
  const lastWatchlistPage = useRef(route.page);
  useEffect(() => {
    const previousPage = lastWatchlistPage.current;
    lastWatchlistPage.current = route.page;
    if (previousPage !== route.page && account.isAuthenticated && !watchlistError && ['dashboard', 'analysis', 'explore'].includes(route.page)) refreshWatchlist();
  }, [route.page, account.isAuthenticated, refreshWatchlist, watchlistError]);
  // Explore keeps its search/page in the URL; typing must not move focus away
  // from the search field, so only entering Explore counts as a navigation.
  const focusKey = ['explore', 'compare'].includes(route.page) ? route.page : route.hash;
  useEffect(() => {
    document.title = `${pageTitles[route.page] || 'Page not found'} | StockSight`;
    main.current?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [focusKey, route.page]);
  useEffect(() => {
    if (!menuOpen) return;
    const nav = navigation.current;
    const toggle = menuButton.current;
    (nav?.querySelector('[aria-current="page"]') || nav?.querySelector('a'))?.focus({ preventScroll: true });
    function close() { setMenuOpen(false); }
    function closeOutside(event) {
      if (!nav?.contains(event.target) && !toggle?.contains(event.target)) close();
    }
    function closeOnEscape(event) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      close();
      toggle?.focus({ preventScroll: true });
    }
    const mobile = window.matchMedia('(max-width: 740px)');
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    window.addEventListener('hashchange', close);
    mobile.addEventListener('change', close);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeOnEscape);
      window.removeEventListener('hashchange', close);
      mobile.removeEventListener('change', close);
    };
  }, [menuOpen]);
  useEffect(() => {
    if (['login', 'signup', 'reset-password'].includes(route.page) && account.isAuthenticated && !account.pending) window.location.hash = '/dashboard';
  }, [route.page, account.isAuthenticated, account.pending]);
  function rememberStock(value) {
    setSelectedSymbol(value);
    try { sessionStorage.setItem(selectedSymbolKey, value); }
    catch { /* The current tab keeps the selection in state when storage is unavailable. */ }
  }
  function selectStock(value) {
    rememberStock(value);
    window.location.hash = `/analysis?symbol=${encodeURIComponent(value)}`;
  }
  function followSidebarLink(href) {
    rememberStock(symbol);
    if (menuOpen) {
      setMenuOpen(false);
      if (href === route.hash) main.current?.focus({ preventScroll: true });
    }
  }
  function updateChartDefaults(next) {
    setChartDefaults(next);
    saveChartDefaults(next);
  }
  if (['login', 'signup', 'reset-password'].includes(route.page)) return <AuthPage key={route.page} mode={route.page} />;
  return <div className="site-shell">
    <a className="skip-link" href="#main" onClick={event => { event.preventDefault(); main.current?.focus(); }}>Skip to content</a>
    <header className="masthead">
      <div className="masthead-inner wrap">
        <div className="masthead-brand">
          <button ref={menuButton} type="button" className="menu-toggle" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="site-navigation" onClick={() => setMenuOpen(open => !open)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d={menuOpen ? 'm6 6 12 12M18 6 6 18' : 'M4 6h16M4 12h16M4 18h16'} /></svg>
          </button>
          <a className="brand" href="#/dashboard" onClick={() => rememberStock(symbol)} aria-label="StockSight home">
            <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 23V9M5 23h22M10 19l6-7 5 3 7-9" /></svg>
            StockSight<span className="brand-divider" aria-hidden="true" /><span className="brand-school">UCONN</span>
          </a>
        </div>
        <AccountControls />
      </div>
    </header>
    <nav id="site-navigation" ref={navigation} className="site-sidebar" aria-label="Main navigation" data-open={menuOpen}
      style={{ '--sidebar-item-height': `${sidebarItemHeight}px`, '--sidebar-item-gap': `${sidebarItemGap}px` }}
      onBlur={event => {
        if (menuOpen && !event.currentTarget.contains(event.relatedTarget) && event.relatedTarget !== menuButton.current) setMenuOpen(false);
      }}>
      <div className="sidebar-items">
        {pages.map(([page, label, icon], index) => {
          const href = page === 'compare' ? compareHash(compareSelection.symbols)
            : `#/${page}${page === 'analysis' ? `?symbol=${encodeURIComponent(symbol)}` : ''}`;
          return <a key={page} href={href} aria-label={label} aria-current={activeIndex === index ? 'page' : undefined} onClick={() => followSidebarLink(href)}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d={icon} /></svg>
            <span aria-hidden="true">{label}</span>
          </a>;
        })}
        {activeIndex >= 0 && <SidebarHighlight activeIndex={activeIndex} itemHeight={sidebarItemHeight} itemGap={sidebarItemGap} reduceMotion={reduceMotion} />}
      </div>
      <div className="sidebar-footer">
        <a href="#/settings" aria-label="Settings" aria-current={route.page === 'settings' ? 'page' : undefined}
          onClick={() => followSidebarLink('#/settings')}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 3-.5 2.2-2 .9-2-.9-2 3.5 1.6 1.5v2.5L3.5 14l2 3.5 2-.8 2 .9.5 2.4h4l.5-2.4 2-.9 2 .8 2-3.5-1.6-1.3v-2.5l1.6-1.5-2-3.5-2 .9-2-.9L14 3z"/><circle cx="12" cy="11.5" r="2.5"/></svg>
          <span aria-hidden="true">Settings</span>
        </a>
      </div>
    </nav>
    <div className="app-content">
    <main ref={main} id="main" className="wrap" tabIndex="-1">
      {account.error && <div role="alert" className="account-error">{account.error}</div>}
      {route.page === 'explore' && <Explore {...route.explore} preferences={preferences} watchlist={watchlist} selection={compareSelection} onOpen={selectStock} />}
      {route.page === 'analysis' && <Analysis symbol={symbol} onSelectSymbol={selectStock} watchlist={watchlist} selection={compareSelection} defaultRange={preferences.defaultRange} chartDefaults={chartDefaults} />}
      {route.page === 'compare' && <Compare symbols={route.compare.symbols} range={route.compare.range ?? preferences.defaultRange ?? '1y'} linkRange={route.compare.range} selection={compareSelection} onOpen={selectStock} />}
      {route.page === 'dashboard' && <Dashboard watchlist={watchlist} selection={compareSelection} onOpen={selectStock}
        invite={account.isAuthenticated && preferences.data?.saved === false && !inviteDismissed} onDismissInvite={() => setInviteDismissed(true)} />}
      {route.page === 'predictions' && <Predictions symbol={symbol} />}
      {route.page === 'performance' && <ModelPerformance />}
      {route.page === 'methodology' && <Methodology />}
      {route.page === 'preferences' && <Preferences preferences={preferences} />}
      {route.page === 'settings' && <Settings chartDefaults={chartDefaults} onChartDefaultsChange={updateChartDefaults} />}
      {route.page === 'not-found' && <section className="app-page"><h1>Page not found</h1><div className="page-panel unavailable-state"><p>This page is unavailable.</p><a className="button-link" href="#/analysis">Go to stock analysis</a></div></section>}
    </main>
    <footer className="footer wrap"><span>StockSight <span className="footer-dot">/</span> UConn</span><p>For education and research. Not financial advice.</p><a href="#/methodology" onClick={() => rememberStock(symbol)}>Data & methodology</a></footer>
    </div>
  </div>;
}
