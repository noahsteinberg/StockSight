import { useEffect, useState } from 'react';

const ranges = [['1mo', '1M'], ['3mo', '3M'], ['1y', '1Y'], ['all', 'All']];
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export default function Analysis() {
  const [input, setInput] = useState('AAPL');
  const [symbol, setSymbol] = useState('AAPL');
  const [range, setRange] = useState('3mo');
  const [result, setResult] = useState({ loading: true });
  const [retry, setRetry] = useState(0);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/prices?range=${range}`, { signal: controller.signal });
        if (!response.ok) throw new Error(response.status === 404 ? 'Symbol unavailable. Try AAPL.' : 'Could not load prices. Check that the API is running.');
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
  const bars = result.data?.bars || [];
  const current = bars[selected ?? bars.length - 1];
  const min = bars.length ? Math.min(...bars.map(bar => bar.close)) : 0;
  const max = bars.length ? Math.max(...bars.map(bar => bar.close)) : 1;
  const points = bars.map((bar, index) => `${40 + index / Math.max(1, bars.length - 1) * 900},${30 + (max - bar.close) / (max - min || 1) * 200}`).join(' ');
  const volumeMax = Math.max(1, ...bars.map(bar => bar.volume));

  return (
    <section className="analysis" id="analysis" aria-labelledby="analysis-title">
      <div className="section-heading"><h1 id="analysis-title">Stock analysis</h1><span>Historical demo · AAPL</span></div>
      <form className="analysis-toolbar" onSubmit={event => { event.preventDefault(); const next = input.trim().toUpperCase(); if (!next) return; reload(); setSymbol(next); setRetry(value => value + 1); }}>
        <label htmlFor="ticker">Ticker</label>
        <input id="ticker" value={input} onChange={event => setInput(event.target.value)} maxLength={12} required autoComplete="off" spellCheck="false" />
        <button type="submit">Search</button>
        <fieldset><legend className="sr-only">Price history range</legend>{ranges.map(([value, label]) => <button key={value} type="button" aria-pressed={range === value} onClick={() => { if (range !== value) { reload(); setRange(value); } }}>{label}</button>)}</fieldset>
      </form>
      <div aria-live="polite" aria-busy={Boolean(result.loading)}>
        {result.loading && <p className="analysis-message">Loading prices…</p>}
        {result.error && <div className="analysis-message" role="alert"><p>{result.error}</p><button onClick={() => { reload(); setRetry(value => value + 1); }}>Retry</button></div>}
        {result.data && bars.length === 0 && <p className="analysis-message">No observations in this range.</p>}
      </div>
      {current && <>
        <div className="quote"><div><h2>{result.data.symbol} <span>{result.data.name}</span></h2><strong>{money.format(current.close)}</strong></div><p>{current.date}<br /><span>Volume {current.volume.toLocaleString('en-US')}</span></p></div>
        <svg className="price-plot" viewBox="0 0 980 320" role="img" aria-label={`AAPL closing price and volume from ${bars[0].date} to ${bars.at(-1).date}`}>
          {[0, 1, 2].map(index => <g key={index}><line x1="40" x2="940" y1={30 + index * 100} y2={30 + index * 100} className="chart-grid" /><text x="40" y={23 + index * 100}>{money.format(max - (max-min) * index/2)}</text></g>)}
          <polyline points={points} fill="none" className="price-line" />
          {bars.map((bar, index) => <rect key={bar.date} x={40 + index / Math.max(1,bars.length-1) * 900} y={290 - bar.volume/volumeMax*40} width={Math.max(1, 800/bars.length)} height={bar.volume/volumeMax*40} className="volume-bar" />)}
          <text x="40" y="315">{bars[0].date}</text><text x="940" y="315" textAnchor="end">{bars.at(-1).date}</text>
        </svg>
        <label className="observation-picker">Inspect date<input aria-label="Inspect historical observation" type="range" min="0" max={bars.length-1} value={selected ?? bars.length-1} onChange={event => setSelected(Number(event.target.value))} /></label>
        <p className="data-note">As of {result.data.as_of} · Unadjusted USD · {bars.length} sessions · <a href={result.data.source_url}>Source: Plotly</a></p>
        <details><summary>Price observations</summary><div className="table-scroll"><table><thead><tr><th scope="col">Date</th><th scope="col">Close (USD)</th><th scope="col">Volume</th></tr></thead><tbody>{bars.map(bar => <tr key={bar.date}><th scope="row">{bar.date}</th><td>{money.format(bar.close)}</td><td>{bar.volume.toLocaleString('en-US')}</td></tr>)}</tbody></table></div></details>
      </>}
    </section>
  );
}
