import { useEffect, useMemo, useRef, useState } from 'react';

// Each line differs by dash pattern as well as colour, so the legend never depends
// on colour alone.
const seriesStyles = [
  { color: '#1858a0', dash: '' },
  { color: '#b45309', dash: '8 5' },
  { color: '#0f766e', dash: '2 4' },
  { color: '#7c3aed', dash: '12 4 3 4' },
];

const height = 300;
const top = 18;
const bottom = 262;
const left = 52;
const indexFormat = new Intl.NumberFormat('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function niceTicks(low, high) {
  const raw = (high - low) / 5;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(factor => factor * power).find(value => value >= raw);
  const ticks = [];
  for (let value = Math.ceil(low / step) * step; value <= high; value += step) ticks.push(Number(value.toFixed(6)));
  return ticks;
}

export function SeriesSwatch({ index }) {
  const style = seriesStyles[index];
  return <svg className="series-swatch" viewBox="0 0 28 10" aria-hidden="true">
    <line x1="1" y1="5" x2="27" y2="5" stroke={style.color} strokeDasharray={style.dash} strokeWidth="2.5" />
  </svg>;
}

export default function CompareChart({ dates, stocks }) {
  const container = useRef(null);
  // The plot itself, not the first <svg> in the card: the readout holds line samples.
  const plot = useRef(null);
  const [width, setWidth] = useState(800);
  const [selected, setSelected] = useState(null);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)));
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const right = width - (width < 480 ? 46 : 64);
  const { x, y, ticks, paths } = useMemo(() => {
    const values = stocks.flatMap(stock => stock.indexed);
    const min = Math.min(100, ...values);
    const max = Math.max(100, ...values);
    const spread = max - min || 2;
    const low = min - spread * .06;
    const high = max + spread * .06;
    const x = index => left + index / Math.max(1, dates.length - 1) * (right - left);
    const y = value => top + (high - value) / (high - low) * (bottom - top);
    const paths = stocks.map(stock => stock.indexed.map((value, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(''));
    return { x, y, ticks: niceTicks(low, high), paths };
  }, [dates, stocks, right]);

  // End labels are nudged apart so overlapping lines keep readable names.
  const labels = stocks.map((stock, index) => ({ index, symbol: stock.symbol, y: y(stock.indexed.at(-1)) }))
    .sort((a, b) => a.y - b.y)
    .reduce((placed, label) => [...placed, { ...label, y: Math.max(label.y, (placed.at(-1)?.y ?? -Infinity) + 14) }], []);
  const last = dates.length - 1;
  const active = selected === null ? null : Math.min(selected, last);
  // The readout always shows one date (the latest until you point at another), so
  // its size never changes and the chart never shifts under the cursor.
  const shown = active ?? last;
  const middle = Math.floor(last / 2);

  function pick(clientX) {
    const box = plot.current.getBoundingClientRect();
    const position = (clientX - box.left) / box.width * width;
    setSelected(Math.max(0, Math.min(last, Math.round((position - left) / (right - left) * last))));
  }

  return <div className="compare-chart" ref={container}>
    <p className="compare-readout" aria-live="polite">
      <strong>{dates[shown]}</strong>
      {stocks.map((stock, index) => <span key={stock.symbol}><SeriesSwatch index={index} /> {stock.symbol} {indexFormat.format(stock.indexed[shown])}</span>)}
      <span className="compare-readout-hint" style={{ visibility: active === null ? 'visible' : 'hidden' }}>Latest · hover, tap or use arrow keys for other dates</span>
    </p>
    <svg ref={plot} viewBox={`0 0 ${width} ${height}`} role="img" tabIndex="0"
      aria-label={`Price change indexed to 100 from ${dates[0]} to ${dates[last]} for ${stocks.map(stock => stock.symbol).join(', ')}. Use Left and Right Arrow to read values.`}
      onPointerMove={event => pick(event.clientX)} onPointerDown={event => pick(event.clientX)}
      onPointerLeave={event => { if (event.pointerType === 'mouse') setSelected(null); }}
      onKeyDown={event => {
        const moves = { ArrowLeft: -1, ArrowRight: 1, Home: -Infinity, End: Infinity };
        if (event.key === 'Escape') { setSelected(null); return; }
        if (!(event.key in moves)) return;
        event.preventDefault();
        const start = active ?? last;
        setSelected(Math.max(0, Math.min(last, start + moves[event.key])));
      }}>
      {ticks.map(tick => <g key={tick}>
        <line x1={left} x2={right} y1={y(tick)} y2={y(tick)} className={tick === 100 ? 'compare-baseline' : 'compare-grid'} />
        <text x={left - 8} y={y(tick) + 4} textAnchor="end">{tick}</text>
      </g>)}
      {!ticks.includes(100) && <g>
        <line x1={left} x2={right} y1={y(100)} y2={y(100)} className="compare-baseline" />
        {ticks.every(tick => Math.abs(y(tick) - y(100)) > 12) && <text x={left - 8} y={y(100) + 4} textAnchor="end">100</text>}
      </g>}
      {(width < 480 ? [0, last] : [0, middle, last]).filter((value, index, all) => all.indexOf(value) === index).map(index => (
        <text key={index} x={x(index)} y={bottom + 22} textAnchor={index === 0 ? 'start' : index === last ? 'end' : 'middle'}>{dates[index]}</text>
      ))}
      {paths.map((path, index) => <path key={stocks[index].symbol} d={path} fill="none" stroke={seriesStyles[index].color}
        strokeDasharray={seriesStyles[index].dash} strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />)}
      {labels.map(label => <text key={label.symbol} x={right + 6} y={label.y + 4} className="compare-end-label" fill={seriesStyles[label.index].color}>{label.symbol}</text>)}
      {active !== null && <g>
        <line x1={x(active)} x2={x(active)} y1={top} y2={bottom} className="compare-cursor" />
        {stocks.map((stock, index) => <circle key={stock.symbol} cx={x(active)} cy={y(stock.indexed[active])} r="4" fill={seriesStyles[index].color} />)}
      </g>}
    </svg>
  </div>;
}
