import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { NoteSectionEditor } from "../notes/NoteSectionEditor";
import {
  DIVERSION_STEPS,
  LOCKPICK_ATTEMPTS,
  LOCKPICK_SETS,
  applyToggle,
  basesForMode,
  calculateCheck,
  togglesForMode,
  type TheftMode,
} from "./theftRules";

type Props = { characterId: number | null; notify: (message: string, kind?: "success" | "error" | "info") => void };

const GUIDE_LINK = "/guides?guida=Regole+Varie#scassinare-borseggiare";

function signed(value: number) {
  return `${value >= 0 ? "+" : "−"}${Math.abs(value)}`;
}

export function TheftTool({ characterId, notify }: Props) {
  const [mode, setMode] = useState<TheftMode>("scasso");
  const [lockBase, setLockBase] = useState("comune");
  const [pocketBase, setPocketBase] = useState("mela");
  const [lockToggles, setLockToggles] = useState<string[]>([]);
  const [pocketToggles, setPocketToggles] = useState<string[]>([]);
  const [diversion, setDiversion] = useState(0);
  const [manual, setManual] = useState(0);
  const [setKey, setSetKey] = useState("nessuno");

  const isLock = mode === "scasso";
  const baseKey = isLock ? lockBase : pocketBase;
  const active = isLock ? lockToggles : pocketToggles;
  const setBase = isLock ? setLockBase : setPocketBase;
  const setActive = isLock ? setLockToggles : setPocketToggles;

  const check = useMemo(
    () => calculateCheck(mode, baseKey, active, diversion, manual, setKey),
    [mode, baseKey, active, diversion, manual, setKey],
  );

  const reset = () => {
    setActive([]);
    setManual(0);
    if (!isLock) setDiversion(0);
  };

  return <div className="theft-tool" data-component-type="panel" data-theme="dark">
    <nav className="theft-modes" role="tablist" aria-label="Tipo di prova" data-component-type="tabset" data-theme="gold">
      <button type="button" role="tab" aria-selected={isLock} className={isLock ? "active" : ""} onClick={() => setMode("scasso")}>
        <span aria-hidden="true">⚿</span><strong>Scasso</strong><small>Ingegneria</small>
      </button>
      <button type="button" role="tab" aria-selected={!isLock} className={!isLock ? "active" : ""} onClick={() => setMode("borseggio")}>
        <span aria-hidden="true">✧</span><strong>Borseggio</strong><small>Rapidità di mano</small>
      </button>
    </nav>

    <section className="theft-calculator">
      <fieldset className="theft-bases">
        <legend>{isLock ? "Livello della serratura" : "Cosa stai rubando"}</legend>
        <div>{basesForMode(mode).map((entry) => <button
          key={entry.key}
          type="button"
          className={entry.key === baseKey ? "active" : ""}
          aria-pressed={entry.key === baseKey}
          title={entry.hint}
          onClick={() => setBase(entry.key)}
        ><strong>{entry.label}</strong><em>{entry.threshold}</em></button>)}</div>
      </fieldset>

      <fieldset className="theft-toggles">
        <legend>Circostanze</legend>
        <div>{togglesForMode(mode).map((toggle) => <label key={toggle.key} className={active.includes(toggle.key) ? "checked" : ""} title={toggle.hint}>
          <input
            type="checkbox"
            checked={active.includes(toggle.key)}
            onChange={() => setActive(applyToggle(mode, active, toggle.key))}
          />
          <span aria-hidden="true" className="theft-check" />
          <span className="theft-toggle-copy"><strong>{toggle.label}</strong><small>{toggle.hint}</small></span>
          <em>{toggle.value === 0 ? "—" : signed(toggle.value)}</em>
        </label>)}</div>
      </fieldset>

      {!isLock && <fieldset className="theft-diversion">
        <legend>Diversivo</legend>
        <div>{DIVERSION_STEPS.map((step) => <button
          key={step}
          type="button"
          className={step === diversion ? "active" : ""}
          aria-pressed={step === diversion}
          onClick={() => setDiversion(step)}
        >{step === 0 ? "Nessuno" : `−${step}`}</button>)}</div>
      </fieldset>}

      {isLock && <fieldset className="theft-set">
        <legend>Set da scasso</legend>
        <select value={setKey} onChange={(event) => setSetKey(event.target.value)}>
          {LOCKPICK_SETS.map((entry) => <option key={entry.key} value={entry.key}>
            {entry.label} · {entry.bonus === 0 ? "nessun bonus" : `${signed(entry.bonus)} al tiro`}
          </option>)}
        </select>
        <p>Il set si rompe dopo {LOCKPICK_ATTEMPTS} tentativi falliti: segna le cariche rimaste qui sotto.</p>
      </fieldset>}

      <fieldset className="theft-manual">
        <legend>Modificatore manuale</legend>
        <div>
          <button type="button" onClick={() => setManual((current) => Math.max(-20, current - 1))} aria-label="Riduci il modificatore manuale">−</button>
          <input
            type="number"
            value={manual}
            min={-20}
            max={20}
            aria-label="Modificatore manuale alla soglia"
            onChange={(event) => setManual(Math.max(-20, Math.min(20, Math.trunc(Number(event.target.value) || 0))))}
          />
          <button type="button" onClick={() => setManual((current) => Math.min(20, current + 1))} aria-label="Aumenta il modificatore manuale">+</button>
        </div>
      </fieldset>
    </section>

    <section className="theft-readout" aria-live="polite">
      <div className="theft-total">
        <small>Soglia da superare</small>
        <strong>{check.threshold}</strong>
        <span>{check.base.label} {check.base.threshold} · modificatore {signed(check.modifier)}</span>
      </div>
      <div className="theft-breakdown">
        <p className="eyebrow">Modificatore finale <b>{signed(check.modifier)}</b></p>
        {check.contributions.length
          ? <ul>{check.contributions.map((entry) => <li key={entry.key}>
            <span>{entry.label}{entry.note && <small> · {entry.note}</small>}</span><em>{signed(entry.value)}</em>
          </li>)}</ul>
          : <p className="empty-copy">Nessuna circostanza attiva: vale la soglia nuda.</p>}
        {isLock && check.rollBonus !== 0 && <p className="theft-roll-bonus">Il set aggiunge <b>{signed(check.rollBonus)}</b> al tiro, non alla soglia.</p>}
        <p className="theft-competence">Tira <b>{check.competence}</b> contro <b>{check.threshold}</b>.</p>
      </div>
      <button type="button" className="button secondary small" onClick={reset}>Azzera circostanze</button>
    </section>

    <section className="theft-note">
      <header>
        <div><p className="eyebrow">Promemoria</p><h3>Note di furto</h3></div>
        <Link className="button secondary small" to={GUIDE_LINK}>Apri la regola</Link>
      </header>
      {characterId
        ? <NoteSectionEditor key="furto" characterId={characterId} section="furto" notify={notify} rows={7} minimal />
        : <p className="empty-copy">Scegli un personaggio per annotare cariche e set.</p>}
    </section>
  </div>;
}
