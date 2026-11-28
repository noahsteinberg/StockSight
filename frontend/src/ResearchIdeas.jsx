import { useEffect, useState } from 'react';
import { useAccount } from './auth-context.js';
import { WatchlistStar } from './AnalysisWatchlist.jsx';
import { CompareToggle } from './CompareTray.jsx';

function parseIdeas(body, method) {
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  if (!body || body.calculation_version !== 'research-ideas-v1' || body.method !== method ||
      !Number.isInteger(body.eligible_count) || !Number.isInteger(body.matching_count) ||
      body.eligible_count < 0 || body.matching_count < body.eligible_count ||
      !Array.isArray(body.items) || body.items.length > 6 ||
      body.items.length !== Math.min(6, body.eligible_count) ||
      new Set(body.items.map(item => item.symbol)).size !== body.items.length ||
      body.items.some(item => !/^[A-Z][A-Z0-9.^=-]{0,15}$/.test(item.symbol) ||
        typeof item.name !== 'string' || !finite(item.metric_pct) ||
        (method === 'variability' && item.metric_pct < 0) ||
        item.as_of !== body.latest_session || typeof item.reason !== 'string' ||
        typeof item.series_revision !== 'string' || !item.series_revision)) {
    throw new Error('Research ideas were incomplete. Try again.');
  }
  return body;
}

export default function ResearchIdeas({ query, sector, mine, watchlist, selection }) {
  const account = useAccount();
  const [method, setMethod] = useState('momentum');
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null);
  const owner = mine ? account.user?.sub : 'public';
  const key = JSON.stringify([query, sector, mine, owner, method, attempt]);
  const fetchPrivate = account.authorizedFetch;
  const allowed = !mine || account.isAuthenticated;
  const current = result?.key === key ? result : null;
  useEffect(() => {
    if (!allowed) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    let active = true;
    const params = new URLSearchParams({ query, method });
    if (!mine && sector) params.set('sector', sector);
    const path = `/api/${mine ? 'me/' : ''}research-ideas?${params}`;
    const request = mine ? fetchPrivate(path, { signal: controller.signal }) : fetch(path, { signal: controller.signal });
    request.then(async response => {
      if (!response.ok) throw new Error('Research ideas are temporarily unavailable.');
      const data = parseIdeas(await response.json(), method);
      if (active) setResult({ key, data });
    }).catch(error => {
      if (active) setResult({ key, error: error.name === 'AbortError' ? 'Research ideas timed out. Try again.' : error.message });
    }).finally(() => clearTimeout(timer));
    return () => { active = false; controller.abort(); clearTimeout(timer); };
  }, [key, query, sector, mine, method, allowed, fetchPrivate]);

  return <section className="page-panel research-ideas" aria-labelledby="ideas-title">
    <div className="panel-heading"><h2 id="ideas-title">Research ideas</h2>
      <label>Find candidates by <select value={method} onChange={event => setMethod(event.target.value)}>
        <option value="momentum">Recent momentum</option>
        <option value="variability">Lower historical variability</option>
      </select></label></div>
    <p>Suggestions follow your search and sector filters. Explore all supported stocks in the list below.</p>
    <p className="muted">{method === 'momentum' ? 'Stocks with the largest price changes over 20 stored sessions.' : 'Stocks with smaller day-to-day price swings over 20 stored changes.'} These describe past prices. Future returns and suitability have not been evaluated.</p>
    <details><summary>How these suggestions are chosen</summary><p>Momentum measures percentage price change over 20 stored sessions. Variability measures the sample standard deviation of 20 daily percentage changes. Both require 21 valid closing prices through the newest stored date and exclude recorded split windows.</p></details>
    {!allowed ? <p>Sign in to use your saved sectors, or turn off Use my preferences.</p>
      : !current ? <p role="status">Finding research ideas…</p>
      : current.error ? <div role="alert"><p>{current.error}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Retry research ideas</button></div>
      : <>
        <p role="status">{current.data.eligible_count} of {current.data.matching_count} matching stocks eligible
          {current.data.latest_session && ` · as of ${current.data.latest_session}`}.
          {current.data.eligible_count < current.data.matching_count && ' Earlier data, short history, and recorded split windows are excluded.'}</p>
        {!current.data.items.length && <p>No candidates meet these filters and history requirements. Try another sector or clear your filters.</p>}
        <ul className="idea-grid">{current.data.items.map(item => <li key={item.symbol}>
          <a aria-label={`Research candidate ${item.symbol} ${item.name}`} href={`#/analysis?symbol=${encodeURIComponent(item.symbol)}`}><strong>{item.symbol}</strong> {item.name}</a>
          <span className="muted">{item.sector || 'Sector unknown'}</span>
          <p>{item.reason}</p>
          <div className="row-actions"><a href={`#/analysis?symbol=${encodeURIComponent(item.symbol)}`}>View analysis</a>
            <WatchlistStar symbol={item.symbol} watchlist={watchlist} context="Research idea" /><CompareToggle symbol={item.symbol} selection={selection} context="Research idea" /></div>
        </li>)}</ul>
      </>}
  </section>;
}
