const reasons = ['insufficient_history', 'insufficient_matches', 'invalid_history'];
const finite = value => typeof value === 'number' && Number.isFinite(value);
const integer = (value, min, max) => Number.isInteger(value) && value >= min && value <= max;
const date = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
  !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().startsWith(value);
const setup = value => value && ['change_20_pct', 'daily_variability_pct', 'vs_average_50_pct'].every(key => finite(value[key])) && value.daily_variability_pct >= 0;
const near = (a, b) => finite(a) && finite(b) && Math.abs(a - b) < 1e-7;
function percentile(values, q) {
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position), upper = Math.ceil(position);
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
}

export function parsePatterns(body, symbol, horizon) {
  const fail = () => { throw new Error('The historical-pattern response was incomplete or inconsistent. Try again.'); };
  if (!body || body.methodology !== 'historical-price-patterns-v1' || body.symbol !== symbol ||
      body.horizon_sessions !== horizon || ![5, 21].includes(horizon) || !date(body.as_of) ||
      typeof body.snapshot_id !== 'string' || !body.snapshot_id || typeof body.name !== 'string' ||
      typeof body.source !== 'string' || typeof body.source_url !== 'string' || !/^https?:\/\//.test(body.source_url) ||
      typeof body.adjustment !== 'string' || !date(body.calculation_start) || body.calculation_start > body.as_of ||
      !integer(body.calculation_sessions, 1, 2500) || typeof body.has_earlier !== 'boolean' ||
      !integer(body.eligible_candidates, 0, 2500) || !integer(body.excluded_event_windows, 0, 2500) ||
      !integer(body.matched_count, 0, 12) || !Array.isArray(body.matches) || !Array.isArray(body.points)) fail();
  if (body.status === 'unavailable') {
    if (!reasons.includes(body.reason) || body.summary !== null || body.matches.length || body.points.length ||
        body.matched_count !== 0 || (body.current_setup !== null && !setup(body.current_setup))) fail();
    return body;
  }
  if (body.status !== 'available' || body.reason !== null || !setup(body.current_setup) ||
      body.matched_count < 8 || body.matches.length !== body.matched_count ||
      body.eligible_candidates < body.matched_count || body.points.length !== horizon + 1) fail();
  for (const [i, match] of body.matches.entries()) {
    if (!match || !date(match.date) || !date(match.end_date) || match.date >= match.end_date || match.end_date > body.as_of ||
        match.date < body.calculation_start || !setup(match.setup) || !Array.isArray(match.path) ||
        match.path.length !== horizon + 1 || !match.path.every(value => finite(value) && value > -100) ||
        !near(match.path[0], 0) || !near(match.path[horizon], match.change_pct) ||
        body.matches.slice(0, i).some(other => !(other.end_date < match.date || match.end_date < other.date))) fail();
  }
  for (const [i, point] of body.points.entries()) {
    const values = body.matches.map(match => match.path[i]);
    if (!point || point.session !== i || !near(point.lower_quartile, percentile(values, .25)) ||
        !near(point.median, percentile(values, .5)) || !near(point.upper_quartile, percentile(values, .75))) fail();
  }
  const outcomes = body.matches.map(match => match.change_pct), summary = body.summary;
  if (!summary || !near(summary.median_change_pct, percentile(outcomes, .5)) ||
      !near(summary.lower_quartile_pct, percentile(outcomes, .25)) ||
      !near(summary.upper_quartile_pct, percentile(outcomes, .75)) ||
      summary.rose !== outcomes.filter(value => value > 0).length ||
      summary.fell !== outcomes.filter(value => value < 0).length ||
      summary.unchanged !== outcomes.filter(value => value === 0).length) fail();
  return body;
}

export async function fetchPatterns(symbol, horizon, signal) {
  const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/patterns?horizon_sessions=${horizon}`, { signal });
  if (!response.ok) throw new Error(response.status === 404 ? 'No stored history is available for this stock.' :
    response.status === 503 ? 'Stored history is temporarily unavailable. Try again.' : 'Could not load historical patterns. Try again.');
  return parsePatterns(await response.json(), symbol, horizon);
}
