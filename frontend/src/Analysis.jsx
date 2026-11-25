import { useEffect, useRef, useState } from 'react';
import HistoricalChart from './HistoricalChart.jsx';
import StockSearchInput from './StockSearchInput.jsx';
import AnalysisWatchlist, { WatchlistStar } from './AnalysisWatchlist.jsx';
import useIndicators from './use-indicators.js';

const ranges = [['1mo', '1M'], ['3mo', '3M'], ['1y', '1Y'], ['all', 'Max']];

function responseError(status, searching = false) {
  if (status === 404) return 'Symbol unavailable. Search for a supported stock.';
  if (status === 503) return searching ? 'Could not search stocks: price storage is unavailable.' : 'Could not load prices: price storage is unavailable.';
  if (status === 422) return 'Invalid request. Check your search or range.';
  return searching ? 'Could not search stocks. Check that the API is running.' : 'Could not load prices. Check that the API is running.';
}

export default function Analysis({ symbol, onSelectSymbol, watchlist, chartDefaults }) {
  const tickerInput = useRef(null);
  const [inputError, setInputError] = useState('');
  const [draft, setDraft] = useState({ symbol, value: symbol });
  const input = draft.symbol === symbol ? draft.value : symbol;
  function setInput(value) { setDraft({ symbol, value }); }
  const [range, setRange] = useState('3mo');
  const [result, setResult] = useState({ loading: true });
  const [retry, setRetry] = useState(0);
  const [searchRequest, setSearchRequest] = useState(null);
  const [search, setSearch] = useState(null);
  const [showSma, setShowSma] = useState(chartDefaults.showSma);
  const [showRsi, setShowRsi] = useState(chartDefaults.showRsi);
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

  function reload() { setResult({ loading: true, symbol }); }
  function closeSearch() {
    setSearch(null);
    setSearchRequest(null);
    tickerInput.current?.focus();
  }
  function clearSearch() {
    setInput('');
    setInputError('');
    closeSearch();
  }
  function handleSearchKeys(event) {
    if (event.key !== 'Escape' || !search) return;
    event.preventDefault();
    closeSearch();
  }
  function startSearch(event) {
    event.preventDefault();
    const query = input.trim();
    if (!query) {
      closeSearch();
      setInputError('Enter a ticker symbol or company name.');
      return;
    }
    setInputError('');
    setSearch({ loading: true });
    setSearchRequest({ query });
  }
  function openStock(next) {
    reload();
    onSelectSymbol(next);
    setInput(next);
    setInputError('');
    setSearch(null);
    setSearchRequest(null);
    setRetry(value => value + 1);
  }
  const loadingPrices = result.loading || result.key !== requestKey;
  const data = loadingPrices ? null : result.data;
  const indicators = useIndicators(symbol, range, showSma || showRsi, data);

  return (
    <section className="analysis" id="analysis" aria-labelledby="analysis-title">
      <div className="section-heading"><h1 id="analysis-title">Stock analysis</h1><span className="historical-badge">Stored daily history</span></div>
      <div className="analysis-search" onKeyDown={handleSearchKeys}>
      <form className="analysis-toolbar" onSubmit={startSearch} role="search" noValidate>
        <label className="sr-only" htmlFor="ticker">Ticker</label>
        <StockSearchInput inputRef={tickerInput} value={input} invalid={inputError}
          onChange={value => { setInput(value); setInputError(''); }} onClear={clearSearch} onSelect={openStock} />
        <button type="submit">Search</button>
      </form>
      <AnalysisWatchlist symbol={symbol} watchlist={watchlist} onOpen={openStock} />
      {inputError && <p id="ticker-error" role="alert" className="validation-error">{inputError}</p>}
      {search && <div className="stock-search" aria-label="Stock search results" aria-live="polite" aria-busy={Boolean(search.loading)}>
        <div className="search-results-heading">
          <span>{search.matches ? `${search.matches.length} ${search.matches.length === 1 ? 'match' : 'matches'}${search.matches.length === 50 ? ' · Refine your search to see more' : ''}` : 'Search results'}</span>
          <button type="button" onClick={closeSearch}>Close results</button>
        </div>
        {search.loading && <p>Searching stocks.</p>}
        {search.error && <div role="alert"><p>{search.error}</p><button type="button" onClick={() => { setSearch({ loading: true }); setSearchRequest({ ...searchRequest }); }}>Retry search</button></div>}
        {search.matches?.length === 0 && <p>No matching stocks for &ldquo;{search.query}&rdquo;. Try another ticker or company name.</p>}
        {search.matches?.length > 0 && <ul>{search.matches.map(stock => <li key={stock.symbol}><button type="button" onClick={() => openStock(stock.symbol)}>{stock.symbol} <span>{stock.name}</span></button></li>)}</ul>}
      </div>}
      </div>
      <div className="chart-card">
      <div className="chart-toolbar"><span>Price & volume <span className="muted">· USD</span></span><fieldset><legend className="sr-only">Price history range</legend>{ranges.map(([value, label]) => <button key={value} type="button" aria-pressed={range === value} onClick={() => { if (range !== value) { reload(); setRange(value); } }}>{label}</button>)}</fieldset></div>
      <div aria-live="polite" aria-busy={Boolean(loadingPrices)}>
        {loadingPrices && <div className="analysis-message loading-state" role="status"><span className="loading-spinner" aria-hidden="true" /><p>Loading prices.</p><div className="chart-skeleton" aria-hidden="true" /></div>}
        {result.error && !loadingPrices && <div className="analysis-message error-state" role="alert"><p>{result.error}</p><button onClick={() => { reload(); setRetry(value => value + 1); }}>Retry</button></div>}
        {data?.bars.length === 0 && <p className="analysis-message">No observations in this range.</p>}
      </div>
      {data?.bars.length > 0 && <HistoricalChart
        key={requestKey} data={data} range={range} showSma={showSma} showRsi={showRsi}
        titleAction={<WatchlistStar symbol={data.symbol} watchlist={watchlist} />}
        onToggleSma={() => setShowSma(value => !value)} onToggleRsi={() => setShowRsi(value => !value)}
        indicators={indicators} onReload={() => { reload(); setRetry(value => value + 1); indicators.retry(); }}>
        <div className="chart-actions">
          <button type="button" onClick={() => { reload(); setRetry(value => value + 1); indicators.retry(); watchlist.retry(); }}>Refresh data</button>
          <a href={`#/predictions?symbol=${encodeURIComponent(symbol)}`}>Predictions for {symbol} <span aria-hidden="true">↗</span></a>
        </div>
      </HistoricalChart>}
      </div>
    </section>
  );
}
