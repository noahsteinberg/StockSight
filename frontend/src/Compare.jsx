import { useState } from 'react';
import CompareChart, { SeriesSwatch } from './CompareChart.jsx';
import StockSearchInput from './StockSearchInput.jsx';
import { compareLimit, compareRanges } from './compare-api.js';
import useCompare from './use-compare.js';
import { compareHash } from './use-compare-selection.js';

const symbolPattern = /^[A-Z][A-Z0-9.^=-]{0,15}$/;
const price = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', signDisplay: 'exceptZero', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const count = new Intl.NumberFormat('en-US');
const ratio = value => `${Number.isInteger(value) ? value : value.toFixed(2)}-for-1`;

function ChangeCell({ stock }) {
  if (stock.period_change_pct == null) {
    return <td className="muted">Unavailable<span className="compare-reason">{stock.metric_status === 'split_unadjusted' ? 'Split inside window' : 'Too little shared history'}</span></td>;
  }
  const value = stock.period_change_pct;
  return <td className={value > 0 ? 'positive' : value < 0 ? 'negative' : 'muted'}>{percent.format(value / 100)}</td>;
}

function Notes({ data }) {
  const newer = data.stocks.filter(stock => stock.as_of > data.end);
  const splits = data.stocks.flatMap(stock => stock.split_events.map(event => ({ ...event, symbol: stock.symbol })));
  return <ul className="compare-notes">
    <li>
      Indexed to 100 on {data.start}. Uses the {count.format(data.common_sessions)} trading days all selected stocks share
      {data.common_sessions < data.requested_sessions && <> (fewer than the {count.format(data.requested_sessions)} requested, because at least one stock has a shorter stored history)</>}.
      Days missing for any stock are skipped, not filled in.
    </li>
    {data.aligned_to_shared_cutoff && <li>
      Ends on {data.end}, the latest date every stock has stored. {newer.map(stock => `${stock.symbol} has data through ${stock.as_of}.`).join(' ')}
    </li>}
    {splits.map(event => <li key={`${event.symbol}-${event.date}`} className={event.price_adjusted ? undefined : 'compare-warning'}>
      {event.symbol} split {ratio(event.ratio)} on {event.date}. {event.price_adjusted
        ? 'Stored prices are already split-adjusted, so its line stays continuous.'
        : 'Stored prices look unadjusted at that date, so its change is withheld and its line jumps there.'}
    </li>)}
    <li>Closes exclude dividends, so this is price change, not total return. Past movement is not a forecast.</li>
  </ul>;
}

