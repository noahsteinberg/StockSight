import { useEffect, useId, useRef, useState } from 'react';
import { suggestStocks } from './stock-suggestions.js';

// A combobox over the whole supported catalog. Focusing it lists every stock (A–Z)
// in a bounded, scrollable box; typing narrows the list. Used by Analysis and Compare.
export default function StockSearchInput({
  inputRef, id = 'ticker', value, invalid, onChange, onClear, onSelect,
  placeholder = 'Ticker or company name', exclude = [], errorId = 'ticker-error', icon = true,
}) {
  const listId = useId();
  const container = useRef(null);
  const [draftRequest, setDraftRequest] = useState(null);
  const [result, setResult] = useState(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const request = draftRequest?.value === value ? draftRequest : null;
  const current = request && result?.request === request ? result : null;
  const excluded = new Set(exclude);
  const matches = (current?.matches ?? []).filter(stock => !excluded.has(stock.symbol));
  // -2 means "the last option", resolved once the list is known.
  const selectedIndex = activeIndex === -2 ? matches.length - 1 : activeIndex;
  const activeStock = matches[selectedIndex];
  const expanded = Boolean(current);
  const activeId = activeStock ? `${listId}-${activeStock.symbol}` : undefined;
  const emptyLabel = expanded && matches.length === 0 ? (current.failed ? 'Suggestions unavailable' : 'No matches') : '';

  useEffect(() => {
    if (!request) return undefined;
    const controller = new AbortController();
    // Filtering is local, so there is no typing delay; the catalog loads once.
    suggestStocks(request.value, { signal: controller.signal })
      .then(found => {
        if (controller.signal.aborted) return;
        setResult({ request, matches: found });
        if (found.length && request.direction) setActiveIndex(request.direction > 0 ? 0 : -2);
      })
      .catch(() => { if (!controller.signal.aborted) setResult({ request, matches: [], failed: true }); });
    function closeOutside(event) {
      if (!container.current?.contains(event.target)) setDraftRequest(null);
    }
    document.addEventListener('pointerdown', closeOutside);
    return () => {
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
    setDraftRequest({ value: next, direction });
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
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const direction = event.key === 'ArrowDown' ? 1 : -1;
    event.preventDefault();
    if (!expanded) begin(value, direction);
    else if (matches.length) {
      const index = selectedIndex;
      setActiveIndex(index < 0 ? (direction === 1 ? 0 : matches.length - 1) :
        (index + direction + matches.length) % matches.length);
    }
  }

  return <div className="ticker-control" ref={container}>
    <div className="search-input">
      {icon && <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 4 4" /></svg>}
      <input ref={inputRef} id={id} placeholder={placeholder} value={value}
        onChange={event => { onChange(event.target.value); begin(event.target.value); }}
        onFocus={() => { if (!request) begin(value); }}
        onClick={() => { if (!request) begin(value); }}
        onKeyDown={handleKeys} onBlur={dismiss} role="combobox" aria-autocomplete="list"
        aria-expanded={expanded} aria-controls={listId} aria-activedescendant={activeId}
        aria-invalid={Boolean(invalid)} aria-describedby={invalid ? errorId : undefined}
        maxLength={40} autoComplete="off" spellCheck="false" />
      {value && onClear && <button className="clear-search" type="button" aria-label="Clear stock search" onClick={() => { dismiss(); onClear(); }}>×</button>}
    </div>
    {/* Pressing inside the list (an option or its scrollbar) must not blur the input. */}
    <ul id={listId} className="stock-suggestions" role="listbox" aria-label="Stock suggestions" hidden={!expanded}
      onMouseDown={event => event.preventDefault()}>
      {matches.map((stock, index) => <li id={`${listId}-${stock.symbol}`} key={stock.symbol} role="option"
        aria-selected={index === selectedIndex} onClick={() => select(stock)}>
        <strong>{stock.symbol}</strong><span>{stock.name}</span>
      </li>)}
      {emptyLabel && <li role="option" aria-selected={false} aria-disabled="true">{emptyLabel}</li>}
    </ul>
    <span className="sr-only" role="status">{expanded ? (emptyLabel || `${matches.length} ${matches.length === 1 ? 'stock' : 'stocks'}`) : ''}</span>
  </div>;
}
