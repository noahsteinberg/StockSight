import { useEffect, useId, useRef, useState } from 'react';

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

function linePath(values, x, y) {
  let connected = false;
  return values.map((value, index) => {
    if (value == null) { connected = false; return ''; }
    const point = `${connected ? 'L' : 'M'}${x(index)},${y(value)}`;
    connected = true;
    return point;
  }).join(' ');
}

export default function PricePlot({ bars, points, showSma, showRsi, selectedIndex }) {
  const container = useRef(null);
  const gradient = useId();
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(200, entry.contentRect.width)));
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const values = bars.map(bar => bar.close);
  const sma = showSma && points ? points.map(point => point.sma_20) : [];
  const allValues = [...values, ...sma.filter(value => value != null)];
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const spread = max - min || Math.max(1, max * .02);
  const low = min - spread * .08;
  const high = max + spread * .08;
  const right = width - 12;
  const x = index => 66 + index / Math.max(1, bars.length - 1) * (right - 66);
  const y = value => 24 + (high - value) / (high - low) * 220;
  const path = linePath(values, x, y);
  const volumeMax = Math.max(1, ...bars.map(bar => bar.volume));
  const selected = selectedIndex ?? bars.length - 1;
  return <div ref={container} className="plot-container">
    <svg className="price-plot" viewBox={`0 0 ${width} 340`} role="img" aria-label={`Closing price and volume from ${bars[0].date} to ${bars.at(-1).date}${showSma && points ? ', with 20-session moving average' : ''}`}>
      <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#2563ab" stopOpacity=".13" /><stop offset="100%" stopColor="#2563ab" stopOpacity="0" /></linearGradient></defs>
      {[0, 1, 2, 3].map(index => <g key={index}><line x1="66" x2={right} y1={24 + index * 220 / 3} y2={24 + index * 220 / 3} className="chart-grid" /><text x="0" y={28 + index * 220 / 3}>{money.format(high - (high - low) * index / 3)}</text></g>)}
      <path d={`${path} L${x(bars.length - 1)},248 L66,248 Z`} fill={`url(#${gradient})`} />
      <path d={path} fill="none" className="price-line" />
      {showSma && points && <path d={linePath(sma, x, y)} fill="none" className="sma-line" />}
      <line x1={x(selected)} x2={x(selected)} y1="18" y2="308" className="inspection-line" />
      <circle cx={x(selected)} cy={y(values[selected])} r="4" className="inspection-dot" />
      {bars.map((bar, index) => <rect key={bar.date} x={Math.min(right - 1, x(index))} y={304 - bar.volume / volumeMax * 40} width={Math.max(.5, (right - 66) * .75 / bars.length)} height={bar.volume / volumeMax * 40} className="volume-bar" />)}
      <text x="0" y="282">Vol.</text><text x="66" y="332">{bars[0].date}</text><text x={right} y="332" textAnchor="end">{bars.at(-1).date}</text>
    </svg>
    {showRsi && points && <div className="rsi-panel"><div className="chart-caption"><span>RSI <span className="muted">14 · Wilder</span></span><span>{points[selected]?.rsi_14 == null ? 'Insufficient history' : points[selected].rsi_14.toFixed(2)}</span></div>
      <svg className="rsi-plot" viewBox={`0 0 ${width} 130`} role="img" aria-label="14-session relative strength index, scale 0 to 100">
        <rect x="66" y="44" width={right - 66} height="40" className="rsi-band" />
        {[0, 30, 70, 100].map(value => <g key={value}><line x1="66" x2={right} y1={114 - value} y2={114 - value} className="chart-grid" /><text x="18" y={118 - value}>{value}</text></g>)}
        <path d={linePath(points.map(point => point.rsi_14), x, value => 114 - value)} fill="none" className="rsi-line" />
        <line x1={x(selected)} x2={x(selected)} y1="14" y2="114" className="inspection-line" />
      </svg></div>}
  </div>;
}
