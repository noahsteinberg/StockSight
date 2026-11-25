// Ticker suggestions come from the real supported catalog: GET /api/stocks with a
// limit large enough for every supported stock (494 today), loaded once per page
// visit and then filtered locally, so typing never waits on the network.
const CATALOG_LIMIT = 1000;
let catalog = null;

function loadCatalog() {
  catalog ??= fetch(`/api/stocks?limit=${CATALOG_LIMIT}`)
    .then(response => {
      if (!response.ok) throw new Error('Stock list unavailable');
      return response.json();
    })
    .then(body => {
      if (!Array.isArray(body) || !body.every(stock => typeof stock?.symbol === 'string' && typeof stock?.name === 'string')) {
        throw new Error('Stock list unavailable');
      }
      // Placeholder names (name == symbol) are shown without repeating the ticker.
      return body.map(stock => ({ symbol: stock.symbol, name: stock.name === stock.symbol ? '' : stock.name }))
        .sort((left, right) => left.symbol.localeCompare(right.symbol));
    })
    .catch(error => { catalog = null; throw error; });
  return catalog;
}

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
  if (ticker.startsWith(query)) return 1;
  if (company.startsWith(query)) return 2;
  if (words.some(word => word.startsWith(query))) return 3;
  if (ticker.includes(query) || company.includes(query)) return 4;
  if (query.length >= 3 && [ticker, company, ...words].some(value =>
    [query.length - 1, query.length, query.length + 1].some(length => withinOneEdit(query, value.slice(0, length))),
  )) return 5;
  return Infinity;
}

// An empty input lists every supported stock A–Z; typing narrows and ranks the list
// (exact ticker, ticker prefix, name prefix, word prefix, substring, one typo).
export async function suggestStocks(input, { signal } = {}) {
  signal?.throwIfAborted();
  const stocks = await loadCatalog();
  signal?.throwIfAborted();
  const query = input.trim().toLowerCase().replace(/\s+/g, ' ');
  if (!query) return stocks;
  return stocks
    .map(stock => ({ stock, score: rank(stock, query) }))
    .filter(({ score }) => Number.isFinite(score))
    .sort((left, right) => left.score - right.score || left.stock.symbol.localeCompare(right.stock.symbol))
    .map(({ stock }) => stock);
}
