import { useEffect, useRef, useState } from 'react';
import { WatchlistStar } from './AnalysisWatchlist.jsx';
import { useAccount } from './auth-context.js';
import CompareTray, { CompareToggle } from './CompareTray.jsx';
import { explorePageSize, exploreSortOptions, sectorNames } from './explore-api.js';
import useExplore, { useSectors } from './use-explore.js';
import { exploreHash } from './use-page-route.js';

const price = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', signDisplay: 'exceptZero', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const count = new Intl.NumberFormat('en-US');

function summary(data, query, page, sector) {
  const parts = [`${count.format(data.total_supported)} supported ${data.total_supported === 1 ? 'stock' : 'stocks'}`];
  if (data.preference_sectors) {
    parts.push(`${count.format(data.total_matching)} ${data.total_matching === 1 ? 'stock matches' : 'stocks match'}${query ? ` “${query}” and` : ''} your sectors (${data.preference_sectors.join(', ')})`);
  } else if (query || sector) {
    parts.push(`${count.format(data.total_matching)} ${data.total_matching === 1 ? 'match' : 'matches'}${query ? ` for “${query}”` : ''}${sector ? ` in ${sector}` : ''}`);
  }
  if (data.items.length > 0) {
    const first = (page - 1) * explorePageSize + 1;
    parts.push(`showing ${count.format(first)}–${count.format(first + data.items.length - 1)}`);
  }
  if (data.latest_session) parts.push(`latest stored session ${data.latest_session}`);
  return parts.join(' · ');
}

function StockRow({ stock, latestSession, watchlist, selection, onOpen }) {
  const change = stock.daily_change_pct;
  const direction = change > 0 ? 'positive' : change < 0 ? 'negative' : 'muted';
  const olderSession = stock.as_of && latestSession && stock.as_of < latestSession;
  return <tr>
    <th scope="row">
      <a href={`#/analysis?symbol=${encodeURIComponent(stock.symbol)}`}
        onClick={event => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
          event.preventDefault();
          onOpen(stock.symbol);
        }}>
        <strong>{stock.symbol}</strong>
        <span className={stock.name ? undefined : 'unknown-name'}>{stock.name || 'Name not yet available'}</span>
      </a>
      <span className="explore-sector">{stock.match_reason || stock.sector || 'Sector unknown'}</span>
    </th>
    <td>
      {stock.last_close == null ? <span className="muted">Unavailable</span> : price.format(stock.last_close)}
      <span className="explore-date">{stock.as_of || 'No stored date'}{olderSession && <span className="older-session"> · earlier session</span>}</span>
    </td>
    <td className={direction}>
      {change == null ? <><span aria-hidden="true">—</span><span className="sr-only">Unavailable</span></> : percent.format(change / 100)}
    </td>
    <td><div className="row-actions"><WatchlistStar symbol={stock.symbol} watchlist={watchlist} /><CompareToggle symbol={stock.symbol} selection={selection} /></div></td>
  </tr>;
}

