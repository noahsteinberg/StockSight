import { useState } from 'react';
import { useAccount } from './auth-context.js';
import { sectorNames } from './explore-api.js';
import { horizonOptions, purposeOptions, rangeOptions } from './preferences-api.js';

function Choice({ name, value, current, label, onChange }) {
  return <label className="preference-choice">
    <input type="radio" name={name} checked={current === value} onChange={() => onChange(value)} />
    <span>{label}</span>
  </label>;
}

function PreferencesForm({ initial, preferences }) {
  const [draft, setDraft] = useState({
    purpose: initial.purpose, sectors: initial.sectors, horizon: initial.horizon, default_range: initial.default_range,
  });
  const set = key => value => setDraft(current => ({ ...current, [key]: value }));
  const busy = preferences.mutation.busy;
  function toggleSector(sector) {
    setDraft(current => ({
      ...current,
      sectors: current.sectors.includes(sector) ? current.sectors.filter(item => item !== sector) : [...current.sectors, sector],
    }));
  }

  return <form className="preferences-form" onSubmit={event => { event.preventDefault(); preferences.save(draft); }}>
    <fieldset className="page-panel">
      <legend>What would you like to do?</legend>
      <p className="preference-help">Saved for future research features.</p>
      <div className="preference-options">
        {purposeOptions.map(([value, label]) => <Choice key={value} name="purpose" value={value} current={draft.purpose} label={label} onChange={set('purpose')} />)}
        <Choice name="purpose" value={null} current={draft.purpose} label="No preference" onChange={set('purpose')} />
      </div>
    </fieldset>
    <fieldset className="page-panel">
      <legend>Which sectors interest you?</legend>
      <p className="preference-help">Explore can list only stocks in these sectors, with the reason for each match. Leave all unchecked for no preference.</p>
      <div className="preference-options sector-options">
        {sectorNames.map(sector => <label key={sector} className="preference-choice">
          <input type="checkbox" checked={draft.sectors.includes(sector)} onChange={() => toggleSector(sector)} />
          <span>{sector}</span>
        </label>)}
      </div>
      {draft.sectors.length > 0 && <button type="button" className="text-button" onClick={() => set('sectors')([])}>Clear sectors</button>}
    </fieldset>
    <fieldset className="page-panel">
      <legend>What research horizon interests you?</legend>
      <p className="preference-help">Saved for your reference. It doesn’t select a forecast horizon; no forecasts are available.</p>
      <div className="preference-options">
        {horizonOptions.map(([value, label]) => <Choice key={value} name="horizon" value={value} current={draft.horizon} label={label} onChange={set('horizon')} />)}
        <Choice name="horizon" value={null} current={draft.horizon} label="Not sure" onChange={set('horizon')} />
      </div>
    </fieldset>
    <fieldset className="page-panel">
      <legend>Which chart window should open by default?</legend>
      <p className="preference-help">Used by Analysis and Compare until you pick a range there.</p>
      <div className="preference-options">
        {rangeOptions.map(([value, label]) => <Choice key={value} name="default_range" value={value} current={draft.default_range} label={label} onChange={set('default_range')} />)}
        <Choice name="default_range" value={null} current={draft.default_range} label="Page default (3M / 1Y)" onChange={set('default_range')} />
      </div>
    </fieldset>
    <div className="preference-actions">
      <button type="submit" className="primary-button" disabled={busy}>{busy ? 'Saving…' : 'Save preferences'}</button>
      {initial.saved && <button type="button" disabled={busy} onClick={preferences.reset}>Reset preferences</button>}
      <a href="#/explore">Not now</a>
    </div>
  </form>;
}

export default function Preferences({ preferences }) {
  const account = useAccount();
  const { data, mutation } = preferences;
  return <section className="app-page preferences-page" aria-labelledby="preferences-title">
    <div className="page-heading"><h1 id="preferences-title">Research preferences</h1><span className="historical-badge">Optional</span></div>
    <p className="preferences-intro">
      Tell StockSight what you’d like to research. Preferences filter and default what you see through simple, visible rules.
      They don’t create recommendations, change prices or feed any model, and we never ask about income, holdings or other financial details.
    </p>
    {!account.isAuthenticated && <div className="page-panel unavailable-state">
      <h2>Sign in to save preferences</h2>
      <p>Browsing, searching and comparing stocks work without an account.</p>
      <div className="page-actions">
        <button type="button" className="primary-button" disabled={account.pending || !account.configured} onClick={() => account.login()}>Sign in</button>
        <a href="#/explore">Explore stocks</a>
      </div>
    </div>}
    {account.isAuthenticated && <div aria-live="polite">
      {mutation.success && <p className="preferences-status" role="status">{mutation.success} {data?.sectors.length > 0 && <a href="#/explore?mine=1">See matching stocks ↗</a>}</p>}
      {mutation.error && <p className="validation-error" role="alert">{mutation.error}</p>}
      {preferences.error && <div className="analysis-message error-state" role="alert"><p>{preferences.error}</p><button type="button" onClick={preferences.retry}>Retry</button></div>}
      {!data && !preferences.error && <p className="analysis-message" role="status">Loading your preferences…</p>}
      {data && <PreferencesForm key={`${preferences.owner}:${data.updated_at}`} initial={data} preferences={preferences} />}
    </div>}
  </section>;
}
