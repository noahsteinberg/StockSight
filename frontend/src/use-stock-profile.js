import { useEffect, useState } from 'react';

const isText = value => typeof value === 'string' && value.length > 0;
const nullableText = value => value === null || isText(value);

// GET /api/stocks/{symbol}/profile: reviewed company name and sector, or nulls.
export function parseStockProfile(body, symbol) {
  const valid = body && typeof body === 'object' && body.symbol === symbol &&
    nullableText(body.company_name) && nullableText(body.sector) && nullableText(body.sub_industry) &&
    body.source && isText(body.source.name) && isText(body.source.url) && /^https:\/\//.test(body.source.url);
  if (!valid) throw new Error('Company details were incomplete.');
  return body;
}

// Keyed to the symbol, so a slow response for the previous stock is never shown.
export default function useStockProfile(symbol) {
  const [result, setResult] = useState({ symbol: null });
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/stocks/${encodeURIComponent(symbol)}/profile`, { signal: controller.signal })
      .then(async response => {
        if (response.status === 404) return null;
        if (!response.ok) throw new Error('Company details are unavailable.');
        return parseStockProfile(await response.json(), symbol);
      })
      .then(data => setResult({ symbol, data }))
      .catch(error => { if (error.name !== 'AbortError') setResult({ symbol, error: error.message }); });
    return () => controller.abort();
  }, [symbol]);
  return result.symbol === symbol ? result : { symbol, loading: true };
}
