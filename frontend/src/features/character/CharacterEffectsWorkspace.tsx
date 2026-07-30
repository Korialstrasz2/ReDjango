import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import type { Effect, EffectConfiguration, EffectOperation, EffectPreset } from "../../lib/types";
import { EffectIcon } from "./EffectIcon";
import { EffectPresetPicker } from "./EffectPresetPicker";

type EffectDraft = {
  name: string;
  description: string;
  origin: string;
  icon: string;
  temporary: boolean;
  operations: EffectOperation[];
};

type EffectAction = (action: string, payload: Record<string, unknown>) => Promise<unknown>;
type EffectEditorFocus = { operationIndex: number; field: "target" | "value" };

type CharacterEffectsWorkspaceProps = {
  characterId: number;
  effects: Effect[];
  configuration: EffectConfiguration;
  open: boolean;
  saving: boolean;
  onOpenChange: (open: boolean) => void;
  onAction: EffectAction;
};

const effectKey = (effect: Effect) => `${effect.scope}-${effect.id}-${effect.slot ?? "custom"}`;
const withoutTemporaryMarker = (value: string) => value.replace(/\s*\(t\)\s*/gi, " ").replace(/\s{2,}/g, " ").trim();
export const effectIconAssetUrl = (name: string | null | undefined, configuration: EffectConfiguration) => {
  const selectedIcon = configuration.icons.find((entry) => entry.value === name);
  return selectedIcon ? selectedIcon.imageUrl : configuration.icons[0]?.imageUrl || "";
};
export const filterEffects = (
  effects: Effect[],
  configuration: EffectConfiguration,
  search: string,
  mode: "text" | "variable",
) => {
  const query = search.trim().toLocaleLowerCase("it");
  if (!query) return effects;
  return effects.filter((effect) => {
    const values = mode === "variable"
      ? effect.operations.flatMap((operation) => [
          operation.target,
          configuration.targets.find((target) => target.value === operation.target)?.label || "",
        ])
      : [effect.name, effect.originName, effect.description];
    return values.some((value) => value.toLocaleLowerCase("it").includes(query));
  });
};

function freshDraft(configuration: EffectConfiguration): EffectDraft {
  return {
    name: "",
    description: "",
    origin: "",
    icon: configuration.icons[0]?.value || "runa",
    temporary: false,
    operations: [{
      target: configuration.targets[0]?.value || "forza",
      operation: configuration.operations[0]?.value || "add",
      value: "0",
      condition: "",
    }],
  };
}

function draftFrom(effect: Effect, configuration: EffectConfiguration): EffectDraft {
  return {
    name: effect.name,
    description: withoutTemporaryMarker(effect.description),
    origin: effect.originName,
    icon: configuration.icons.some((entry) => entry.value === effect.icon) ? effect.icon : "runa",
    temporary: effect.temporary,
    // Un effetto senza modifiche resta senza modifiche: è una condizione narrata,
    // non un modulo da riempire.
    operations: effect.operations.map((operation) => ({ ...operation })),
  };
}

function draftFromPreset(preset: EffectPreset, configuration: EffectConfiguration): EffectDraft {
  return {
    name: preset.name,
    description: withoutTemporaryMarker(preset.description),
    origin: preset.origin,
    icon: configuration.icons.some((entry) => entry.value === preset.icon) ? preset.icon : "runa",
    temporary: preset.temporary,
    operations: preset.operations.map((operation) => ({ ...operation })),
  };
}

function EffectRail({ effects, configuration, selectedKey, onOpen, onSelect, onNew }: {
  effects: Effect[];
  configuration: EffectConfiguration;
  selectedKey: string | null;
  onOpen: () => void;
  onSelect: (effect: Effect) => void;
  onNew: () => void;
}) {
  const hasTemporary = effects.some((effect) => effect.temporary);
  return <aside
    className={["effect-rail", hasTemporary ? "has-temporary" : ""].filter(Boolean).join(" ")}
    aria-label={`Apri tutti gli effetti (${effects.length})`}
    data-component-type="navigation"
    data-theme="dark"
    tabIndex={0}
    onClick={onOpen}
    onKeyDown={(event) => {
      if (event.target !== event.currentTarget || (event.key !== "Enter" && event.key !== " ")) return;
      event.preventDefault();
      onOpen();
    }}
  >
    <div className="effect-rail-heading"><span>Effetti</span><strong>{effects.length}</strong></div>
    <div className="effect-rail-icons">
      {effects.map((effect) => <button
        key={effectKey(effect)}
        type="button"
        className={[selectedKey === effectKey(effect) ? "active" : "", effect.temporary ? "temporary" : ""].filter(Boolean).join(" ")}
        title={effect.name}
        aria-label={`Apri effetto ${effect.name}`}
        onClick={() => onSelect(effect)}
      >
        <EffectIcon name={effect.icon} assetUrl={effectIconAssetUrl(effect.icon, configuration)} />
        {effect.temporary && <span className="effect-temporary-mark" aria-label="Temporaneo">(t)</span>}
      </button>)}
    </div>
    <button className="effect-rail-new" type="button" title="Nuovo effetto" aria-label="Crea un nuovo effetto" onClick={onNew}>+</button>
  </aside>;
}

