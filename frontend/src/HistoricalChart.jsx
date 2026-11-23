import { useEffect, useId, useMemo, useRef, useState } from 'react';
import PricePlot from './PricePlot.jsx';

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const percentage = new Intl.NumberFormat('en-US', { style: 'percent', signDisplay: 'exceptZero', minimumFractionDigits: 2, maximumFractionDigits: 2 });

function downloadPrices(symbol, range, bars, replaying) {
  const rows = bars.map(({ date, open, high, low, close, volume }) => [date, open, high, low, close, volume].join(','));
  const csv = ['Date,Open (USD),High (USD),Low (USD),Close (USD),Volume', ...rows].join('\r\n');
  const link = document.createElement('a');
  const suffix = replaying ? `-through-${bars.at(-1).date}` : '';
  link.href = `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
  link.download = `${symbol}-historical-prices-${range}${suffix}.csv`;
  link.click();
}

export default function HistoricalChart({ data, range, showSma, showRsi, onToggleSma, onToggleRsi, indicators, onReload, titleAction, children }) {
  const [choosingStart, setChoosingStart] = useState(false);
  const [replay, setReplay] = useState(null);
  const replayId = useId();
  const nextStep = useRef(null);
  const replaying = replay !== null;
  const total = data.bars.length;
  const visibleCount = replaying ? replay.through + 1 : total;
  const bars = useMemo(() => data.bars.slice(0, visibleCount), [data.bars, visibleCount]);
  const points = useMemo(() => indicators.data?.points.slice(0, visibleCount), [indicators.data, visibleCount]);
  const latest = bars.at(-1);
  const change = bars.length > 1 && bars[0].close ? latest.close / bars[0].close - 1 : null;
  const replayDone = replaying && visibleCount === total;

  useEffect(() => {
    if (replaying) nextStep.current?.focus({ preventScroll: true });
  }, [replaying]);

  function startReplay(event) {
    event.preventDefault();
    const index = Number(new FormData(event.currentTarget).get('start'));
    setReplay({ start: index, through: index, run: 0 });
    setChoosingStart(false);
  }

  return <>
    <div className="quote">
      <div>
        <div className="quote-title">
          <h2>{data.symbol} <span>{data.name}</span></h2>
          {titleAction}
        </div>
        <div className="price-value">
          <strong>{money.format(latest.close)}</strong>
          <span className="quote-date">{latest.date}<br />{replaying ? 'Replay close' : 'Latest stored close'}</span>
        </div>
      </div>
      {change !== null && <div className={`range-change ${change < 0 ? 'negative' : 'positive'}`}>
        <strong>{percentage.format(change)}</strong>
        <span>{replaying ? 'Revealed range' : 'Range change'}</span>
      </div>}
    </div>
    <div className="indicator-toolbar" role="group" aria-label="Chart controls">
      <span className="muted">Indicators</span>
      <button type="button" aria-pressed={showSma} onClick={onToggleSma}><span className="legend-swatch sma" aria-hidden="true" />SMA 20</button>
      <button type="button" aria-pressed={showRsi} onClick={onToggleRsi}><span className="legend-swatch rsi" aria-hidden="true" />RSI 14</button>
      {total > 1 && <button type="button" className="replay-toggle" aria-expanded={choosingStart || replaying} aria-controls={replayId}
        onClick={() => replaying ? setReplay(null) : setChoosingStart(value => !value)}>
        {replaying ? 'Exit replay' : 'Historical replay'}
      </button>}
    </div>
    <div id={replayId} hidden={!choosingStart && !replaying}>
      {choosingStart && <form className="replay-panel" onSubmit={startReplay}>
        <label htmlFor={`${replayId}-start`}>Start session</label>
        <select id={`${replayId}-start`} name="start" defaultValue={Math.max(0, total - 21)}>
          {data.bars.slice(0, -1).map((bar, index) => <option key={bar.date} value={index}>{bar.date}</option>)}
        </select>
        <button type="submit">Start replay</button>
      </form>}
      {replaying && <div className="replay-panel">
        <p role="status"><span>Replay through</span> <strong>{latest.date}</strong>{replayDone && <span> · Complete</span>}</p>
        <div className="replay-actions">
          <button type="button" ref={nextStep} aria-disabled={replayDone} onClick={() => {
            if (!replayDone) setReplay(value => ({ ...value, through: value.through + 1 }));
          }}>Next session <span aria-hidden="true">→</span></button>
          <button type="button" onClick={() => setReplay(value => ({ ...value, through: value.start, run: value.run + 1 }))}>Restart</button>
        </div>
      </div>}
    </div>
    {indicators.loading && <p role="status" className="indicator-feedback">Loading indicators…</p>}
    {indicators.error && <div role="alert" className="indicator-feedback error-state"><p>{indicators.error}</p>{indicators.mismatch ?
      <button type="button" onClick={onReload}>Reload prices & indicators</button> :
      <button type="button" onClick={indicators.retry}>Retry indicators</button>}</div>}
    <PricePlot key={replay ? replay.run : 'history'} bars={bars} points={points} showSma={showSma} showRsi={showRsi} replaying={replaying} />
    {children}
    <div id="data-details" className="data-details">
      <p className="data-note">
        {replaying ? 'Replay through' : 'As of'} {replaying ? latest.date : data.as_of} · {bars.length} sessions · {bars[0].date} to {latest.date} · <a href={data.source_url}>Source: {data.source}</a><br />
        {data.adjustment}
      </p>
      {data.has_earlier && !replaying && <p className="data-note">Earlier stored sessions are outside this view. Showing the latest {data.session_limit} sessions.{range === 'all' ? ' Max is capped at 2,000 sessions.' : ' Choose a longer range to see more.'}</p>}
      <button className="csv-button" type="button" onClick={() => downloadPrices(data.symbol, range, bars, replaying)}>Download price CSV</button>
    </div>
    <details>
      <summary>Price observations</summary>
      <div className="table-scroll">
        <table>
          <thead><tr><th scope="col">Date</th><th scope="col">Close (USD)</th><th scope="col">Volume</th></tr></thead>
          <tbody>{bars.map(bar => <tr key={bar.date}><th scope="row">{bar.date}</th><td>{money.format(bar.close)}</td><td>{bar.volume.toLocaleString('en-US')}</td></tr>)}</tbody>
        </table>
      </div>
    </details>
  </>;
}
