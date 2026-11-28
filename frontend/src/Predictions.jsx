import { useEffect, useState } from 'react';
import PatternExplorer from './PatternExplorer.jsx';
import SignalPanel from './SignalPanel.jsx';
import StockSearchInput from './StockSearchInput.jsx';
import { fetchPatternSnapshot } from './pattern-api.js';
import { patternHash } from './pattern-route.js';

export function PatternResults({ symbol, horizon, chartHistory, onReloadChart }) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null);
  const key = `${symbol}:${attempt}`;
  const current = result?.key === key ? result : null;
  function reloadHistory() {
    onReloadChart?.();
    setAttempt(value => value + 1);
  }
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    let active = true;
    fetchPatternSnapshot(symbol, controller.signal)
      .then(data => { if (active) setResult({ key, data }); })
      .catch(error => { if (active) setResult({ key, error: error.name === 'AbortError' ? 'Stored history timed out. Try again.' : error.message }); })
      .finally(() => clearTimeout(timer));
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [symbol, key]);
  if (!current) return <div className="page-panel analysis-message" role="status">Loading stored history for {symbol}…</div>;
  if (current.error) return <div className="page-panel analysis-message" role="alert"><p>{current.error}</p>
    <button type="button" onClick={reloadHistory}>Retry stored history</button></div>;
  if (chartHistory && (chartHistory.snapshot_id !== current.data.snapshot_id || chartHistory.as_of !== current.data.as_of)) {
    return <div className="page-panel analysis-message" role="alert">
      <p>The stored history changed. Refresh the chart and patterns together.</p>
      <button type="button" onClick={reloadHistory}>Refresh chart and patterns</button>
    </div>;
  }
  return <PatternExplorer symbol={symbol} horizon={horizon} history={current.data}
    onChangeHorizon={value => { window.location.hash = patternHash(symbol, value); }}
    onReloadHistory={reloadHistory} />;
}

export default function Predictions({ symbol }) {
  const [draft, setDraft] = useState({ symbol, value: symbol });
  const [error, setError] = useState('');
  const value = draft.symbol === symbol ? draft.value : symbol;
  function open(next) {
    const ticker = next.trim().toUpperCase();
    if (!/^[A-Z][A-Z0-9.^=-]{0,15}$/.test(ticker)) {
      setError('Enter a ticker or choose a company from the suggestions.'); return;
    }
    setError(''); setDraft({ symbol: ticker, value: ticker });
    window.location.hash = `#/predictions?symbol=${encodeURIComponent(ticker)}&model=1`;
  }
  return <section className="app-page predictions-page" aria-labelledby="predictions-title">
    <div className="page-heading"><h1 id="predictions-title">Predictions</h1><span className="historical-badge">Model unavailable</span></div>
    <p className="predictions-intro">Model forecasts will appear here after evaluation and approval. Explore historical patterns within each stock’s Analysis page.</p>
    <div className="page-panel prediction-request">
      <div><span className="note-label">SELECTED STOCK</span><h2>{symbol}</h2><a href={`#/analysis?symbol=${encodeURIComponent(symbol)}`}>View {symbol} analysis ↗</a></div>
      <form className="prediction-search" onSubmit={event => { event.preventDefault(); open(value); }} noValidate>
        <label htmlFor="prediction-ticker">Choose a stock</label>
        <div><StockSearchInput id="prediction-ticker" value={value} invalid={error} errorId="prediction-search-error"
          onChange={next => { setDraft({ symbol, value: next }); setError(''); }} onSelect={open}
          onClear={() => setDraft({ symbol, value: '' })} />
          <button type="submit">Open model status</button></div>
        {error && <p id="prediction-search-error" className="validation-error" role="alert">{error}</p>}
      </form>
    </div>
    <details key={symbol} className="page-panel help-disclosure model-details" open>
      <summary>ML prediction status and model information</summary>
      <div><SignalPanel key={symbol} symbol={symbol} />
        <h2>Prediction history</h2><h3>Prediction history is unavailable</h3>
        <p>Saved model forecasts and their outcomes will appear here after a model is approved. Historical matches above are a separate research tool.</p>
        <a href="#/performance">Model performance</a>
      </div>
    </details>
  </section>;
}
