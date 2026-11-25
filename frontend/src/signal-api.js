// GET /api/stocks/{symbol}/signals: typed research-signal status (issue #19 phase 5).
// No model is approved, so the API answers "unavailable". The adapter still checks
// the full contract (FRONTEND_ML_INTEGRATION_SPEC.md §4) so a malformed or
// inconsistent response can never render as a signal.

export const signalHorizon = 1;

export const reasonMessages = {
  model_not_approved: 'No approved model signal is available.',
  insufficient_history: 'There isn’t enough stored history for a signal.',
  input_not_settled: 'The latest session’s data hasn’t settled yet.',
  stale_batch: 'The last signal is out of date, so it isn’t shown as current.',
  incompatible_artifact: 'The model and data versions don’t match, so no signal is shown.',
};

const signalFields = ['target_kind', 'as_of_session', 'target_session', 'published_at', 'direction', 'raw_score',
  'probability', 'signal_strength', 'universe_percentile', 'risk_level', 'model_version', 'data_snapshot', 'provenance'];
const requiredWhenAvailable = ['target_kind', 'as_of_session', 'target_session', 'published_at', 'model_version', 'data_snapshot', 'provenance'];
const isDate = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
const inRange = (value, low, high) => value === null || (typeof value === 'number' && Number.isFinite(value) && value >= low && value <= high);

export function parseSignal(body, symbol) {
  const base = body && typeof body === 'object' &&
    body.schema_version === '1' && body.ticker === symbol &&
    body.horizon_sessions === signalHorizon && ['available', 'unavailable'].includes(body.status) &&
    signalFields.every(field => field in body);
  const unavailable = base && body.status === 'unavailable' &&
    body.unavailable_reason in reasonMessages && signalFields.every(field => body[field] === null);
  const available = base && body.status === 'available' && body.unavailable_reason === null &&
    requiredWhenAvailable.every(field => body[field] !== null) &&
    isDate(body.as_of_session) && isDate(body.target_session) && body.as_of_session < body.target_session &&
    inRange(body.probability, 0, 1) && inRange(body.universe_percentile, 0, 100);
  if (!unavailable && !available) throw new Error('The signal response was incomplete or inconsistent, so nothing is shown.');
  return body;
}

export async function fetchSignal(symbol, signal) {
  const params = new URLSearchParams({ horizon_sessions: String(signalHorizon) });
  const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/signals?${params}`, { signal });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(response.status === 503 ? 'Signal status is temporarily unavailable. Try again.' : 'Could not check the signal status. Try again.');
  return parseSignal(await response.json(), symbol);
}