export default function Explore({ query, page, sector, sort, mine, preferences, watchlist, selection, onOpen }) {
  const account = useAccount();
  // "Use my preferences" reads the private discovery list for the signed-in account.
  const personal = mine && account.isAuthenticated ? { owner: preferences.owner, authorizedFetch: account.authorizedFetch } : null;
  const searchInput = useRef(null);
  const listTop = useRef(null);
  // The URL owns the applied search; the draft keeps exactly what is being typed.
  const [draft, setDraft] = useState({ source: query, value: query });
  const input = draft.source === query ? draft.value : query;
  const explore = useExplore(query, page, mine ? null : sector, sort, personal);
  const sectors = useSectors();
  const sectorCounts = new Map(sectors.data?.sectors.map(item => [item.name, item.count]));
  const data = explore.data;
  const totalPages = data ? Math.max(1, Math.ceil(data.total_matching / explorePageSize)) : 1;

  useEffect(() => {
    const next = draft.value.trim();
    if (draft.source !== query || next === query) return undefined;
    // Only a search the user paused on becomes a history step, so Back undoes it
    // without recording one entry per keystroke.
    const timer = setTimeout(() => {
      setDraft(current => ({ ...current, source: next }));
      window.location.hash = exploreHash({ query: next, sector, sort, mine });
    }, 300);
    return () => clearTimeout(timer);
  }, [draft, query, sector, sort, mine]);

  function applySearch(value) {
    const next = value.trim();
    setDraft({ source: next, value });
    if (next !== query || page !== 1) window.location.hash = exploreHash({ query: next, sector, sort, mine });
  }
  function chooseSector(next) {
    window.location.hash = exploreHash({ query, sector: next || null, sort });
  }
  function clearFilters() {
    setDraft({ source: '', value: '' });
    window.location.hash = exploreHash({});
    searchInput.current?.focus();
  }
  function clearSearch() {
    applySearch('');
    searchInput.current?.focus();
  }
  function goToPage(next) {
    window.location.hash = exploreHash({ query, page: next, sector, sort, mine });
    listTop.current?.scrollIntoView({ block: 'start' });
  }

  return <section className="app-page explore" aria-labelledby="explore-title">
    <div className="page-heading"><h1 id="explore-title">Explore stocks</h1><span className="historical-badge">Stored daily history</span></div>
    <form className="explore-search" role="search" noValidate onSubmit={event => { event.preventDefault(); applySearch(input); }}>
      <label className="sr-only" htmlFor="explore-query">Search ticker or company</label>
      <input ref={searchInput} id="explore-query" type="search" value={input} maxLength={40} autoComplete="off" spellCheck="false"
        placeholder="Search ticker or company" onChange={event => setDraft({ source: query, value: event.target.value })} />
      {input && <button type="button" onClick={clearSearch}>Clear</button>}
      <label className="explore-sector-filter">
        <span>Sector</span>
        <select value={mine ? '' : sector || ''} disabled={mine} onChange={event => chooseSector(event.target.value)}>
          <option value="">All sectors</option>
          {sectorNames.map(name => <option key={name} value={name}>{name}{sectorCounts.has(name) ? ` (${sectorCounts.get(name)})` : ''}</option>)}
        </select>
      </label>
      <label className="explore-sector-filter">
        <span>Sort by</span>
        <select value={sort} onChange={event => {
          window.location.hash = exploreHash({ query, sector, mine, sort: event.target.value });
        }}>
          {exploreSortOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>
      {account.isAuthenticated && <button type="button" className="explore-mine" aria-pressed={mine}
        onClick={() => { window.location.hash = exploreHash({ query, sort, mine: !mine }); }}>Use my preferences</button>}
      {(query || sector || mine || sort !== 'ticker') && <button type="button" className="explore-reset" onClick={clearFilters}>Reset filters</button>}
    </form>
    {mine && !account.isAuthenticated && <div className="page-panel unavailable-state">
      <p>Sign in to list stocks that match your saved preferences. Everything else on Explore works without an account.</p>
      <div className="page-actions">
        <button type="button" className="primary-button" disabled={account.pending || !account.configured} onClick={() => account.login()}>Sign in</button>
        <button type="button" onClick={clearFilters}>Show all stocks</button>
      </div>
    </div>}
    {mine && account.isAuthenticated && data?.preference_sectors?.length === 0 && <div className="page-panel unavailable-state">
      <p>You haven’t chosen any sectors yet, so nothing can match. Explore never widens an empty filter to everything.</p>
      <div className="page-actions"><a className="button-link primary-link" href="#/preferences">Choose sectors</a><button type="button" onClick={clearFilters}>Show all stocks</button></div>
    </div>}
    {!(mine && (!account.isAuthenticated || data?.preference_sectors?.length === 0)) && <>
    <div ref={listTop} className="page-panel explore-panel">
      <p className="explore-summary" role="status">
        {data ? summary(data, query, page, sector) : explore.error ? 'Stock list unavailable' : 'Loading stocks…'}
        {data && explore.loading && <span className="muted"> · Updating…</span>}
        {mine && data?.preference_sectors && <> · <a href="#/preferences">Edit preferences</a></>}
      </p>
      {explore.error && <div className="analysis-message error-state" role="alert">
        <p>{explore.error}</p>
        <button type="button" onClick={explore.retry}>Retry</button>
      </div>}
      {!data && !explore.error && <div className="analysis-message loading-state" aria-hidden="true">
        <span className="loading-spinner" /><div className="chart-skeleton" />
      </div>}
      {data && data.total_matching === 0 && <div className="analysis-message">
        <p>{data.preference_sectors
          ? <>No supported stocks in your sectors match{query && <> “{query}”</>}.</>
          : query || sector
          ? <>No supported stocks match{query && <> “{query}”</>}{sector && <> in {sector}</>}. Try another ticker or company name{sector ? ', or choose All sectors' : ''}.</>
          : 'No supported stocks are stored yet.'}</p>
        {(query || sector || mine) && <button type="button" onClick={clearFilters}>Reset filters</button>}
      </div>}
      {data && data.total_matching > 0 && data.items.length === 0 && <div className="analysis-message">
        <p>Page {page} is past the end of these results.</p>
        <button type="button" onClick={() => goToPage(totalPages)}>Go to page {totalPages}</button>
      </div>}
      {data && data.items.length > 0 && <div className="table-scroll explore-table" aria-busy={explore.loading}>
        <table>
          <caption className="sr-only">Supported stocks, page {page} of {totalPages}</caption>
          <thead><tr>
            <th scope="col">Stock</th>
            <th scope="col">Last stored close</th>
            <th scope="col" title="Change between the latest two stored closes">Daily change</th>
            <th scope="col">Save · Compare</th>
          </tr></thead>
          <tbody>{data.items.map(stock => <StockRow key={stock.symbol} stock={stock} latestSession={data.latest_session} watchlist={watchlist} selection={selection} onOpen={onOpen} />)}</tbody>
        </table>
      </div>}
      {data && totalPages > 1 && data.items.length > 0 && <nav className="explore-pages" aria-label="Stock list pages">
        <button type="button" disabled={page <= 1 || explore.loading} onClick={() => goToPage(page - 1)}><span aria-hidden="true">‹ </span>Previous</button>
        <span>Page {page} of {totalPages}</span>
        <button type="button" disabled={page >= totalPages || explore.loading} onClick={() => goToPage(page + 1)}>Next<span aria-hidden="true"> ›</span></button>
      </nav>}
    </div>
    </>}
    <CompareTray selection={selection} />
    <p className="explore-note">
      {sectors.data
        ? <>Company names and GICS sectors come from a reviewed copy of <a href={sectors.data.source.url}>{sectors.data.source.name}</a> (revision of {sectors.data.source.revision_date}, {sectors.data.source.license}).{sectors.data.unknown > 0 && ` ${count.format(sectors.data.unknown)} supported ${sectors.data.unknown === 1 ? 'stock has' : 'stocks have'} no reviewed sector yet.`} </>
        : 'Company names and sectors appear only when reviewed. '}
      Daily change compares the latest two stored closes; it is not a forecast. <a href="#/methodology">Methodology</a>
    </p>
  </section>;
}
