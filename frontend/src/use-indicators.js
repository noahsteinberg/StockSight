import { useEffect, useState } from 'react';

export default function useIndicators(symbol, range, enabled, priceData) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState(null);
  const key = `${symbol}:${range}:${attempt}`;
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/indicators?range=${range}`, { signal: controller.signal });
        if (!response.ok) throw new Error('Indicators are unavailable. Try again.');
        const data = await response.json();
        if (active) setResult({ key, data });
      } catch (error) {
        if (active) setResult({ key, error: error.name === 'AbortError' ? 'Indicators timed out. Try again.' : error.message });
      } finally { clearTimeout(timeout); }
    }
    load();
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, [enabled, symbol, range, key]);
  const current = enabled && result?.key === key ? result : null;
  const data = current?.data;
  const aligned = data && priceData && data.symbol === symbol && data.range === range &&
    Boolean(priceData.snapshot_id) && data.snapshot_id === priceData.snapshot_id &&
    data.as_of === priceData.as_of && data.source === priceData.source && data.adjustment === priceData.adjustment &&
    data.points?.length === priceData.bars.length && data.points.every((point, index) => point.date === priceData.bars[index].date);
  return {
    data: aligned ? data : null,
    loading: enabled && !current,
    mismatch: Boolean(data && priceData && !aligned),
    error: current?.error || (data && priceData && !aligned ? 'Prices and indicators came from different data snapshots. Reload both to continue.' : null),
    retry: () => setAttempt(value => value + 1),
  };
}
