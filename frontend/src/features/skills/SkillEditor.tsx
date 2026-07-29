import { type FormEvent, useMemo, useState } from "react";

import type { EffectConfiguration, SkillFamily } from "../../lib/types";
import type { ActiveReminder, PassiveFeature, SkillOption, UnifiedSkill } from "./types";

type Props = {
  skill: UnifiedSkill | null;
  templateSkill?: UnifiedSkill | null;
  suggestedNumber?: number;
  families: SkillFamily[];
  skillOptions: SkillOption[];
  effectConfiguration: EffectConfiguration;
  saving: boolean;
  onSave: (values: Record<string, unknown>) => void;
  onCancel: () => void;
  onArchive?: () => void;
  onDelete?: () => void;
  submitLabel?: string;
  allowTemplateIdentity?: boolean;
};

type Draft = {
  name: string; slug: string; number: string; familyId: string; familyOrder: string;
  magic: boolean; baseXpCost: string; xpType: string; rulesCost: string;
  description: string; requirementsText: string; prerequisiteIds: number[];
  spellTier: string; spellRange: string; spellEffectUnit: string; spellBaseMana: string;
  spellEffectPerMana: string; spellMinimumMana: string; spellRounding: string;
  spellFixedCosts: Record<string, number>;
  spellLegacyFormula: string; spellCostNotes: string; profileTags: string; profileNotes: string;
  passiveEffects: PassiveFeature[]; activeReminders: ActiveReminder[]; icon: string; notes: string; metadata: string;
};

const EMPTY_OPERATION = { target: "pa", operation: "add", value: "1", condition: "" };
const EMPTY_COSTS = { pf: 0, mana: 0, energia: 0, potere: 0, pa: 0, stanchezza: 0 };
// Il Mana fisso vive in "Mana fisso iniziale" perché entra nella conversione in
// Energia e PA; qui restano solo le risorse che si sommano senza essere convertite.
const EMPTY_FIXED_SPELL_COSTS = { pf: 0, energia: 0, potere: 0, pa: 0, stanchezza: 0 };

function draftFrom(skill: UnifiedSkill | null, templateSkill: UnifiedSkill | null, families: SkillFamily[], suggestedNumber?: number): Draft {
  const source = skill || templateSkill;
  return {
    name: source?.name || "", slug: skill?.slug || "", number: skill ? String(skill.number) : templateSkill && suggestedNumber ? String(suggestedNumber) : "",
    familyId: String(source?.familyId || families[0]?.id || ""), familyOrder: String(source?.familyOrder || 0),
    magic: Boolean(source?.magic), baseXpCost: String(source?.baseXpCost || 0),
    xpType: source?.xpType || "all", rulesCost: source?.rulesCost || "",
    description: source?.description || "", requirementsText: source?.requirementsText || "",
    prerequisiteIds: [...(source?.unlock.prerequisiteIds || [])],
    spellTier: source?.spell?.tier || "base", spellRange: source?.spell?.range || "",
    spellEffectUnit: source?.spell?.effectUnit || "Effetto", spellBaseMana: String(source?.spell?.baseMana || 0),
    spellEffectPerMana: String(source?.spell?.effectPerMana || 1), spellMinimumMana: String(source?.spell?.minimumMana || 0),
    spellRounding: source?.spell?.rounding || "none", spellLegacyFormula: source?.spell?.legacyFormula || "",
    spellCostNotes: source?.spell?.costNotes || "",
    spellFixedCosts: { ...EMPTY_FIXED_SPELL_COSTS, ...(source?.spell?.fixedCosts || {}) },
    profileTags: JSON.stringify(source?.profileTags || {}, null, 2), profileNotes: source?.profileNotes || "",
    passiveEffects: (source?.passiveEffects || []).map((feature) => ({ ...feature, operations: feature.operations.map((operation) => ({ ...operation })) })),
    activeReminders: (source?.activeReminders || []).map((feature) => ({ ...feature, costs: { ...feature.costs } })),
    icon: source?.icon || "runa", notes: source?.notes || "", metadata: JSON.stringify(skill?.metadata || {}, null, 2),
  };
}

