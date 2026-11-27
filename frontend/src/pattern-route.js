// Public links preserve the selected stock and the historical outcome window.
export const patternHorizon = value => String(value) === '5' ? 5 : 21;

export function patternHash(symbol, horizon = 21) {
  const params = new URLSearchParams({ symbol, horizon: String(patternHorizon(horizon)) });
  return `#/predictions?${params}`;
}
