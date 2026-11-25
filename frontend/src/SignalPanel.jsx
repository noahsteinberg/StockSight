import { reasonMessages } from './signal-api.js';
import useSignal from './use-signal.js';

function AvailableSignal({ data }) {
  // Only validated, dated fields are shown; no probability is invented when null.
  return <dl className="definition-list signal-facts">
    <div><dt>Target</dt><dd>{data.target_kind.replaceAll('_', ' ')} over {data.horizon_sessions} session · for {data.target_session}</dd></div>
    <div><dt>Inputs through</dt><dd>{data.as_of_session} · published {data.published_at}</dd></div>
    {data.universe_percentile !== null && <div><dt>Relative rank</dt><dd>{data.universe_percentile}th percentile among supported stocks (a ranking, not a probability)</dd></div>}
    {data.probability !== null && <div><dt>Probability</dt><dd>{Math.round(data.probability * 100)}%</dd></div>}
    <div><dt>Model</dt><dd>{data.model_version} · data {data.data_snapshot} · {data.provenance}</dd></div>
  </dl>;
}

export default function SignalPanel({ symbol, compact = false }) {
  const signal = useSignal(symbol);
  if (signal.data === null) return null;
  const available = signal.data?.status === 'available';
  return <section className={`page-panel signal-panel${compact ? ' compact' : ''}`} aria-labelledby={`signal-title-${compact ? 'c' : 'f'}`} aria-busy={Boolean(signal.loading)}>
    <div className="panel-heading">
      <h2 id={`signal-title-${compact ? 'c' : 'f'}`}>Research signal · {symbol}</h2>
      {signal.data && <span className="historical-badge">{available ? 'Available' : 'Unavailable'}</span>}
    </div>
    {signal.loading && <p role="status">Checking the signal status for {symbol}…</p>}
    {signal.error && <div role="alert" className="signal-error"><p>{signal.error}</p><button type="button" onClick={signal.retry}>Retry signal check</button></div>}
    {signal.data && !available && <>
      <p role="status">{reasonMessages[signal.data.unavailable_reason]}</p>
      <p className="signal-note">A signal appears here only after a model passes evaluation on held-out data and its outputs are stored with dates and versions. Nothing is generated when you open this page, and past prices or indicators are not forecasts.</p>
    </>}
    {available && <AvailableSignal data={signal.data} />}
    <div className="page-actions">
      {compact && <a href={`#/predictions?symbol=${encodeURIComponent(symbol)}`}>Signal details for {symbol} <span aria-hidden="true">↗</span></a>}
      <a href="#/performance">Model performance <span aria-hidden="true">↗</span></a>
    </div>
  </section>;
}

export function SignalStatus({ symbol }) {
  const signal = useSignal(symbol);
  const text = signal.loading ? 'checking…'
    : signal.error ? 'status unavailable'
    : signal.data === null ? 'not supported'
    : signal.data.status === 'available' ? 'signal available'
    : 'no approved model';
  return <li><strong>{symbol}</strong> {text}</li>;
}
