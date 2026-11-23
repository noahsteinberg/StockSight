const stocks = [
  ['AAPL', 'Apple Inc.'],
  ['ABT', 'Abbott Laboratories'],
  ['ADBE', 'Adobe Inc.'],
  ['AMD', 'Advanced Micro Devices'],
  ['AMZN', 'Amazon.com Inc.'],
  ['ARKK', 'ARK Innovation ETF'],
  ['AVGO', 'Broadcom Inc.'],
  ['BA', 'The Boeing Company'],
  ['BRK-B', 'Berkshire Hathaway Inc.'],
  ['COST', 'Costco Wholesale Corporation'],
  ['DIS', 'The Walt Disney Company'],
  ['GOOG', 'Alphabet Inc.'],
  ['GS', 'The Goldman Sachs Group'],
  ['IBM', 'International Business Machines'],
  ['INTC', 'Intel Corporation'],
  ['JPM', 'JPMorgan Chase & Co.'],
  ['META', 'Meta Platforms Inc.'],
  ['MSFT', 'Microsoft Corporation'],
  ['NFLX', 'Netflix Inc.'],
  ['NVDA', 'NVIDIA Corporation'],
  ['ORCL', 'Oracle Corporation'],
  ['PLTR', 'Palantir Technologies Inc.'],
  ['QCOM', 'Qualcomm Inc.'],
  ['QQQ', 'Invesco QQQ Trust'],
  ['SPY', 'SPDR S&P 500 ETF Trust'],
  ['TSLA', 'Tesla Inc.'],
  ['V', 'Visa Inc.'],
  ['WMT', 'Walmart Inc.'],
].map(([symbol, name]) => ({ symbol, name }));

function withinOneEdit(left, right) {
  if (Math.abs(left.length - right.length) > 1) return false;
  let index = 0;
  while (index < left.length && index < right.length && left[index] === right[index]) index++;
  if (index === Math.min(left.length, right.length)) return true;
  if (left.length > right.length) return left.slice(index + 1) === right.slice(index);
  if (left.length < right.length) return left.slice(index) === right.slice(index + 1);
  return left.slice(index + 1) === right.slice(index + 1) ||
    (left[index] === right[index + 1] && left[index + 1] === right[index] && left.slice(index + 2) === right.slice(index + 2));
}

function rank(stock, query) {
  const ticker = stock.symbol.toLowerCase();
  const company = stock.name.toLowerCase();
  const words = company.match(/[a-z0-9]+/g) ?? [];
  if (ticker === query) return 0;
  if (ticker.startsWith(query) || company.startsWith(query)) return 1;
  if (words.some(word => word.startsWith(query))) return 2;
  if (ticker.includes(query) || company.includes(query)) return 3;
  if (query.length >= 3 && [ticker, company, ...words].some(value =>
    [query.length - 1, query.length, query.length + 1].some(length => withinOneEdit(query, value.slice(0, length))),
  )) return 4;
  return Infinity;
}

// Replace this provider with an API request returning the same { symbol, name } records.
export async function suggestStocks(input, { signal } = {}) {
  signal?.throwIfAborted();
  const query = input.trim().toLowerCase().replace(/\s+/g, ' ');
  if (!query) return [];
  return stocks
    .map(stock => ({ stock, score: rank(stock, query) }))
    .filter(({ score }) => Number.isFinite(score))
    .sort((left, right) => left.score - right.score || left.stock.symbol.localeCompare(right.stock.symbol))
    .slice(0, 8)
    .map(({ stock }) => stock);
}
