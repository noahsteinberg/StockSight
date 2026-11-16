import Watchlist from './Watchlist.jsx';

export function Dashboard({ watchlist, onOpen, symbol }) {
  return <section className="app-page" aria-labelledby="dashboard-title">
    <div className="page-heading"><h1 id="dashboard-title">My dashboard</h1><a className="button-link primary-link" href="#/analysis">Find a stock <span aria-hidden="true">↗</span></a></div>
    <Watchlist watchlist={watchlist} onOpen={onOpen} selectedSymbol={symbol} expanded />
    <div className="dashboard-links"><a href="#/predictions"><span>Predictions</span><span className="muted">Currently unavailable</span><span aria-hidden="true">↗</span></a><a href="#/performance"><span>Model performance</span><span className="muted">Currently unavailable</span><span aria-hidden="true">↗</span></a></div>
  </section>;
}

export function Predictions({ symbol }) {
  return <section className="app-page" aria-labelledby="predictions-title">
    <div className="page-heading"><h1 id="predictions-title">Predictions</h1><span className="historical-badge">Unavailable</span></div>
    <div className="page-panel prediction-request">
      <div><span className="note-label">SELECTED STOCK</span><h2>{symbol}</h2><a href={`#/analysis?symbol=${encodeURIComponent(symbol)}`}>View {symbol} analysis ↗</a></div>
      <div className="prediction-action"><button type="button" disabled aria-describedby="prediction-unavailable">Generate prediction</button><p id="prediction-unavailable">Prediction generation is not available yet.</p></div>
    </div>
    <div className="page-panel history-panel"><div className="panel-heading"><h2>Prediction history</h2></div><div className="unavailable-state"><span className="state-mark" aria-hidden="true">↗</span><h3>Prediction history is unavailable</h3><p>No prediction service is connected. Saved forecasts and their outcomes cannot be shown yet.</p><a className="button-link" href="#/analysis">Continue stock analysis</a></div></div>
    <details className="page-panel help-disclosure"><summary>How prediction outcomes work</summary><div><dl className="definition-list"><div><dt>Pending</dt><dd>The target trading session has not resolved.</dd></div><div><dt>Resolved</dt><dd>The forecast can be compared with its observed outcome.</dd></div></dl><p>Historical replay must be labeled separately from a newly generated forecast.</p></div></details>
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
      <section className="page-panel"><h2>Historical data</h2><p>Charts show stored daily observations, not live quotes. Each chart identifies its source, latest observation, displayed dates and price-adjustment convention.</p><p>The team dataset is a Yahoo Finance historical snapshot. A separate Apple fixture is used for explicit offline demos. The chart’s source label identifies which is shown.</p><dl className="definition-list"><div><dt>Ranges</dt><dd>1M: 21 observations · 3M: 63 · 1Y: 252 · Max: up to 2,000.</dd></div><div><dt>Coverage</dt><dd>Ranges count stored sessions, not calendar days. Missing sessions are not filled in.</dd></div><div><dt>Limitations</dt><dd>The team snapshot’s price adjustments, upstream cleaning and calendar coverage remain unverified. USD is assumed for its US-stock scope.</dd></div></dl></section>
      <section className="page-panel"><h2>Technical indicators</h2><dl className="definition-list"><div><dt>SMA 20</dt><dd>The mean of the current close and 19 preceding stored closes. At least 20 observations are required.</dd></div><div><dt>RSI 14</dt><dd>Wilder-smoothed relative strength on a 0–100 scale, initialized from 14 close-to-close changes. At least 15 observations are required; flat prices return 50.</dd></div><div><dt>Calculation history</dt><dd>Indicators use up to the latest 10,000 stored observations before trimming the visible range. Short histories retain unavailable values.</dd></div></dl><p>Indicators describe past prices. They are not forecasts or recommendations.</p></section>
      <section className="page-panel"><h2>Private watchlists</h2><p>Sign in to save up to 100 supported stocks. Your watchlist persists across visits and belongs to your account.</p><p>Auth0 manages signup and login. Signing out revokes the current StockSight session.</p><a href="#/dashboard">Open my dashboard ↗</a></section>
      <section className="page-panel"><h2>About StockSight</h2><p>A UConn CSE 4095 project by Noah Steinberg, Gavin Javier Pino, Parth Sachdev, and Vladislav Lagutin.</p><p>Predictions and model evaluation remain in development. StockSight is for education and research, not financial advice.</p><div className="page-actions"><a href="https://github.com/noahsteinberg/StockSight">GitHub ↗</a><a href="https://github.com/noahsteinberg/StockSight/blob/main/SPECIFICATION.md">Project specification ↗</a></div></section>
    </div>
  </section>;
}
