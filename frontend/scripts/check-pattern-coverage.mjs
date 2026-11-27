// Read-only catalog acceptance. Writes a compact report, never raw price histories.
import process from 'node:process';
import { writeFile } from 'node:fs/promises';
import { parsePatterns } from '../src/pattern-api.js';

const base = new URL(process.argv[2] || 'http://127.0.0.1:8000');
if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password) {
  throw new Error('Use an HTTP API origin without credentials.');
}
const startedAt = new Date().toISOString();
async function get(path) {
  const response = await fetch(new URL(path, base), { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

const stocks = await get('/api/stocks?limit=1000');
if (!Array.isArray(stocks) || !stocks.length || stocks.length === 1000 ||
    new Set(stocks.map(s => s.symbol)).size !== stocks.length) {
  throw new Error('The supported-stock catalog is empty, duplicated or possibly truncated.');
}
const results = [];
let next = 0;
async function worker() {
  while (next < stocks.length) {
    const { symbol } = stocks[next++];
    const row = { symbol, outcomes: [], errors: [] };
    try {
      const history = await get(`/api/stocks/${encodeURIComponent(symbol)}/prices?range=1mo`);
      for (const horizon of [5, 21]) {
        try {
          const raw = await get(`/api/stocks/${encodeURIComponent(symbol)}/patterns?horizon_sessions=${horizon}`);
          const body = parsePatterns(raw, symbol, horizon);
          if (body.snapshot_id !== history.snapshot_id || body.as_of !== history.as_of) {
            throw new Error('Chart/pattern snapshot mismatch');
          }
          row.outcomes.push({ horizon, status: body.status, reason: body.reason,
            matches: body.matched_count, as_of: body.as_of, sessions: body.calculation_sessions });
        } catch (error) {
          row.errors.push({ horizon, message: error.message });
        }
      }
    } catch (error) {
      row.errors.push({ message: error.message });
    }
    results.push(row);
    if (results.length % 50 === 0 || results.length === stocks.length) {
      process.stdout.write(`Checked ${results.length}/${stocks.length} stocks\n`);
    }
  }
}
await Promise.all(Array.from({ length: 3 }, worker));
results.sort((a, b) => a.symbol.localeCompare(b.symbol));
const outcomes = results.flatMap(row => row.outcomes);
const unavailable = results.flatMap(row => row.outcomes.filter(o => o.status === 'unavailable')
  .map(o => ({ symbol: row.symbol, ...o })));
const errors = results.filter(row => row.errors.length);
const summary = { stocks: stocks.length, checked: results.length, responses: outcomes.length,
  available: outcomes.filter(o => o.status === 'available').length,
  unavailable, errors, passed: errors.length === 0 && outcomes.length === stocks.length * 2 };
if (process.argv[3]) await writeFile(process.argv[3], JSON.stringify({
  started_at: startedAt, finished_at: new Date().toISOString(), summary, results,
}, null, 2) + '\n');
process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
if (!summary.passed) process.exitCode = 1;
