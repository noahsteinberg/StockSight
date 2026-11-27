import { useEffect, useState } from 'react';
import { fetchPatterns } from './pattern-api.js';

const percent = value => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
const tone = value => value > 0 ? 'pattern-positive' : value < 0 ? 'pattern-negative' : '';

function PatternChart({ data, selected }) {
  const values = data.matches.flatMap(match => match.path);
  const low = Math.min(0, ...values), high = Math.max(0, ...values);
  const padding = Math.max((high - low) * .08, .1);
  const min = low - padding, max = high + padding;
  const x = i => i / data.horizon_sessions * 800;
  const y = value => 210 - (value - min) / (max - min) * 210;
  const path = values => values.map((value, i) => `${x(i)},${y(value)}`).join(' ');
  const band = [...data.points.map(p => `${x(p.session)},${y(p.upper_quartile)}`),
    ...[...data.points].reverse().map(p => `${x(p.session)},${y(p.lower_quartile)}`)].join(' ');
  return <div className="pattern-plot" aria-label="Historical outcome paths">
    <div className="pattern-ylabels" aria-hidden="true"><span>{percent(max)}</span><span>{percent((max + min) / 2)}</span><span>{percent(min)}</span></div>
    <div className="pattern-plot-main">
      <svg viewBox="0 0 800 210" preserveAspectRatio="none" role="img"
        aria-label={`${data.matched_count} historical paths over ${data.horizon_sessions} stored sessions. Median ending change ${percent(data.summary.median_change_pct)}. Historical comparisons, not a forecast.`}>
        {[0, .5, 1].map(v => <line key={v} x1="0" x2="800" y1={v * 210} y2={v * 210} stroke="#e2e7ee" />)}
        <line x1="0" x2="800" y1={y(0)} y2={y(0)} stroke="#9cabc0" strokeDasharray="5 5" />
        <polygon points={band} fill="#dce9f8" opacity=".7" />
        {data.matches.map((match, i) => <polyline key={match.date} points={path(match.path)} fill="none"
          stroke={selected === i ? '#b87516' : '#8ba0b9'} strokeWidth={selected === i ? 2.5 : 1}
          opacity={selected === null || selected === i ? .8 : .25} vectorEffect="non-scaling-stroke" />)}
        <polyline points={path(data.points.map(p => p.median))} fill="none" stroke="#1858a0" strokeWidth="3" vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="pattern-xlabels"><span>Similar setup</span><span>{data.horizon_sessions} stored sessions later</span></div>
    </div>
  </div>;
}

