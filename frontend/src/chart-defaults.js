const storageKey = 'stocksight:chart-defaults';

export const defaultChartSettings = { showSma: false, showRsi: false };

export function readChartDefaults() {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    return { showSma: saved?.showSma === true, showRsi: saved?.showRsi === true };
  } catch {
    return defaultChartSettings;
  }
}

export function saveChartDefaults(settings) {
  try {
    localStorage.setItem(storageKey, JSON.stringify(settings));
  } catch { /* The current tab still applies the defaults when storage is blocked. */ }
}
