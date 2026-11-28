import CompareTray from './CompareTray.jsx';
import Watchlist from './Watchlist.jsx';

export function Dashboard({ watchlist, selection, onOpen, invite, onDismissInvite }) {
  return <section className="app-page" aria-labelledby="dashboard-title">
    <div className="page-heading"><h1 id="dashboard-title">Dashboard</h1><a className="button-link primary-link" href="#/explore">Explore stocks <span aria-hidden="true">↗</span></a></div>
    {invite && <aside className="page-panel preference-invite" aria-labelledby="preference-invite-title">
      <div><h2 id="preference-invite-title">Optional: set research preferences</h2><p>Choose sectors you’re curious about to list matching stocks in Explore, and pick a default chart window. You can skip this; nothing else changes.</p></div>
      <div className="page-actions"><a className="button-link primary-link" href="#/preferences">Set preferences</a><button type="button" onClick={onDismissInvite}>Not now</button></div>
    </aside>}
    <Watchlist watchlist={watchlist} selection={selection} onOpen={onOpen} />
    <CompareTray selection={selection} />
  </section>;
}

export function ModelPerformance() {
  return <section className="app-page" aria-labelledby="performance-title">
    <div className="page-heading"><h1 id="performance-title">Model performance</h1><span className="historical-badge">Unavailable</span></div>
    <div className="page-panel unavailable-state"><span className="state-mark" aria-hidden="true">▥</span><h2>No evaluated model is available</h2><p>Model and baseline results will appear here after evaluation on held-out data. No accuracy results are available yet.</p><div className="page-actions"><a className="button-link primary-link" href="#/analysis">Explore stock analysis</a><a href="#/methodology">Data & methodology ↗</a></div></div>
    <details className="page-panel help-disclosure"><summary>What a useful evaluation includes</summary><div><dl className="definition-list"><div><dt>Evaluation period</dt><dd>Dates and sample count from data excluded from training.</dd></div><div><dt>Baseline comparison</dt><dd>Model and baseline measured on the same eligible predictions.</dd></div><div><dt>Reproducibility</dt><dd>Model version, data snapshot, prediction target and information cutoff.</dd></div></dl></div></details>
  </section>;
}

export function Methodology() {
  return <section className="app-page methodology-page" aria-labelledby="methodology-title">
    <div className="page-heading"><h1 id="methodology-title">Data & methodology</h1></div>
    <div className="methodology-grid">
      <section className="page-panel"><h2>Historical data</h2><p>Charts show stored daily observations, not live quotes. Each chart identifies its source, latest observation, displayed dates and price-adjustment convention. The separate TradingView market-price panel follows the selected ticker and may be delayed. Its prices do not update the historical chart, indicators, watchlist changes or CSV export.</p><p>Stored history starts with the team’s Yahoo Finance snapshot and can include validated updates for completed trading sessions. Refresh data reloads the latest stored observations. A separate Apple fixture is used for explicit offline demos. The chart’s source label identifies which is shown.</p><dl className="definition-list"><div><dt>Ranges</dt><dd>1M: 21 observations · 3M: 63 · 1Y: 252 · Max: up to 2,000.</dd></div><div><dt>Coverage</dt><dd>Ranges count stored sessions, not calendar days. Missing sessions are not filled in.</dd></div><div><dt>Limitations</dt><dd>Updates check recent overlapping prices; they do not establish a consistently adjusted total-return history or independently verify the original upstream cleaning. Charts display USD for the supported US-stock scope.</dd></div></dl></section>
      <section className="page-panel"><h2>Company names and sectors</h2><p>Company names, GICS sectors and sub-industries come from a reviewed copy of Wikipedia’s <a href="https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&oldid=1384572480">List of S&P 500 companies</a>, pinned to its November 8, 2026 revision (CC BY-SA 4.0) and matched to every supported ticker on November 24.</p><dl className="definition-list"><div><dt>Coverage</dt><dd>All 494 supported stocks at review. A stock added later shows “Sector unknown” until the file is reviewed again; nothing is guessed from a ticker.</dd></div><div><dt>Limitations</dt><dd>A static snapshot, not a live feed: index membership and classifications can change. Sectors describe companies; they are not recommendations.</dd></div></dl></section>
      <section className="page-panel"><h2>Technical indicators</h2><dl className="definition-list"><div><dt>SMA 20</dt><dd>The mean of the current close and 19 preceding stored closes. At least 20 observations are required.</dd></div><div><dt>RSI 14</dt><dd>Wilder-smoothed relative strength on a 0–100 scale, initialized from 14 close-to-close changes. At least 15 observations are required; flat prices return 50.</dd></div><div><dt>Calculation history</dt><dd>Indicators use up to the latest 10,000 stored observations before trimming the visible range. Short histories retain unavailable values.</dd></div></dl><p>Indicators describe past prices. They are not forecasts or recommendations.</p></section>
      <section className="page-panel"><h2>Private watchlists</h2><p>Sign in to save up to 100 supported stocks. Your watchlist persists across visits and belongs to your account.</p><p>Auth0 manages signup and login. Signing out revokes the current StockSight session.</p><a href="#/dashboard">Open your watchlist ↗</a></section>
      <section className="page-panel"><h2>About StockSight</h2><p>A UConn CSE 4095 project by Noah Steinberg, Gavin Javier Pino, Parth Sachdev, and Vladislav Lagutin.</p><p>Predictions and model evaluation remain in development. StockSight is for education and research, not financial advice.</p><div className="page-actions"><a href="#/performance">Model performance</a><a href="https://github.com/noahsteinberg/StockSight">GitHub ↗</a><a href="https://github.com/noahsteinberg/StockSight/blob/main/SPECIFICATION.md">Project specification ↗</a></div></section>
    </div>
  </section>;
}
