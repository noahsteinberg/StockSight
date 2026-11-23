import { useEffect, useId, useRef, useState } from 'react';
import { suggestStocks } from './stock-suggestions.js';

export default function StockSearchInput({ inputRef, value, invalid, onChange, onClear, onSelect }) {
  const listId = useId();
  const container = useRef(null);
  const [draftRequest, setDraftRequest] = useState(null);
  const [result, setResult] = useState(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const request = draftRequest?.value === value ? draftRequest : null;
  const current = request && result?.request === request ? result : null;
  const matches = current?.matches ?? [];
  const activeStock = matches[activeIndex];
  const expanded = Boolean(current);
  const activeId = activeStock ? `${listId}-${activeStock.symbol}` : undefined;
  const emptyLabel = expanded && matches.length === 0 ? (current.failed ? 'Suggestions unavailable' : 'No matches') : '';

  useEffect(() => {
    if (!request) return;
    const controller = new AbortController();
    const debounce = setTimeout(async () => {
      try {
        const matches = await suggestStocks(request.value, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setResult({ request, matches });
        if (matches.length && request.direction) setActiveIndex(request.direction > 0 ? 0 : matches.length - 1);
      } catch {
        if (!controller.signal.aborted) setResult({ request, matches: [], failed: true });
      }
    }, 200);
    function closeOutside(event) {
      if (!container.current?.contains(event.target)) setDraftRequest(null);
    }
    document.addEventListener('pointerdown', closeOutside);
    return () => {
      clearTimeout(debounce);
      controller.abort();
      document.removeEventListener('pointerdown', closeOutside);
    };
  }, [request]);

  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' });
  }, [activeId]);

  function dismiss() {
    setDraftRequest(null);
    setActiveIndex(-1);
  }

  function begin(next, direction = 0) {
    setActiveIndex(-1);
    setDraftRequest(next.trim() ? { value: next, direction } : null);
  }

  function select(stock) {
    dismiss();
    onSelect(stock.symbol);
  }

  function handleKeys(event) {
    if (event.nativeEvent.isComposing) return;
    if (event.key === 'Escape' && request) {
      event.preventDefault();
      event.stopPropagation();
      dismiss();
    }
    if (event.key === 'Enter') {
      if (activeStock) {
        event.preventDefault();
        select(activeStock);
      } else dismiss();
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || !value.trim()) return;
    const direction = event.key === 'ArrowDown' ? 1 : -1;
    if (!request) {
      event.preventDefault();
      begin(value, direction);
    } else if (matches.length) {
      event.preventDefault();
      setActiveIndex(index => index === -1 ? (direction === 1 ? 0 : matches.length - 1) :
        (index + direction + matches.length) % matches.length);
    }
  }

  return <div className="ticker-control" ref={container}>
    <div className="search-input">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 4 4" /></svg>
      <input ref={inputRef} id="ticker" placeholder="Ticker or company name" value={value}
        onChange={event => { onChange(event.target.value); begin(event.target.value); }}
        onKeyDown={handleKeys} onBlur={dismiss} role="combobox" aria-autocomplete="list"
        aria-expanded={expanded} aria-controls={listId} aria-activedescendant={activeId}
        aria-invalid={Boolean(invalid)} aria-describedby={invalid ? 'ticker-error' : undefined}
        maxLength={40} required autoComplete="off" spellCheck="false" />
      {value && <button className="clear-search" type="button" aria-label="Clear stock search" onClick={() => { dismiss(); onClear(); }}>×</button>}
    </div>
    <ul id={listId} className="stock-suggestions" role="listbox" aria-label="Stock suggestions" hidden={!expanded}>
      {matches.map((stock, index) => <li id={`${listId}-${stock.symbol}`} key={stock.symbol} role="option"
        aria-selected={index === activeIndex} onMouseDown={event => event.preventDefault()} onClick={() => select(stock)}>
        <strong>{stock.symbol}</strong><span>{stock.name}</span>
      </li>)}
      {emptyLabel && <li role="option" aria-selected={false} aria-disabled="true">{emptyLabel}</li>}
    </ul>
    <span className="sr-only" role="status">{emptyLabel}</span>
  </div>;
}
