import test from 'node:test';
import assert from 'node:assert/strict';
import { parsePatterns } from '../src/pattern-api.js';

// Synthetic contract data only: hand-calculated quartiles for eight outcomes.
const outcomes = [-8, -4, -2, 0, 2, 4, 8, 12];
const setup = { change_20_pct: 2, daily_variability_pct: 1, vs_average_50_pct: 3 };
function fixture() {
  return {
    methodology: 'historical-price-patterns-v1', symbol: 'TEST', name: 'Synthetic only',
    as_of: '2025-01-01', snapshot_id: 'test-only', source: 'test', source_url: 'https://example.test',
    adjustment: 'test', calculation_start: '2023-01-01', calculation_sessions: 500,
    has_earlier: false, horizon_sessions: 21, status: 'available', reason: null, current_setup: { ...setup },
    eligible_candidates: 400, excluded_event_windows: 0, matched_count: 8,
    summary: { median_change_pct: 1, lower_quartile_pct: -2.5, upper_quartile_pct: 5, rose: 4, fell: 3, unchanged: 1 },
    matches: outcomes.map((outcome, i) => ({
      date: `2024-${String(i + 1).padStart(2, '0')}-01`, end_date: `2024-${String(i + 1).padStart(2, '0')}-22`,
      setup: { ...setup }, change_pct: outcome,
      path: Array.from({ length: 22 }, (_, j) => outcome * j / 21),
    })),
    points: Array.from({ length: 22 }, (_, j) => ({
      session: j, lower_quartile: -2.5 * j / 21, median: j / 21, upper_quartile: 5 * j / 21,
    })),
  };
}

test('accepts inspectable paths with independently specified quartiles and zero outcomes', () => {
  assert.equal(parsePatterns(fixture(), 'TEST', 21).matched_count, 8);
});

test('rejects wrong identity, horizon, future, overlap and inconsistent summaries', () => {
  const mutations = [
    b => { b.symbol = 'OTHER'; }, b => { b.horizon_sessions = 5; },
    b => { b.matches[0].end_date = '2025-01-02'; },
    b => { b.matches[1].date = '2024-01-21'; },
    b => { b.summary.rose = 5; }, b => { b.summary.median_change_pct = 99; },
    b => { b.points[5].upper_quartile = 99; }, b => { b.matches[0].path[21] = 99; },
    b => { b.matches[0].path[1] = NaN; }, b => { b.matches[0].path[1] = -100; },
    b => { b.matches[0] = null; }, b => { b.points[0] = null; },
    b => { b.matches[0].date = '2024-02-30'; }, b => { b.calculation_sessions = 2501; },
  ];
  for (const mutate of mutations) {
    const body = fixture(); mutate(body);
    assert.throws(() => parsePatterns(body, 'TEST', 21), /incomplete or inconsistent/);
  }
});

test('unavailable responses cannot accidentally display outcomes', () => {
  const unavailable = { ...fixture(), status: 'unavailable', reason: 'insufficient_history',
    current_setup: null, matched_count: 0, matches: [], points: [], summary: null };
  assert.equal(parsePatterns(unavailable, 'TEST', 21).status, 'unavailable');
  assert.throws(() => parsePatterns({ ...unavailable, summary: fixture().summary }, 'TEST', 21));
  assert.throws(() => parsePatterns({ ...unavailable, reason: 'guess' }, 'TEST', 21));
});
