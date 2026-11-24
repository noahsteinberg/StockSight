import { useEffect, useRef, useState } from 'react';
import { tradingViewSymbol } from './tradingview-symbols.js';

const embedScript = 'https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js';

export default function MarketQuote({ symbol, asOf }) {
  const host = useRef(null);
  const [attempt, setAttempt] = useState(0);
  const [failedAttempt, setFailedAttempt] = useState(null);
  const listing = tradingViewSymbol(symbol);
  const unavailable = !listing || failedAttempt === attempt;
  const symbolURL = listing && `https://www.tradingview.com/symbols/${listing.replace(':', '-')}/`;

  useEffect(() => {
    if (!listing) return;
    // Each effect owns its entire embed. Removing it also removes the old
    // iframe when the ticker changes or React StrictMode mounts again.
    const container = document.createElement('div');
    container.className = 'tradingview-widget-container';
    const widget = document.createElement('div');
    widget.className = 'tradingview-widget-container__widget';
    container.appendChild(widget);
    let active = true;
    let timeout;
    const fail = () => { if (active) setFailedAttempt(attempt); };
    const observer = new MutationObserver(() => {
      const frame = container.querySelector('iframe');
      if (frame) {
        frame.title = `${symbol} market price from TradingView`;
        clearTimeout(timeout);
        observer.disconnect();
      }
    });
    observer.observe(container, { childList: true, subtree: true });
    const script = document.createElement('script');
    script.src = embedScript;
    script.async = true;
    script.textContent = JSON.stringify({ symbol: listing, width: '100%', locale: 'en', colorTheme: 'light', isTransparent: true });
    script.addEventListener('error', fail);
    host.current.appendChild(container);
    timeout = setTimeout(fail, 12000);
    container.appendChild(script);
    return () => {
      active = false;
      clearTimeout(timeout);
      observer.disconnect();
      script.removeEventListener('error', fail);
      container.remove();
    };
  }, [listing, symbol, attempt]);

  return (
    <section className="market-quote" aria-labelledby="market-quote-title">
      <div className="market-quote-heading">
        <h2 id="market-quote-title">Latest market price</h2>
        <span>TradingView · prices may be delayed</span>
      </div>
      <div ref={host} className="market-quote-embed" hidden={unavailable} />
      {unavailable && <div className="market-quote-fallback" role="status">
        <p>Market widget unavailable for {symbol}.</p>
        {listing && <button type="button" onClick={() => setAttempt(value => value + 1)}>Retry market widget</button>}
      </div>}
      <div className="market-quote-footer">
        {symbolURL && <a href={symbolURL} target="_blank" rel="noopener noreferrer">{symbol} by TradingView ↗</a>}
        <p>Historical chart{asOf ? ` through ${asOf}` : ''} below uses stored daily prices.</p>
      </div>
    </section>
  );
}
