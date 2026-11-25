import { compareLimit } from './compare-api.js';
import { compareHash } from './use-compare-selection.js';

export function CompareToggle({ symbol, selection }) {
  const selected = selection.symbols.includes(symbol);
  const blocked = !selected && selection.full;
  return <button type="button" className="compare-toggle" aria-pressed={selected} disabled={blocked}
    aria-label={`Compare ${symbol}`}
    title={blocked ? `Comparison holds up to ${compareLimit} stocks` : selected ? `Remove ${symbol} from comparison` : `Add ${symbol} to comparison`}
    onClick={() => selection.toggle(symbol)}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d={selected ? 'm5 12 4.5 4.5L19 7' : 'M12 5v14M5 12h14'} /></svg>
  </button>;
}

export default function CompareTray({ selection }) {
  const { symbols } = selection;
  if (symbols.length === 0) return null;
  const ready = symbols.length >= 2;
  return <section className="compare-tray" aria-label="Stocks selected for comparison">
    <strong>Compare <span className="muted">({symbols.length} of {compareLimit})</span></strong>
    <ul>{symbols.map(symbol => <li key={symbol}>{symbol}
      <button type="button" aria-label={`Remove ${symbol} from comparison`} onClick={() => selection.toggle(symbol)}>×</button>
    </li>)}</ul>
    <div className="compare-tray-actions">
      {ready ? <a className="button-link primary-link" href={compareHash(symbols)}>Compare {symbols.length} stocks</a>
        : <span className="muted">Pick at least one more stock</span>}
      <button type="button" onClick={selection.clear}>Clear</button>
    </div>
  </section>;
}