export default function PatternExplorer({ symbol, history, horizon, onChangeHorizon, onReloadHistory }) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null);
  const [selection, setSelection] = useState(null);
  const key = `${symbol}:${horizon}:${attempt}`;
  const selected = selection?.key === key ? selection.index : null;
  function setSelected(index) { setSelection(index === null ? null : { key, index }); }
  const loading = result?.key !== key;
  const data = result?.key === key ? result.data : null;
  const error = result?.key === key ? result.error : null;
  const mismatch = data && history && (data.snapshot_id !== history.snapshot_id || data.as_of !== history.as_of);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timer = setTimeout(() => controller.abort(), 10000);
    fetchPatterns(symbol, horizon, controller.signal)
      .then(data => { if (active) setResult({ data, key }); })
      .catch(error => { if (active) setResult({ key, error: error.name === 'AbortError' ? 'Historical patterns timed out. Try again.' : error.message }); })
      .finally(() => clearTimeout(timer));
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [symbol, horizon, attempt, key]);

  function retry() { setSelected(null); setAttempt(value => value + 1); }
  const ready = data?.status === 'available' && !mismatch && history;
  return <section className="pattern-explorer" aria-labelledby="pattern-title">
    <div className="pattern-header">
      <div><span className="pattern-eyebrow">A CLOSER LOOK AT HISTORY</span><h2 id="pattern-title">Historical Pattern Explorer</h2>
        <p>When {symbol} looked similar before, what happened next?</p></div>
      <span className="pattern-badge">Historical comparisons</span>
    </div>
    <div className="pattern-controls">
      <fieldset><legend>Look ahead in past examples</legend>{[5, 21].map(value => <button key={value} type="button"
        aria-pressed={horizon === value} onClick={() => { if (horizon !== value) onChangeHorizon(value); }}>{value} sessions</button>)}</fieldset>
      <button type="button" disabled={Boolean(loading)} onClick={retry}>Refresh matches</button>
    </div>
    <div aria-live="polite" aria-busy={loading}>
      {loading && <p className="pattern-message" role="status">Finding historical comparisons for {symbol}…</p>}
      {error && <div className="pattern-message" role="alert"><p>{error}</p><button type="button" onClick={retry}>Retry patterns</button></div>}
      {mismatch && <div className="pattern-message" role="alert"><p>The stored history changed. Refresh the history and matches to use the same data.</p>
        <button type="button" onClick={onReloadHistory}>Refresh history and matches</button></div>}
      {data?.status === 'unavailable' && !mismatch && history && <p className="pattern-message">{data.reason === 'invalid_history' ?
        'This history needs a data check before comparisons can be shown.' :
        'There are not enough usable, non-overlapping examples for this setup. Try 5 sessions or another stock.'}</p>}
    </div>
    {ready && <>
      <div className="pattern-setup"><strong>Setup as of {data.as_of}</strong>
        <span>20-session change <b>{percent(data.current_setup.change_20_pct)}</b></span>
        <span>Daily variability <b>{data.current_setup.daily_variability_pct.toFixed(2)}%</b></span>
        <span>Vs. 50-session average <b>{percent(data.current_setup.vs_average_50_pct)}</b></span>
      </div>
      <div className="pattern-summary">
        <div><span>Middle past outcome</span><strong className={tone(data.summary.median_change_pct)}>{percent(data.summary.median_change_pct)}</strong><small>Median price change after {horizon} sessions</small></div>
        <div><span>Middle half of outcomes</span><strong>{percent(data.summary.lower_quartile_pct)} <span>to</span> {percent(data.summary.upper_quartile_pct)}</strong><small>Historical range, not a prediction interval</small></div>
        <div><span>{data.matched_count} matched periods</span><strong>{data.summary.rose} rose <span>·</span> {data.summary.fell} fell</strong><small>{data.summary.unchanged ? `${data.summary.unchanged} unchanged · ` : ''}Outcome windows do not overlap</small></div>
      </div>
      <div className="pattern-chart-heading"><h3>How those periods unfolded</h3><div className="pattern-legend"><span>─ Median</span><span>▰ Middle half</span><span>─ Individual periods</span></div></div>
      <PatternChart data={data} selected={selected} />
      <div className="pattern-selection" aria-live="polite">{selected === null ? 'Select an example below to highlight its path.' :
        <>Highlighted: {data.matches[selected].date} → {data.matches[selected].end_date} <button type="button" onClick={() => setSelected(null)}>Clear highlight</button></>}</div>
      <details className="pattern-examples"><summary>Inspect the {data.matched_count} historical examples</summary>
        <div className="pattern-table-scroll" tabIndex="0" role="region" aria-label="Historical pattern examples">
          <table><caption className="sr-only">Nearest historical comparisons for {symbol}, ordered by setup similarity</caption>
            <thead><tr><th scope="col">Setup date</th><th scope="col">End date</th><th scope="col">20-session change</th><th scope="col">Daily variability</th><th scope="col">Vs. 50-session avg.</th><th scope="col">Actual later change</th></tr></thead>
            <tbody>{data.matches.map((match, i) => <tr key={match.date} data-highlighted={selected === i}>
              <td><button type="button" aria-pressed={selected === i} onClick={() => setSelected(selected === i ? null : i)}>{match.date}</button></td>
              <td>{match.end_date}</td><td>{percent(match.setup.change_20_pct)}</td><td>{match.setup.daily_variability_pct.toFixed(2)}%</td><td>{percent(match.setup.vs_average_50_pct)}</td>
              <td className={tone(match.change_pct)}>{percent(match.change_pct)}</td></tr>)}</tbody></table>
        </div>
      </details>
      <p className="pattern-source">{data.matched_count} closest non-overlapping periods from {data.calculation_sessions.toLocaleString()} stored observations · {data.calculation_start} to {data.as_of} · <a href={data.source_url} target="_blank" rel="noopener noreferrer">{data.source}</a></p>
      <details className="pattern-method"><summary>How matching works and what this can tell you</summary>
        <p>We compare 20-session price change, the sample standard deviation of 20 daily close changes, and price relative to its 50-session average. Each input uses only prices known on its setup date. Features are scaled using prior eligible setups, with equal weight. The closest examples are approximate comparisons.</p>
        <p>We choose up to 12 examples by setup similarity, never by how well they performed afterward, and require at least 8. Their outcome windows do not share observations; this does not make them statistically independent. Recorded split-event windows are excluded; unrecorded corporate actions may still affect history.</p>
        <p>Windows count stored sessions, not calendar days. Missing observations may stretch calendar duration. Quartiles use linear interpolation. Price change excludes dividends. These historical comparisons are not a validated forecast or a probability of profit.</p>
        <p>{data.adjustment}{data.has_earlier ? ' Earlier stored observations are outside the 2,500-session calculation limit.' : ''}</p>
      </details>
    </>}
    <p className="pattern-footer">Past outcomes describe these examples. They do not predict what happens next.</p>
  </section>;
}