function EffectEditor({ effect, configuration, saving, initialFocus, onCancel, onSave }: {
  effect: Effect | null;
  configuration: EffectConfiguration;
  saving: boolean;
  initialFocus: EffectEditorFocus | null;
  onCancel: () => void;
  onSave: (values: EffectDraft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<EffectDraft>(() => effect ? draftFrom(effect, configuration) : freshDraft(configuration));
  const [iconSearch, setIconSearch] = useState("");
  const [presetPickerOpen, setPresetPickerOpen] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => setDraft(effect ? draftFrom(effect, configuration) : freshDraft(configuration)), [effect, configuration]);
  useEffect(() => setIconSearch(""), [effect]);
  useEffect(() => {
    if (!initialFocus) return;
    const frame = window.requestAnimationFrame(() => {
      const input = formRef.current?.querySelector<HTMLInputElement>(
        `[data-effect-operation-index="${initialFocus.operationIndex}"][data-effect-operation-field="${initialFocus.field}"]`,
      );
      input?.focus();
      input?.select();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [effect, initialFocus]);

  const filteredIcons = useMemo(() => {
    const query = iconSearch.trim().toLocaleLowerCase("it");
    if (!query) return configuration.icons;
    return configuration.icons.filter((icon) => [icon.label, icon.value, icon.category, icon.keywords]
      .some((value) => value.toLocaleLowerCase("it").includes(query)));
  }, [configuration.icons, iconSearch]);

  const updateOperation = (index: number, values: Partial<EffectOperation>) => {
    setDraft((current) => ({
      ...current,
      operations: current.operations.map((operation, operationIndex) => operationIndex === index ? { ...operation, ...values } : operation),
    }));
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSave(draft);
  };

  return <form ref={formRef} className="effect-editor" onSubmit={submit} data-component-type="form" data-theme="dark">
    <header className="effect-editor-header">
      <div>
        <p className="eyebrow">{effect ? "Modifica effetto" : "Nuovo effetto"}</p>
        <h3>{effect ? effect.name : "Crea e applica"}</h3>
      </div>
      <button
        className="button secondary small effect-preset-open"
        type="button"
        onClick={() => setPresetPickerOpen(true)}
        title="Parti da un preset già pronto"
      >Preset</button>
      {effect?.scope === "legacy" && <span className="effect-format-badge">Verrà personalizzato</span>}
    </header>

    {presetPickerOpen && <EffectPresetPicker
      configuration={configuration}
      onClose={() => setPresetPickerOpen(false)}
      onPick={(preset) => { setDraft(draftFromPreset(preset, configuration)); setPresetPickerOpen(false); }}
    />}

    {effect?.scope === "legacy" && <p className="effect-legacy-note">Salvando, questo effetto attivo passa al formato personalizzato. Lo slot storico e gli altri effetti esistenti restano invariati.</p>}

    <div className="effect-fields-grid">
      <label>Nome<input required maxLength={180} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="Es. Benedizione della Luna" /></label>
      <label className="effect-origin-field">Origine<input maxLength={180} value={draft.origin} onChange={(event) => setDraft({ ...draft, origin: event.target.value })} placeholder="Incantesimo, oggetto, luogo…" /></label>
      <label className="effect-temporary-field"><input type="checkbox" checked={draft.temporary} onChange={(event) => setDraft({ ...draft, temporary: event.target.checked })} /><strong>Temporaneo</strong></label>
      <label className="effect-description-field">Descrizione<textarea rows={3} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} placeholder="Aspetto narrativo e regole dell'effetto…" /></label>
    </div>

    <fieldset className="effect-icon-picker">
      <legend>Icona</legend>
      <div className="effect-icon-picker-tools">
        <label htmlFor="effect-icon-search">Cerca un'icona</label>
        <input id="effect-icon-search" type="search" value={iconSearch} onChange={(event) => setIconSearch(event.target.value)} placeholder="Es. mana, fuoco, maledizione…" />
        <span>{filteredIcons.length} disponibili</span>
      </div>
      <div className="effect-icon-picker-grid">{filteredIcons.map((icon) => <label key={icon.value} className={draft.icon === icon.value ? "selected" : ""}>
        <input type="radio" name="effect-icon" value={icon.value} aria-label={icon.label} checked={draft.icon === icon.value} onChange={() => setDraft({ ...draft, icon: icon.value })} />
        <span className="effect-icon-picker-symbol" title={icon.label}><EffectIcon name={icon.value} assetUrl={icon.imageUrl} /></span>
      </label>)}</div>
    </fieldset>

    <section className="effect-operations-editor">
      <header><div><p className="eyebrow">Modifiche</p></div><button type="button" className="button secondary small" onClick={() => setDraft((current) => ({ ...current, operations: [...current.operations, freshDraft(configuration).operations[0]] }))}>Aggiungi modifica</button></header>
      <div className="effect-operation-list">{draft.operations.map((operation, index) => <article className="effect-operation-row" key={index}>
        <div className="effect-operation-number">{index + 1}</div>
        <label>Campo<input
          required
          aria-label="Campo"
          data-effect-operation-index={index}
          data-effect-operation-field="target"
          list={`effect-targets-${index}`}
          value={configuration.targets.find((target) => target.value === operation.target)?.label || operation.target}
          aria-invalid={!configuration.targets.some((target) => target.value === operation.target)}
          onChange={(event) => {
            const raw = event.target.value.trim();
            const match = configuration.targets.find((target) => target.value.toLocaleLowerCase("it") === raw.toLocaleLowerCase("it") || target.label.toLocaleLowerCase("it") === raw.toLocaleLowerCase("it"));
            event.target.setCustomValidity(match ? "" : "Scegli un campo presente nell'elenco.");
            updateOperation(index, { target: match?.value || raw });
          }}
          onBlur={(event) => event.target.setCustomValidity(configuration.targets.some((target) => target.value === operation.target) ? "" : "Scegli un campo presente nell'elenco.")}
          placeholder="Scrivi per cercare…"
        /><datalist id={`effect-targets-${index}`}>{configuration.targets.map((target) => <option key={target.value} value={target.label}>{target.value}</option>)}</datalist></label>
        <label>Operazione<select aria-label="Operazione" value={operation.operation} onChange={(event) => updateOperation(index, { operation: event.target.value })}>{configuration.operations.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>
        <label className="effect-expression-field">Valore o formula<input required spellCheck={false} data-effect-operation-index={index} data-effect-operation-field="value" value={operation.value} onChange={(event) => updateOperation(index, { value: event.target.value })} placeholder="5 oppure floor(final.mana / 10)" /></label>
        <label className="effect-condition-field">Condizione, facoltativa<input spellCheck={false} value={operation.condition} onChange={(event) => updateOperation(index, { condition: event.target.value })} placeholder="personaggio.livello >= 5" /></label>
        <button className="effect-operation-remove" type="button" onClick={() => setDraft((current) => ({ ...current, operations: current.operations.filter((_, operationIndex) => operationIndex !== index) }))} aria-label={`Rimuovi modifica ${index + 1}`}>×</button>
        <p>{configuration.operations.find((entry) => entry.value === operation.operation)?.description}</p>
      </article>)}</div>
      {!draft.operations.length && <p className="effect-operations-descriptive">Nessuna modifica: l'effetto resta descrittivo e non tocca il calcolo del personaggio.</p>}
    </section>

    <details className="effect-operation-guide">
      <summary>Mini guida alle operazioni</summary>
      <div className="effect-guide-scroll">
        <p className="effect-operation-order-note">{configuration.operationOrderNote}</p>
        {configuration.operations.map((entry) => <article key={entry.value}><h5>{entry.label}</h5><p>{entry.description}</p><code>{entry.example}</code><small>{entry.timing}</small></article>)}
      </div>
    </details>

    <details className="effect-formula-guide">
      <summary>Guida rapida alle formule</summary>
      <div className="effect-formula-guide-grid effect-guide-scroll">{configuration.formulaGuide.map((entry) => <article key={entry.title}><h5>{entry.title}</h5><p>{entry.text}</p><code>{entry.example}</code>{entry.values.length > 0 && <ul>{entry.values.map((value) => <li key={value}><code>{value}</code></li>)}</ul>}</article>)}</div>
    </details>

    <footer className="effect-editor-actions"><button className="button secondary" type="button" onClick={onCancel}>Annulla</button><button className="button primary" type="submit" disabled={saving}>{saving ? "Salvataggio…" : effect ? "Salva modifiche" : "Crea effetto"}</button></footer>
  </form>;
}

export function CharacterEffectsWorkspace({ characterId, effects, configuration, open, saving, onOpenChange, onAction }: CharacterEffectsWorkspaceProps) {
  const [search, setSearch] = useState("");
  const [searchMode, setSearchMode] = useState<"text" | "variable">("text");
  const [selectedKey, setSelectedKey] = useState<string | null>(effects[0] ? effectKey(effects[0]) : null);
  const [editorEffect, setEditorEffect] = useState<Effect | null | undefined>(undefined);
  const [editorFocus, setEditorFocus] = useState<EffectEditorFocus | null>(null);
  const [pendingName, setPendingName] = useState<string | null>(null);
  const selected = effects.find((effect) => effectKey(effect) === selectedKey) || effects[0] || null;
  const filtered = useMemo(
    () => filterEffects(effects, configuration, search, searchMode),
    [configuration, effects, search, searchMode],
  );

  useEffect(() => {
    if (pendingName) {
      const created = effects.find((effect) => effect.name === pendingName && effect.scope === "custom");
      if (created) {
        setSelectedKey(effectKey(created));
        setPendingName(null);
        return;
      }
    }
    if (selectedKey && effects.some((effect) => effectKey(effect) === selectedKey)) return;
    setSelectedKey(effects[0] ? effectKey(effects[0]) : null);
  }, [effects, pendingName, selectedKey]);

  const openEffect = (effect: Effect) => {
    setSelectedKey(effectKey(effect));
    setEditorFocus(null);
    setEditorEffect(undefined);
    onOpenChange(true);
  };
  const startNew = () => {
    setEditorFocus(null);
    setEditorEffect(null);
    onOpenChange(true);
  };
  const startEditing = (effect: Effect, focus: EffectEditorFocus | null = null) => {
    setEditorFocus(focus);
    setEditorEffect(effect);
  };
  const saveEffect = async (values: EffectDraft) => {
    if (editorEffect) {
      await onAction("effects.update", {
        characterId,
        effectId: editorEffect.scope === "custom" ? editorEffect.id : undefined,
        legacySlot: editorEffect.scope === "legacy" ? editorEffect.slot : undefined,
        values,
      });
    } else {
      setPendingName(values.name.trim());
      await onAction("effects.create", { characterId, values });
    }
    setEditorFocus(null);
    setEditorEffect(undefined);
  };
  const removeSelected = async () => {
    if (!selected || !window.confirm(`Rimuovere l'effetto “${selected.name}”?`)) return;
    await onAction("effects.remove", {
      characterId,
      effectId: selected.scope === "custom" ? selected.id : undefined,
      slot: selected.scope === "legacy" ? selected.slot : undefined,
    });
  };

  const targetLabel = (value: string) => configuration.targets.find((entry) => entry.value === value)?.label || value;
  const operationLabel = (value: string) => configuration.operations.find((entry) => entry.value === value)?.label || value;

  return <>
    {!open && <EffectRail effects={effects} configuration={configuration} selectedKey={null} onOpen={() => onOpenChange(true)} onSelect={openEffect} onNew={startNew} />}
    {open && <section className="effects-workspace" aria-label="Gestione effetti" data-component-type="workspace" data-theme="dark">
      <header className="effects-workspace-header">
        <div><p className="eyebrow">Effetti</p><h2>Condizioni attive</h2><p>Effetti personali, ordinati e subito applicati al calcolo.</p></div>
        <button className="effects-close" type="button" onClick={() => onOpenChange(false)} aria-label="Chiudi effetti">×</button>
      </header>
      <div className="effects-workspace-body">
        <aside className="effects-directory">
          <div className="effects-directory-tools">
            <div className="effect-search-heading">
              <label htmlFor="effect-search">Cerca</label>
              <select aria-label="Campo di ricerca degli effetti" value={searchMode} onChange={(event) => setSearchMode(event.target.value as "text" | "variable")}>
                <option value="text">Nome, origine, descrizione</option>
                <option value="variable">Variabile modificata</option>
              </select>
            </div>
            <input id="effect-search" type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={searchMode === "variable" ? "Es. ener per Energia…" : "Nome, origine o descrizione…"} />
            <button className="button primary" type="button" onClick={startNew}>Nuovo effetto</button>
          </div>
          <div className="effects-directory-list">{filtered.length ? filtered.map((effect) => <button key={effectKey(effect)} type="button" className={selected && effectKey(effect) === effectKey(selected) ? "active" : ""} onClick={() => openEffect(effect)}>
            <EffectIcon name={effect.icon} assetUrl={effectIconAssetUrl(effect.icon, configuration)} />
            <span><strong>{effect.name}</strong><small>{effect.originName || "Effetto personale"}</small></span>
            {effect.temporary && <em>(t)</em>}
          </button>) : <p className="empty-copy">Nessun effetto corrisponde alla ricerca.</p>}</div>
        </aside>

        <main className="effect-detail-area">
          {editorEffect !== undefined ? <EffectEditor effect={editorEffect} configuration={configuration} saving={saving} initialFocus={editorFocus} onCancel={() => { setEditorFocus(null); setEditorEffect(undefined); }} onSave={saveEffect} /> : selected ? <article className="effect-detail-card">
            <header>
              <div className="effect-detail-symbol"><EffectIcon name={selected.icon} assetUrl={effectIconAssetUrl(selected.icon, configuration)} /></div>
              <div><p className="eyebrow">Effetto</p><h3>{selected.name}</h3><div className="effect-detail-badges">{selected.temporary && <span>(t) Temporaneo</span>}{selected.scope === "legacy" && <span>Formato storico</span>}{selected.scope === "automatic" && <span>Automatico</span>}</div></div>
              {selected.editable && <div className="effect-detail-actions"><button className="button secondary small" type="button" onClick={() => startEditing(selected)}>{selected.scope === "legacy" ? "Personalizza" : "Modifica"}</button><button className="button danger small" type="button" onClick={removeSelected} disabled={saving}>Rimuovi</button></div>}
            </header>
            <div className="effect-detail-copy"><p>{withoutTemporaryMarker(selected.description) || "Nessuna descrizione."}</p>{selected.originName && <dl><div><dt>Origine</dt><dd>{selected.originName}</dd></div></dl>}</div>
            <section className="effect-operation-summary"><header><p className="eyebrow">Impatto sul PG</p><h4>{selected.operations.length} {selected.operations.length === 1 ? "modifica" : "modifiche"}</h4></header>
              {selected.operations.length ? <div>{selected.operations.map((operation, index) => <article key={`${operation.target}-${index}`}><span>{index + 1}</span><div>
                <button className="effect-operation-edit effect-operation-edit-target" type="button" disabled={!selected.editable} title={selected.editable ? "Modifica campo" : "Effetto automatico"} aria-label={`Modifica il campo della modifica ${index + 1}`} onClick={() => selected.editable && startEditing(selected, { operationIndex: index, field: "target" })}><strong>{targetLabel(operation.target)} · {operationLabel(operation.operation)}</strong></button>
                <button className="effect-operation-edit effect-operation-edit-value" type="button" disabled={!selected.editable} title={selected.editable ? "Modifica valore o formula" : "Effetto automatico"} aria-label={`Modifica il valore o la formula della modifica ${index + 1}`} onClick={() => selected.editable && startEditing(selected, { operationIndex: index, field: "value" })}><code>{operation.value}</code></button>
                {operation.condition && <small>Solo se: <code>{operation.condition}</code></small>}
              </div></article>)}</div> : <p className="empty-copy">Questo effetto storico non espone modifiche configurabili.</p>}
            </section>
            {selected.scope === "custom" && <footer className="effect-order-actions"><span>Ordine di applicazione</span><button type="button" disabled={saving} onClick={() => onAction("effects.move", { characterId, effectId: selected.id, direction: "up" })}>↑ Prima</button><button type="button" disabled={saving} onClick={() => onAction("effects.move", { characterId, effectId: selected.id, direction: "down" })}>↓ Dopo</button></footer>}
          </article> : <div className="effects-empty-state"><EffectIcon name="runa" assetUrl={effectIconAssetUrl("runa", configuration)} /><h3>Nessun effetto attivo</h3><p>Crea un effetto personale e scegli come modifica il personaggio.</p><button className="button primary" type="button" onClick={startNew}>Nuovo effetto</button></div>}
        </main>
      </div>
    </section>}
  </>;
}
