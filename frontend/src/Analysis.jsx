import { useEffect, useState } from 'react';
import PricePlot from './PricePlot.jsx';
import { useAccount } from './auth-context.js';
import useIndicators from './use-indicators.js';

const ranges = [['1mo', '1M'], ['3mo', '3M'], ['1y', '1Y'], ['all', 'Max']];
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

function responseError(status, searching = false) {
  if (status === 404) return 'Symbol unavailable. Search for a supported stock.';
  if (status === 503) return searching ? 'Could not search stocks: price storage is unavailable.' : 'Could not load prices: price storage is unavailable.';
  if (status === 422) return 'Invalid request. Check your search or range.';
  return searching ? 'Could not search stocks. Check that the API is running.' : 'Could not load prices. Check that the API is running.';
}

export default function Analysis({ symbol, onSelectSymbol, watchlist }) {
  const account = useAccount();
  const [inputError, setInputError] = useState('');
  const [draft, setDraft] = useState({ symbol, value: symbol });
  const input = draft.symbol === symbol ? draft.value : symbol;
  function setInput(value) { setDraft({ symbol, value }); }
  const [range, setRange] = useState('3mo');
  const [result, setResult] = useState({ loading: true });
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState(null);
  const [searchRequest, setSearchRequest] = useState(null);
  const [search, setSearch] = useState(null);
  const [showSma, setShowSma] = useState(false);
  const [showRsi, setShowRsi] = useState(false);
  const requestKey = `${symbol}:${range}:${retry}`;

  useEffect(() => {
    if (!searchRequest) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/api/stocks?query=${encodeURIComponent(searchRequest.query)}`, { signal: controller.signal });
        if (!response.ok) throw new Error(responseError(response.status, true));
        const matches = await response.json();
        if (active) setSearch({ matches, query: searchRequest.query });
      } catch (error) {
        if (active) setSearch({ error: error.name === 'AbortError' ? 'Search timed out. Try again.' : error.message });
      } finally { clearTimeout(timeout); }
    }
    load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [searchRequest]);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/prices?range=${range}`, { signal: controller.signal });
        if (!response.ok) throw new Error(responseError(response.status));
        const data = await response.json();
        if (active) setResult({ data, symbol, key: requestKey });
      } catch (error) {
        if (active) setResult({ error: error.name === 'AbortError' ? 'Request timed out. Try again.' : error.message, symbol, key: requestKey });
      } finally { clearTimeout(timeout); }
    }
    load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [symbol, range, retry, requestKey]);

  function reload() { setSelected(null); setResult({ loading: true, symbol }); }
  function startSearch(event) {
    event.preventDefault();
    const query = input.trim();
    if (!query) { setInputError('Enter a ticker symbol or company name.'); return; }
    setInputError('');
    setSearch({ loading: true });
    setSearchRequest({ query });
  }
  function openStock(next) {
    reload();
    onSelectSymbol(next);
    setInput(next);
    setSearch(null);
    setSearchRequest(null);
    setRetry(value => value + 1);
  }
  const loadingPrices = result.loading || result.key !== requestKey;
  const bars = !loadingPrices && result.data ? result.data.bars : [];
  const selectedIndex = selected?.key === requestKey && selected.index < bars.length ? selected.index : null;
  const current = bars[selectedIndex ?? bars.length - 1];
  const indicators = useIndicators(symbol, range, showSma || showRsi, !loadingPrices ? result.data : null);
  const indicatorPoint = indicators.data?.points[selectedIndex ?? bars.length - 1];
  const rangeChange = bars.length > 1 && bars[0].close !== 0 ? (bars.at(-1).close / bars[0].close - 1) * 100 : null;

  return (
    <section className="analysis" id="analysis" aria-labelledby="analysis-title">
      <div className="section-heading"><h1 id="analysis-title">Stock analysis</h1><span className="historical-badge">Historical prices</span></div>
      <form className="analysis-toolbar" onSubmit={startSearch} role="search">
        <label className="sr-only" htmlFor="ticker">Ticker</label>
        <div className="search-input"><span aria-hidden="true">⌕</span><input id="ticker" placeholder="Ticker or company name" value={input} onChange={event => { setInput(event.target.value); setInputError(''); }} aria-invalid={Boolean(inputError)} aria-describedby={inputError ? 'ticker-error search-hint' : 'search-hint'} maxLength={40} required autoComplete="off" spellCheck="false" /></div>
        <button type="submit">Search</button>
      </form>
      <p id="search-hint" className="search-hint">Search by ticker or company name.</p>
      {inputError && <p id="ticker-error" role="alert" className="validation-error">{inputError}</p>}
      {search && <div className="stock-search" aria-label="Stock search results" aria-live="polite" aria-busy={Boolean(search.loading)}>
        {search.loading && <p>Searching stocks.</p>}
        {search.error && <div role="alert"><p>{search.error}</p><button type="button" onClick={() => { setSearch({ loading: true }); setSearchRequest({ ...searchRequest }); }}>Retry search</button></div>}
        {search.matches?.length === 0 && <p>No matching stocks for &ldquo;{search.query}&rdquo;. Try another ticker or company name.</p>}
        {search.matches?.length > 0 && <><div className="search-results-heading"><p>{search.matches.length} {search.matches.length === 1 ? 'match' : 'matches'}{search.matches.length === 50 ? ' · Up to 50 results; narrow your search' : ''}</p><button type="button" onClick={() => { setSearch(null); setSearchRequest(null); }}>Close results</button></div><ul>{search.matches.map(stock => <li key={stock.symbol}><button type="button" onClick={() => openStock(stock.symbol)}>{stock.symbol} <span>{stock.name}</span></button></li>)}</ul></>}
      </div>}
      <div className="chart-card">
      <div className="chart-toolbar"><span>Price & volume <span className="muted">· USD</span></span><fieldset><legend className="sr-only">Price history range</legend>{ranges.map(([value, label]) => <button key={value} type="button" aria-pressed={range === value} onClick={() => { if (range !== value) { reload(); setRange(value); } }}>{label}</button>)}</fieldset></div>
      <div aria-live="polite" aria-busy={Boolean(loadingPrices)}>
        {loadingPrices && <div className="analysis-message loading-state" role="status"><span className="loading-spinner" aria-hidden="true" /><p>Loading prices.</p><div className="chart-skeleton" aria-hidden="true" /></div>}
        {result.error && !loadingPrices && <div className="analysis-message error-state" role="alert"><p>{result.error}</p><button onClick={() => { reload(); setRetry(value => value + 1); }}>Retry</button></div>}
        {result.data && result.symbol === symbol && !loadingPrices && bars.length === 0 && <p className="analysis-message">No observations in this range.</p>}
      </div>
      {current && <>
        <div className="quote"><div><h2>{result.data.symbol} <span>{result.data.name}</span></h2><div className="price-value"><strong>{money.format(current.close)}</strong><span className="quote-date">{current.date}<br />{selectedIndex == null ? 'Latest stored close' : 'Selected close'}</span></div></div>{rangeChange != null && <div className={`range-change ${rangeChange < 0 ? 'negative' : 'positive'}`}><strong>{rangeChange >= 0 ? '+' : ''}{rangeChange.toFixed(2)}%</strong><span>Displayed period</span></div>}</div>
        {account.configured && <div className="save-stock"><button type="button"
          disabled={account.isLoading || watchlist.mutation.busy || (account.isAuthenticated && (watchlist.loading || Boolean(watchlist.error) || watchlist.items.some(stock => stock.symbol === result.data.symbol)))}
          onClick={() => account.isAuthenticated ? watchlist.save(result.data.symbol) : account.login()}>
          {!account.isAuthenticated ? 'Sign in to save' : watchlist.items.some(stock => stock.symbol === result.data.symbol) ? 'Saved to watchlist' : 'Save to watchlist'}
        </button><a href="#/dashboard">Your watchlist ↗</a></div>}
        <a className="forecast-link" href={`#/predictions?symbol=${encodeURIComponent(symbol)}`}>Predictions for {symbol} <span aria-hidden="true">↗</span></a>
        <div className="indicator-toolbar" role="group" aria-label="Technical indicators"><span className="muted">Indicators</span><button type="button" aria-pressed={showSma} onClick={() => setShowSma(value => !value)}><span className="legend-swatch sma" aria-hidden="true" />SMA 20</button><button type="button" aria-pressed={showRsi} onClick={() => setShowRsi(value => !value)}><span className="legend-swatch rsi" aria-hidden="true" />RSI 14</button><span className="price-legend"><span className="legend-swatch" aria-hidden="true" />Close</span></div>
        {indicators.loading && <p role="status" className="indicator-feedback">Loading indicators…</p>}
        {indicators.error && <div role="alert" className="indicator-feedback error-state"><p>{indicators.error}</p>{indicators.mismatch ? <button type="button" onClick={() => { reload(); setRetry(value => value + 1); indicators.retry(); }}>Reload prices & indicators</button> : <button type="button" onClick={indicators.retry}>Retry indicators</button>}</div>}
        <PricePlot bars={bars} points={indicators.data?.points} showSma={showSma} showRsi={showRsi} selectedIndex={selectedIndex} />
        <label className="observation-picker">Inspect date<input aria-label="Inspect historical observation" type="range" min="0" max={bars.length-1} value={selectedIndex ?? bars.length-1} aria-valuetext={`${current.date}, ${money.format(current.close)}`} onChange={event => setSelected({ key: requestKey, index: Number(event.target.value) })} /><span>{current.date}</span></label>
        <dl className="observation-stats"><div><dt>Open · USD</dt><dd>{money.format(current.open)}</dd></div><div><dt>High · USD</dt><dd>{money.format(current.high)}</dd></div><div><dt>Low · USD</dt><dd>{money.format(current.low)}</dd></div><div><dt>Volume</dt><dd>{current.volume.toLocaleString('en-US')}</dd></div></dl>
        {indicators.data && <div className="indicator-values" aria-live="polite">{showSma && <span>SMA 20 · {indicatorPoint?.sma_20 == null ? 'Insufficient history (20 observations required)' : money.format(indicatorPoint.sma_20)}</span>}{showRsi && <span>RSI 14 · {indicatorPoint?.rsi_14 == null ? 'Insufficient history (15 observations required)' : `${indicatorPoint.rsi_14.toFixed(2)} / 100`}</span>}<p className="muted">SMA averages 20 stored closes. RSI measures momentum on a 0–100 scale. Neither is a forecast.</p></div>}
        <div id="data-details" className="data-details"><p className="data-note">As of {result.data.as_of} · {bars.length} sessions · {bars[0].date} to {bars.at(-1).date} · <a href={result.data.source_url}>Source: {result.data.source}</a><br />{result.data.adjustment} · Historical data, not live quotes.</p>
        {result.data.has_earlier && <p className="data-note">Earlier stored sessions are outside this view. Showing the latest {result.data.session_limit} sessions.{range === 'all' ? ' Max is capped at 2,000 sessions.' : ' Choose a longer range to see more.'}</p>}
        </div>
        <details><summary>Price observations</summary><div className="table-scroll"><table><thead><tr><th scope="col">Date</th><th scope="col">Close (USD)</th><th scope="col">Volume</th></tr></thead><tbody>{bars.map(bar => <tr key={bar.date}><th scope="row">{bar.date}</th><td>{money.format(bar.close)}</td><td>{bar.volume.toLocaleString('en-US')}</td></tr>)}</tbody></table></div></details>
      </>}
      </div>
    </section>
  );
}
