import { useEffect, useState } from 'react';
import PricePlot from './PricePlot.jsx';

const ranges = [['1mo', '1M'], ['3mo', '3M'], ['1y', '1Y'], ['all', 'Max']];
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

function responseError(status, searching = false) {
  if (status === 404) return 'Symbol unavailable. Search for a supported stock.';
  if (status === 422) return 'Invalid request. Check your search or range.';
  return searching ? 'Could not search stocks. Check that the API is running.' : 'Could not load prices. Check that the API is running.';
}

export default function Analysis() {
  const [inputError, setInputError] = useState('');
  const [input, setInput] = useState('AAPL');
  const [symbol, setSymbol] = useState('AAPL');
  const [range, setRange] = useState('3mo');
  const [result, setResult] = useState({ loading: true });
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState(null);
  const [searchRequest, setSearchRequest] = useState(null);
  const [search, setSearch] = useState(null);

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
        if (active) setResult({ data });
      } catch (error) {
        if (active) setResult({ error: error.name === 'AbortError' ? 'Request timed out. Try again.' : error.message });
      } finally { clearTimeout(timeout); }
    }
    load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [symbol, range, retry]);

  function reload() { setSelected(null); setResult({ loading: true }); }
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
    setSymbol(next);
    setInput(next);
    setSearch(null);
    setSearchRequest(null);
    setRetry(value => value + 1);
  }
  const bars = result.data?.bars || [];
  const current = bars[selected ?? bars.length - 1];

  return (
    <section className="analysis" id="analysis" aria-labelledby="analysis-title">
      <div className="section-heading"><h1 id="analysis-title">Stock analysis</h1><span>Historical prices</span></div>
      <form className="analysis-toolbar" onSubmit={startSearch}>
        <label htmlFor="ticker">Ticker</label>
        <input id="ticker" value={input} onChange={event => { setInput(event.target.value); setInputError(''); }} aria-invalid={Boolean(inputError)} aria-describedby={inputError ? 'ticker-error search-hint' : 'search-hint'} maxLength={40} required autoComplete="off" spellCheck="false" />
        <button type="submit">Search</button>
        <fieldset><legend className="sr-only">Price history range</legend>{ranges.map(([value, label]) => <button key={value} type="button" aria-pressed={range === value} onClick={() => { if (range !== value) { reload(); setRange(value); } }}>{label}</button>)}</fieldset>
      </form>
      <p id="search-hint" className="data-note">Search by ticker or company name. Max shows up to 2,000 latest trading sessions.</p>
      {inputError && <p id="ticker-error" role="alert" className="validation-error">{inputError}</p>}
      {search && <div className="stock-search" aria-label="Stock search results" aria-live="polite" aria-busy={Boolean(search.loading)}>
        {search.loading && <p>Searching stocks.</p>}
        {search.error && <div role="alert"><p>{search.error}</p><button type="button" onClick={() => { setSearch({ loading: true }); setSearchRequest({ ...searchRequest }); }}>Retry search</button></div>}
        {search.matches?.length === 0 && <p>No matching stocks for &ldquo;{search.query}&rdquo;. Try another ticker or company name.</p>}
        {search.matches?.length > 0 && <><p>Choose a stock to view its history. Up to 50 matches; narrow your search if needed.</p><ul>{search.matches.map(stock => <li key={stock.symbol}><button type="button" onClick={() => openStock(stock.symbol)}>{stock.symbol} <span>{stock.name}</span></button></li>)}</ul></>}
      </div>}
      <div aria-live="polite" aria-busy={Boolean(result.loading)}>
        {result.loading && <p className="analysis-message">Loading prices.</p>}
        {result.error && <div className="analysis-message" role="alert"><p>{result.error}</p><button onClick={() => { reload(); setRetry(value => value + 1); }}>Retry</button></div>}
        {result.data && bars.length === 0 && <p className="analysis-message">No observations in this range.</p>}
      </div>
      {current && <>
        <div className="quote"><div><h2>{result.data.symbol} <span>{result.data.name}</span></h2><strong>{money.format(current.close)}</strong></div><p>{current.date}<br /><span>Volume {current.volume.toLocaleString('en-US')}</span></p></div>
        <PricePlot bars={bars} />
        <label className="observation-picker">Inspect date<input aria-label="Inspect historical observation" type="range" min="0" max={bars.length-1} value={selected ?? bars.length-1} aria-valuetext={`${current.date}, ${money.format(current.close)}`} onChange={event => setSelected(Number(event.target.value))} /></label>
        <p className="data-note">As of {result.data.as_of} · {bars.length} sessions · {bars[0].date} to {bars.at(-1).date} · <a href={result.data.source_url}>Source: {result.data.source}</a><br />{result.data.adjustment} · Historical data, not live quotes.</p>
        {result.data.has_earlier && <p className="data-note">Earlier stored sessions are outside this view. Showing the latest {result.data.session_limit} sessions.{range === 'all' ? ' Max is capped at 2,000 sessions.' : ' Choose a longer range to see more.'}</p>}
        <details><summary>Price observations</summary><div className="table-scroll"><table><thead><tr><th scope="col">Date</th><th scope="col">Close (USD)</th><th scope="col">Volume</th></tr></thead><tbody>{bars.map(bar => <tr key={bar.date}><th scope="row">{bar.date}</th><td>{money.format(bar.close)}</td><td>{bar.volume.toLocaleString('en-US')}</td></tr>)}</tbody></table></div></details>
      </>}
    </section>
  );
}
