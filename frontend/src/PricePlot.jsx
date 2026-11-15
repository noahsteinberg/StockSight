import { useEffect, useRef, useState } from 'react';

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export default function PricePlot({ bars }) {
  const container = useRef(null);
  const [width, setWidth] = useState(980);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)));
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const min = Math.min(...bars.map(bar => bar.close));
  const max = Math.max(...bars.map(bar => bar.close));
  const right = width - 20;
  const x = index => 60 + index / Math.max(1, bars.length - 1) * (right - 60);
  const points = bars.map((bar, index) => `${x(index)},${30 + (max - bar.close) / (max - min || 1) * 200}`).join(' ');
  const volumeMax = Math.max(1, ...bars.map(bar => bar.volume));
  return <div ref={container} className="plot-container">
    <svg className="price-plot" viewBox={`0 0 ${width} 320`} role="img" aria-label={`Closing price and volume from ${bars[0].date} to ${bars.at(-1).date}`}>
      {[0, 1, 2].map(index => <g key={index}>
        <line x1="60" x2={right} y1={30 + index * 100} y2={30 + index * 100} className="chart-grid" />
        <text x="0" y={34 + index * 100}>{money.format(max - (max - min) * index / 2)}</text>
      </g>)}
      <polyline points={points} fill="none" className="price-line" />
      {bars.map((bar, index) => <rect key={bar.date} x={x(index)} y={290 - bar.volume / volumeMax * 40} width={Math.max(1, (right - 60) * .8 / bars.length)} height={bar.volume / volumeMax * 40} className="volume-bar" />)}
      <text x="60" y="315">{bars[0].date}</text>
      <text x={right} y="315" textAnchor="end">{bars.at(-1).date}</text>
    </svg>
  </div>;
}