export default function Compare({ symbols: requested, range, selection, onOpen }) {
  const symbols = requested.slice(0, compareLimit);
  const overLimit = requested.length > compareLimit;
  const comparison = useCompare(symbols, range);
  const data = comparison.data;
  const [draft, setDraft] = useState('');
  const [inputError, setInputError] = useState('');

  function show(nextSymbols, nextRange = range) {
    selection.replace(nextSymbols);
    window.location.assign(compareHash(nextSymbols, nextRange));
  }
  function addSymbol(event) {
    event.preventDefault();
    addTicker(draft);
  }
  function addTicker(value) {
    const symbol = value.trim().toUpperCase();
    if (!symbolPattern.test(symbol)) { setInputError('Enter a ticker symbol, such as MSFT.'); return; }
    if (symbols.includes(symbol)) { setInputError(`${symbol} is already in this comparison.`); return; }
    if (symbols.length >= compareLimit) { setInputError(`A comparison holds up to ${compareLimit} stocks. Remove one first.`); return; }
    setDraft('');
    setInputError('');
    show([...symbols, symbol]);
  }

  return <section className="app-page compare" aria-labelledby="compare-title">
    <div className="page-heading"><h1 id="compare-title">Compare stocks</h1><span className="historical-badge">Stored daily history</span></div>
    <div className="page-panel compare-controls">
      <ul className="compare-chips" aria-label="Stocks in this comparison">
        {symbols.map((symbol, index) => <li key={symbol}>
          {data && <SeriesSwatch index={index} />}
          <a href={`#/analysis?symbol=${encodeURIComponent(symbol)}`} onClick={event => {
            if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            onOpen(symbol);
          }}>{symbol}</a>
          <button type="button" aria-label={`Remove ${symbol} from comparison`} onClick={() => show(symbols.filter(item => item !== symbol))}>×</button>
        </li>)}
      </ul>
      <form className="compare-add" onSubmit={addSymbol} noValidate>
        <label htmlFor="compare-add-input" className="sr-only">Add a ticker to the comparison</label>
        <StockSearchInput id="compare-add-input" value={draft} invalid={inputError} errorId="compare-add-error"
          placeholder="Add ticker or company" icon={false} exclude={symbols}
          onChange={value => { setDraft(value); setInputError(''); }} onSelect={addTicker} />
        <button type="submit">Add</button>
      </form>
      <fieldset className="compare-ranges">
        <legend className="sr-only">Comparison range</legend>
        {compareRanges.map(([value, label]) => <button key={value} type="button" aria-pressed={range === value} onClick={() => { if (range !== value) show(symbols, value); }}>{label}</button>)}
      </fieldset>
      {inputError && <p id="compare-add-error" role="alert" className="validation-error">{inputError}</p>}
    </div>
    {overLimit && <p className="compare-notice" role="status">A comparison holds up to {compareLimit} stocks, so only the first {compareLimit} from the link are shown.</p>}

    {symbols.length < 2 && <div className="page-panel unavailable-state">
      <h2>Add at least two stocks to compare</h2>
      <p>Pick stocks with the + button on Explore or your Watchlist, or type a ticker above.</p>
      <a className="button-link primary-link" href="#/explore">Explore stocks</a>
    </div>}

    {comparison.error && <div className="page-panel analysis-message error-state" role="alert">
      <p>{comparison.error}</p>
      {comparison.unknown.length > 0
        ? <div className="page-actions">{comparison.unknown.map(symbol => <button key={symbol} type="button" onClick={() => show(symbols.filter(item => item !== symbol))}>Remove {symbol}</button>)}</div>
        : <button type="button" onClick={comparison.retry}>Retry</button>}
    </div>}

    {comparison.loading && !data && <div className="page-panel analysis-message loading-state" role="status">
      <span className="loading-spinner" aria-hidden="true" /><p>Loading comparison.</p>
    </div>}

    {data && data.common_sessions === 0 && <div className="page-panel unavailable-state">
      <h2>These stocks can’t be compared yet</h2>
      <p>They share fewer than two stored trading days, so there is no common window to compare.</p>
    </div>}

    {data && data.common_sessions > 0 && <div className="chart-card compare-card" aria-busy={comparison.loading}>
      <div className="compare-card-heading">
        <h2>Price change since {data.start}</h2>
        <span className="muted">{data.start} to {data.end} · {count.format(data.common_sessions)} shared trading days</span>
      </div>
      <CompareChart key={`${symbols.join(',')}:${range}`} dates={data.dates} stocks={data.stocks} />
      <div className="table-scroll compare-table">
        <table>
          <caption className="sr-only">Comparison summary from {data.start} to {data.end}</caption>
          <thead><tr>
            <th scope="col">Stock</th>
            <th scope="col">Change</th>
            <th scope="col">Start → end close</th>
            <th scope="col">Latest stored close</th>
          </tr></thead>
          <tbody>{data.stocks.map((stock, index) => <tr key={stock.symbol}>
            <th scope="row"><span className="compare-stock"><SeriesSwatch index={index} /><strong>{stock.symbol}</strong></span>
              <span className={stock.name ? 'compare-name' : 'compare-name unknown-name'}>{stock.name || 'Name not yet available'}</span></th>
            <ChangeCell stock={stock} />
            <td>{stock.start_close == null ? '—' : `${price.format(stock.start_close)} → ${price.format(stock.end_close)}`}</td>
            <td>{price.format(stock.last_close)}<span className="explore-date">{stock.as_of}</span></td>
          </tr>)}</tbody>
        </table>
      </div>
      <Notes data={data} />
    </div>}
  </section>;
}
