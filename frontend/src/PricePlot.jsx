import { useEffect, useId, useMemo, useRef, useState } from 'react';

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', signDisplay: 'exceptZero', maximumFractionDigits: 2 });
const volumeRatio = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const plotLeft = 66;

function linePath(values, x, y) {
  let connected = false;
  return values.map((value, index) => {
    if (value == null) { connected = false; return ''; }
    const point = `${connected ? 'L' : 'M'}${x(index)},${y(value)}`;
    connected = true;
    return point;
  }).join(' ');
}

export default function PricePlot({ bars, points, showSma, showRsi, replaying }) {
  const container = useRef(null);
  const interaction = useRef(null);
  const id = useId();
  const latest = bars.at(-1);
  const [preview, setPreview] = useState(null);
  const [pin, setPin] = useState(null);
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(200, entry.contentRect.width)));
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const right = width - 12;
  const { x, y, low, high, path, smaPath, rsiPath, volumes } = useMemo(() => {
    const values = bars.map(bar => bar.close);
    const sma = showSma && points ? points.map(point => point.sma_20) : [];
    const allValues = [...values, ...sma.filter(value => value != null)];
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const spread = max - min || Math.max(1, max * .02);
    const low = min - spread * .08;
    const high = max + spread * .08;
    const x = index => plotLeft + index / Math.max(1, bars.length - 1) * (right - plotLeft);
    const y = value => 24 + (high - value) / (high - low) * 220;
    const volumeMax = Math.max(1, ...bars.map(bar => bar.volume));
    const volumes = bars.map((bar, index) => <rect key={bar.date} x={Math.min(right - 1, x(index))} y={304 - bar.volume / volumeMax * 40} width={Math.max(.5, (right - plotLeft) * .75 / bars.length)} height={bar.volume / volumeMax * 40} className="volume-bar" />);
    return {
      x, y, low, high, volumes,
      path: linePath(values, x, y),
      smaPath: linePath(sma, x, y),
      rsiPath: showRsi && points ? linePath(points.map(point => point.rsi_14), x, value => 114 - value) : '',
    };
  }, [bars, points, right, showRsi, showSma]);

  const pinned = pin?.through === latest.date ? pin.index : null;
  const hovered = preview?.through === latest.date ? preview.index : null;
  const lastIndex = bars.length - 1;
  const selected = pinned ?? hovered ?? lastIndex;
  const inspecting = pinned !== null || hovered !== null;
  const observation = bars[selected];
  const previous = bars[selected - 1];
  const change = previous?.close ? observation.close / previous.close - 1 : null;
  const priorVolumes = bars.slice(Math.max(0, selected - 20), selected);
  const volumeTotal = priorVolumes.reduce((total, bar) => total + bar.volume, 0);
  const relativeVolume = volumeTotal ? observation.volume * priorVolumes.length / volumeTotal : null;
  const point = points?.[selected];

  function indexAtPointer(event) {
    const bounds = event.currentTarget.ownerSVGElement.getBoundingClientRect();
    const xPosition = (event.clientX - bounds.left) / bounds.width * width;
    const fraction = Math.min(1, Math.max(0, (xPosition - plotLeft) / (right - plotLeft)));
    return Math.round(fraction * lastIndex);
  }
  function hover(event) {
    if (event.pointerType === 'touch' || pinned !== null) return;
    const index = indexAtPointer(event);
    if (hovered !== index) setPreview({ through: latest.date, index });
  }
  function pinSession(index) {
    setPreview(null);
    setPin({ through: latest.date, index });
  }
  function clearInspection() {
    setPreview(null);
    setPin(null);
  }
  function inspectKeys(event) {
    const index = pinned ?? lastIndex;
    const target = {
      ArrowLeft: Math.max(0, index - 1),
      ArrowRight: Math.min(lastIndex, index + 1),
      Home: 0,
      End: lastIndex,
    };
    if (event.key === 'Escape') {
      event.preventDefault();
      clearInspection();
    } else if (Object.hasOwn(target, event.key)) {
      event.preventDefault();
      pinSession(target[event.key]);
    }
  }
  return <div ref={container} className="plot-container">
    <div className="inspection-summary">
      {inspecting ? <div className="inspection-readout">
        <span className="inspection-state">{pinned !== null ? 'Pinned' : 'Preview'}</span>
        <time dateTime={observation.date}>{observation.date}</time>
        <strong>{money.format(observation.close)}</strong>
        <span className="inspection-volume">Vol. {observation.volume.toLocaleString('en-US')}</span>
      </div> : <p className="inspection-hint">Hover or tap to inspect</p>}
      {pinned !== null && <button type="button" className="inspection-reset" onClick={() => {
        clearInspection();
        interaction.current?.focus({ preventScroll: true });
      }}>
        {replaying ? 'Replay date' : 'Latest'}
      </button>}
    </div>
    <p id={`${id}-keys`} className="sr-only">Use Left and Right Arrow to inspect sessions, Home and End to jump to the first or last, and Escape to clear your selection.</p>
    <p className="sr-only" role="status">{pinned === null ? '' : `Pinned ${bars[pinned].date}, ${money.format(bars[pinned].close)}, volume ${bars[pinned].volume.toLocaleString('en-US')}.`}</p>
    <div ref={interaction} className="plot-interaction" role="group" aria-label="Inspect historical observations" aria-describedby={`${id}-keys`} tabIndex={0} onKeyDown={inspectKeys}>
    <svg className="price-plot" viewBox={`0 0 ${width} 340`} role="img" aria-label={`Closing price and volume from ${bars[0].date} to ${bars.at(-1).date}${showSma && points ? ', with 20-session moving average' : ''}`}>
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2563ab" stopOpacity=".13" /><stop offset="100%" stopColor="#2563ab" stopOpacity="0" /></linearGradient></defs>
      {[0, 1, 2, 3].map(index => <g key={index}><line x1="66" x2={right} y1={24 + index * 220 / 3} y2={24 + index * 220 / 3} className="chart-grid" /><text x="0" y={28 + index * 220 / 3}>{money.format(high - (high - low) * index / 3)}</text></g>)}
      <path d={`${path} L${x(lastIndex)},248 L66,248 Z`} fill={`url(#${id})`} />
      <path d={path} fill="none" className="price-line" />
      {showSma && points && <path d={smaPath} fill="none" className="sma-line" />}
      {volumes}
      <line x1={x(selected)} x2={x(selected)} y1="18" y2="308" className="inspection-line" />
      <circle cx={x(selected)} cy={y(observation.close)} r="4" className="inspection-dot" />
      <text x="0" y="282">Vol.</text><text x="66" y="332">{bars[0].date}</text>{lastIndex > 0 && <text x={right} y="332" textAnchor="end">{latest.date}</text>}
      <rect x={plotLeft} y="18" width={right - plotLeft} height="290" className="plot-inspection-target" aria-hidden="true"
        onPointerMove={hover} onPointerLeave={() => setPreview(null)} onClick={event => pinSession(indexAtPointer(event))} />
    </svg>
    {showRsi && points && <div className="rsi-panel"><div className="chart-caption"><span>RSI <span className="muted">14 · Wilder</span></span><span>{points[selected]?.rsi_14 == null ? 'Insufficient history' : points[selected].rsi_14.toFixed(2)}</span></div>
      <svg className="rsi-plot" viewBox={`0 0 ${width} 130`} role="img" aria-label="14-session relative strength index, scale 0 to 100">
        <rect x="66" y="44" width={right - 66} height="40" className="rsi-band" />
        {[0, 30, 70, 100].map(value => <g key={value}><line x1="66" x2={right} y1={114 - value} y2={114 - value} className="chart-grid" /><text x="18" y={118 - value}>{value}</text></g>)}
        <path d={rsiPath} fill="none" className="rsi-line" />
        <line x1={x(selected)} x2={x(selected)} y1="14" y2="114" className="inspection-line" />
      </svg></div>}
    </div>
    <div className="inspection-context">
      <dl className="observation-stats">
        <div><dt>Vs. prior close</dt><dd className={change == null ? undefined : change < 0 ? 'negative' : 'positive'}>{change == null ? '—' : percent.format(change)}</dd></div>
        <div><dt>Open</dt><dd>{money.format(observation.open)}</dd></div>
        <div><dt>Day range</dt><dd>{money.format(observation.low)}–{money.format(observation.high)}</dd></div>
        <div><dt>Volume</dt><dd>{observation.volume.toLocaleString('en-US')}</dd>{relativeVolume != null && <dd className="relative-volume">{volumeRatio.format(relativeVolume)}× {priorVolumes.length}-session avg</dd>}</div>
      </dl>
      {points && <div className="indicator-values">
        {showSma && <span>SMA 20 · {point?.sma_20 == null ? 'Insufficient history (20 observations required)' : money.format(point.sma_20)}</span>}
        {showRsi && <span>RSI 14 · {point?.rsi_14 == null ? 'Insufficient history (15 observations required)' : `${point.rsi_14.toFixed(2)} / 100`}</span>}
      </div>}
    </div>
  </div>;
}
