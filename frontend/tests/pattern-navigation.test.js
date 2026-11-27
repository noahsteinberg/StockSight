import test from 'node:test';
import assert from 'node:assert/strict';
import { patternHash, patternHorizon } from '../src/pattern-route.js';
import { parsePatternSnapshot } from '../src/pattern-api.js';

test('historical links preserve the ticker and selected window in a shareable URL', () => {
  assert.equal(patternHash('AAPL', 5), '#/predictions?symbol=AAPL&horizon=5');
  assert.equal(patternHash('BRK-B', 21), '#/predictions?symbol=BRK-B&horizon=21');
  assert.equal(patternHorizon('5'), 5);
  for (const value of [null, undefined, '21', '0', '6', '05', 'bad']) {
    assert.equal(patternHorizon(value), 21);
  }
});

test('a standalone result must be anchored to an identified current stored-price snapshot', () => {
  const body = { symbol: 'AAPL', name: 'Apple', snapshot_id: 'revision-1', as_of: '2026-11-25', bars: [{ date: '2026-11-25' }] };
  assert.deepEqual(parsePatternSnapshot(body, 'AAPL'), { symbol: 'AAPL', name: 'Apple', snapshot_id: 'revision-1', as_of: '2026-11-25' });
  for (const change of [{symbol:'MSFT'}, {snapshot_id:''}, {as_of:'2026-02-30'}, {bars:[]}, {bars:[{date:'2026-11-24'}]}]) {
    assert.throws(() => parsePatternSnapshot({ ...body, ...change }, 'AAPL'), /incomplete/);
  }
});