export function SkillEditor({ skill, templateSkill = null, suggestedNumber, families, skillOptions, effectConfiguration, saving, onSave, onCancel, onArchive, onDelete, submitLabel, allowTemplateIdentity = false }: Props) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(skill, templateSkill, families, suggestedNumber));
  const [error, setError] = useState("");
  const [prerequisiteQuery, setPrerequisiteQuery] = useState("");
  const groupedFamilies = useMemo(() => {
    const groups = new Map<string, SkillFamily[]>();
    families.forEach((family) => {
      const group = family.group || "Generali";
      groups.set(group, [...(groups.get(group) || []), family]);
    });
    return [...groups.entries()];
  }, [families]);
  const update = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const visiblePrerequisites = useMemo(() => {
    const query = prerequisiteQuery.trim().toLocaleLowerCase("it");
    return skillOptions.filter((option) => option.id !== skill?.id && (!query || `${option.name} ${option.familyName}`.toLocaleLowerCase("it").includes(query))).slice(0, 80);
  }, [prerequisiteQuery, skill?.id, skillOptions]);
  const updatePassive = (index: number, changes: Partial<PassiveFeature>) => update("passiveEffects", draft.passiveEffects.map((feature, current) => current === index ? { ...feature, ...changes } : feature));
  const updateOperation = (passiveIndex: number, operationIndex: number, changes: Partial<PassiveFeature["operations"][number]>) => {
    const feature = draft.passiveEffects[passiveIndex];
    updatePassive(passiveIndex, { operations: feature.operations.map((operation, current) => current === operationIndex ? { ...operation, ...changes } : operation) });
  };
  const updateActive = (index: number, changes: Partial<ActiveReminder>) => update("activeReminders", draft.activeReminders.map((feature, current) => current === index ? { ...feature, ...changes } : feature));
  const togglePrerequisite = (id: number) => update("prerequisiteIds", draft.prerequisiteIds.includes(id) ? draft.prerequisiteIds.filter((entry) => entry !== id) : [...draft.prerequisiteIds, id]);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!allowTemplateIdentity && !skill && templateSkill && draft.name.trim().toLocaleLowerCase("it") === templateSkill.name.trim().toLocaleLowerCase("it")) {
      setError("Cambia il nome dell'abilità usata come esempio prima di salvarla.");
      return;
    }
    try {
      onSave({
        name: draft.name, slug: draft.slug, number: draft.number, familyId: draft.familyId, familyOrder: draft.familyOrder,
        magic: draft.magic, baseXpCost: draft.baseXpCost, xpType: draft.xpType,
        rulesCost: draft.rulesCost, description: draft.description,
        requirementsText: draft.requirementsText, prerequisiteIds: draft.prerequisiteIds,
        spell: draft.magic ? {
          tier: draft.spellTier, range: draft.spellRange, effectUnit: draft.spellEffectUnit,
          baseMana: draft.spellBaseMana, effectPerMana: draft.spellEffectPerMana,
          minimumMana: draft.spellMinimumMana, fixedCosts: draft.spellFixedCosts,
          rounding: draft.spellRounding,
          legacyFormula: draft.spellLegacyFormula, costNotes: draft.spellCostNotes,
          combatConfiguration: { prepared: true, spendsResources: false },
        } : null,
        profileTags: JSON.parse(draft.profileTags || "{}"), profileNotes: draft.profileNotes,
        passiveEffects: draft.passiveEffects, activeReminders: draft.activeReminders,
        icon: draft.icon, notes: draft.notes, metadata: JSON.parse(draft.metadata || "{}"),
      });
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? `JSON non valido: ${caught.message}` : "Controlla tag e metadati.");
    }
  };

  return <form className="skill-editor" onSubmit={submit} data-component-type="form" data-theme="parchment">
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="skill-editor-section">
      <header><span>01</span><div><h3>Identità e progressione</h3><p>Il nucleo consultabile e acquistabile dell'abilità.</p></div></header>
      <div className="skill-editor-grid">
        <label>Nome<input value={draft.name} maxLength={180} required onChange={(event) => update("name", event.target.value)} /></label>
        <label>Slug<input value={draft.slug} maxLength={180} placeholder="generato dal nome" onChange={(event) => update("slug", event.target.value)} /></label>
        <label>Numero<input type="number" min="1" value={draft.number} required onChange={(event) => update("number", event.target.value)} /></label>
        <label>Famiglia<select value={draft.familyId} onChange={(event) => update("familyId", event.target.value)}>{groupedFamilies.map(([group, groupFamilies]) => <optgroup key={group} label={group}>{groupFamilies.map((family) => <option key={family.id} value={family.id}>{family.name}</option>)}</optgroup>)}</select></label>
        <label>Ordine nella famiglia<input type="number" min="0" value={draft.familyOrder} onChange={(event) => update("familyOrder", event.target.value)} /></label>
        <label>Costo PE base<input type="number" min="0" value={draft.baseXpCost} onChange={(event) => update("baseXpCost", event.target.value)} /><small>Qui si modifica sempre il costo base; il rincaro del personaggio è calcolato soltanto nel catalogo e nello sblocco.</small></label>
        <label>Tipo PE<select value={draft.xpType} onChange={(event) => update("xpType", event.target.value)}><option value="all">Tutti</option><option value="general">Generali</option><option value="red">Rossi</option><option value="green">Verdi</option><option value="blue">Blu</option></select></label>
        <label className="check-field"><input type="checkbox" checked={draft.magic} onChange={(event) => update("magic", event.target.checked)} /> Abilità magica</label>
        <label>Icona<input value={draft.icon} maxLength={80} onChange={(event) => update("icon", event.target.value)} /></label>
        <label className="wide">Descrizione<textarea rows={6} value={draft.description} onChange={(event) => update("description", event.target.value)} /></label>
        <label className="wide">Costo regolamentare<input value={draft.rulesCost} maxLength={255} placeholder="Es. 4 Energia" onChange={(event) => update("rulesCost", event.target.value)} /></label>
        <label className="wide">Requisiti leggibili<textarea rows={3} value={draft.requirementsText} onChange={(event) => update("requirementsText", event.target.value)} /></label>
      </div>
      <div className="skill-prerequisite-picker"><label>Prerequisiti verificati<input type="search" value={prerequisiteQuery} placeholder="Cerca per nome o famiglia…" onChange={(event) => setPrerequisiteQuery(event.target.value)} /></label><div>{visiblePrerequisites.map((option) => <label key={option.id}><input type="checkbox" checked={draft.prerequisiteIds.includes(option.id)} onChange={() => togglePrerequisite(option.id)} /><span><strong>{option.name}</strong><small>{option.familyName}</small></span></label>)}</div></div>
    </section>

    <section className="skill-editor-section">
      <header><span>02</span><div><h3>Effetti passivi</h3><p>Vengono proposti e accettati esplicitamente durante lo sblocco.</p></div><button type="button" className="button secondary" onClick={() => update("passiveEffects", [...draft.passiveEffects, { id: `passivo-${Date.now()}`, name: "", description: "", icon: "runa", operations: [{ ...EMPTY_OPERATION }] }])}>Aggiungi passivo</button></header>
      <div className="skill-feature-editor-list">{draft.passiveEffects.map((feature, passiveIndex) => <article key={feature.id || passiveIndex} className="skill-feature-editor" data-component-type="card" data-theme="arcane"><header><strong>Passivo {passiveIndex + 1}</strong><button type="button" className="text-danger" onClick={() => update("passiveEffects", draft.passiveEffects.filter((_, index) => index !== passiveIndex))}>Rimuovi</button></header><div className="skill-editor-grid"><label>Nome<input value={feature.name} onChange={(event) => updatePassive(passiveIndex, { name: event.target.value })} /></label><label>Icona<select value={feature.icon} onChange={(event) => updatePassive(passiveIndex, { icon: event.target.value })}>{effectConfiguration.icons.map((icon) => <option key={icon.value} value={icon.value}>{icon.label}</option>)}</select></label><label className="wide">Descrizione<textarea rows={3} value={feature.description} onChange={(event) => updatePassive(passiveIndex, { description: event.target.value })} /></label></div><div className="skill-operation-list">{feature.operations.map((operation, operationIndex) => <div key={operationIndex} className="skill-operation-row"><label>Bersaglio<input list="skill-effect-targets" value={operation.target} onChange={(event) => updateOperation(passiveIndex, operationIndex, { target: event.target.value })} /></label><label>Operazione<select value={operation.operation} onChange={(event) => updateOperation(passiveIndex, operationIndex, { operation: event.target.value })}>{effectConfiguration.operations.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><label>Valore<input value={operation.value} onChange={(event) => updateOperation(passiveIndex, operationIndex, { value: event.target.value })} /></label><label>Condizione<input value={operation.condition} placeholder="facoltativa" onChange={(event) => updateOperation(passiveIndex, operationIndex, { condition: event.target.value })} /></label><button type="button" aria-label="Rimuovi modifica" onClick={() => updatePassive(passiveIndex, { operations: feature.operations.filter((_, index) => index !== operationIndex) })}>×</button></div>)}</div><button type="button" className="button secondary compact" onClick={() => updatePassive(passiveIndex, { operations: [...feature.operations, { ...EMPTY_OPERATION }] })}>Aggiungi modifica</button></article>)}</div>
      <datalist id="skill-effect-targets">{effectConfiguration.targets.map((target) => <option key={target.value} value={target.value}>{target.label}</option>)}</datalist>
    </section>

    <section className="skill-editor-section">
      <header><span>03</span><div><h3>Azioni attive e promemoria</h3><p>Diventano pulsanti consultabili; non eseguono automaticamente la regola.</p></div><button type="button" className="button secondary" onClick={() => update("activeReminders", [...draft.activeReminders, { id: `azione-${Date.now()}`, name: "", description: "", trigger: "", duration: "", usageNotes: "", costs: { ...EMPTY_COSTS }, icon: "runa" }])}>Aggiungi azione</button></header>
      <div className="skill-feature-editor-list">{draft.activeReminders.map((feature, activeIndex) => <article key={feature.id || activeIndex} className="skill-feature-editor" data-component-type="card" data-theme="gold"><header><strong>Azione {activeIndex + 1}</strong><button type="button" className="text-danger" onClick={() => update("activeReminders", draft.activeReminders.filter((_, index) => index !== activeIndex))}>Rimuovi</button></header><div className="skill-editor-grid"><label>Nome<input value={feature.name} onChange={(event) => updateActive(activeIndex, { name: event.target.value })} /></label><label>Icona<select value={feature.icon} onChange={(event) => updateActive(activeIndex, { icon: event.target.value })}>{effectConfiguration.icons.map((icon) => <option key={icon.value} value={icon.value}>{icon.label}</option>)}</select></label><label className="wide">Descrizione<textarea rows={4} value={feature.description} onChange={(event) => updateActive(activeIndex, { description: event.target.value })} /></label><label>Innesco<input value={feature.trigger} onChange={(event) => updateActive(activeIndex, { trigger: event.target.value })} /></label><label>Durata<input value={feature.duration} onChange={(event) => updateActive(activeIndex, { duration: event.target.value })} /></label><label className="wide">Note d'uso<textarea rows={2} value={feature.usageNotes} onChange={(event) => updateActive(activeIndex, { usageNotes: event.target.value })} /></label></div><div className="skill-cost-editor">{Object.keys(EMPTY_COSTS).map((key) => <label key={key}>{key === "pa" ? "PA" : key[0].toUpperCase() + key.slice(1)}<input type="number" min="0" value={feature.costs[key as keyof typeof EMPTY_COSTS] || 0} onChange={(event) => updateActive(activeIndex, { costs: { ...feature.costs, [key]: Number(event.target.value) || 0 } })} /></label>)}</div></article>)}</div>
    </section>

    {draft.magic && <section className="skill-editor-section spell-editor-section"><header><span>04</span><div><h3>Configuratore incantesimo</h3><p>Formula lineare sicura e leggibile, separata dagli effetti passivi e dalle azioni.</p></div></header><div className="skill-editor-grid"><label>Tier<select value={draft.spellTier} onChange={(event) => update("spellTier", event.target.value)}><option value="base">Base</option><option value="apprentice">Apprendista</option><option value="master">Maestro</option></select></label><label>Raggio<input value={draft.spellRange} onChange={(event) => update("spellRange", event.target.value)} /></label><label>Nome dell'effetto<input value={draft.spellEffectUnit} placeholder="Danno, metri, turni…" onChange={(event) => update("spellEffectUnit", event.target.value)} /></label><label>Mana fisso iniziale<input type="number" min="0" step="0.001" value={draft.spellBaseMana} onChange={(event) => update("spellBaseMana", event.target.value)} /><small>Lascia 0 per un incantesimo a solo costo variabile; metti 15 per un "15 Mana più tot per effetto". Entra nella conversione in Energia e PA.</small></label><label>Effetto prodotto da 1 Mana<input type="number" min="0.000001" step="0.000001" value={draft.spellEffectPerMana} onChange={(event) => update("spellEffectPerMana", event.target.value)} /><small>0,333… equivale a 3 Mana per effetto.</small></label><label>Mana minimo<input type="number" min="0" step="0.001" value={draft.spellMinimumMana} onChange={(event) => update("spellMinimumMana", event.target.value)} /></label><label>Arrotondamento dell'effetto<select value={draft.spellRounding} onChange={(event) => update("spellRounding", event.target.value)}><option value="none">Nessuno</option><option value="floor">Per difetto</option><option value="ceil">Per eccesso</option><option value="nearest">Al più vicino</option></select></label><aside className="spell-formula-preview"><strong>Formula configurata</strong><code>{draft.spellEffectUnit || "Effetto"} = max(0, (Mana - {draft.spellBaseMana || "0"}) × {draft.spellEffectPerMana || "0"})</code><small>Mana richiesto = {draft.spellBaseMana || "0"} fissi + {draft.spellEffectUnit || "Effetto"} ÷ {draft.spellEffectPerMana || "1"}. Il combattimento usa questa definizione, ma questa schermata non spende risorse.</small></aside><fieldset className="wide spell-fixed-costs"><legend>Costi fissi aggiuntivi per lancio</legend><div className="skill-cost-editor">{Object.keys(EMPTY_FIXED_SPELL_COSTS).map((key) => <label key={key}>{key === "pa" ? "PA" : key === "pf" ? "PF" : key[0].toUpperCase() + key.slice(1)}<input type="number" min="0" value={draft.spellFixedCosts[key as keyof typeof EMPTY_FIXED_SPELL_COSTS] || 0} onChange={(event) => update("spellFixedCosts", { ...draft.spellFixedCosts, [key]: Math.max(0, Number(event.target.value) || 0) })} /></label>)}</div><small>Si pagano a ogni lancio e si sommano ai costi convertiti dal Mana, senza essere riconvertiti.</small></fieldset><label className="wide">Formula Elder originale<input value={draft.spellLegacyFormula} placeholder="Solo provenienza e confronto" onChange={(event) => update("spellLegacyFormula", event.target.value)} /></label><label className="wide">Note sui costi<textarea rows={3} value={draft.spellCostNotes} onChange={(event) => update("spellCostNotes", event.target.value)} /></label></div></section>}

    <section className="skill-editor-section"><header><span>{draft.magic ? "05" : "04"}</span><div><h3>Profilo e metadati</h3><p>Dati di supporto, ricerca e revisione.</p></div></header><div className="skill-editor-grid"><label className="wide">Tag profilo JSON<textarea className="code-input" rows={7} value={draft.profileTags} onChange={(event) => update("profileTags", event.target.value)} /></label><label className="wide">Note profilo<textarea rows={3} value={draft.profileNotes} onChange={(event) => update("profileNotes", event.target.value)} /></label><label className="wide">Note interne<textarea rows={3} value={draft.notes} onChange={(event) => update("notes", event.target.value)} /></label><label className="wide">Metadati JSON<textarea className="code-input" rows={6} value={draft.metadata} onChange={(event) => update("metadata", event.target.value)} /></label></div></section>
    <div className="skill-editor-actions"><button type="button" className="button secondary" onClick={onCancel}>Annulla</button>{onDelete && <button type="button" className="button danger" onClick={onDelete}>Elimina definitivamente</button>}{onArchive && <button type="button" className="button danger" onClick={onArchive}>Archivia</button>}<button className="button primary" disabled={saving || !draft.name.trim() || !draft.number || !draft.familyId || Boolean(!allowTemplateIdentity && !skill && templateSkill && draft.name.trim().toLocaleLowerCase("it") === templateSkill.name.trim().toLocaleLowerCase("it"))}>{submitLabel || (skill ? "Salva abilità" : "Crea abilità")}</button></div>
  </form>;
}
