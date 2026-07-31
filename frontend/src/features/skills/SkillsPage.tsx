import { type CSSProperties, useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { closestCenter, DndContext, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Modal } from "../../components/Modal";
import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type { SkillUnlockPreview } from "../../lib/types";
import { SkillEditor } from "./SkillEditor";
import { ACTIVE_COST_LABELS, costsLabel, type ActiveReminder, type CombatButton, type CombatButtonModifiers, type UnifiedSkill, type UnifiedSkillCatalog, XP_LABELS } from "./types";

type SkillActionData = {
  skill?: UnifiedSkill | null;
  skills?: UnifiedSkillCatalog | null;
  skillPreview?: UnifiedUnlockPreview | null;
  spellPreview?: SpellCastPreview | null;
  character?: unknown;
};
type SpellCastPreview = {
  requestedEffect: number;
  projectedEffect: number;
  effectUnit: string;
  requiredManaBeforeDiscounts: number;
  powerConsidered: number;
  resourceOptions: { mana: number; energy: number | null; actionPoints: number | null };
  note: string;
};
type UnifiedUnlockPreview = Omit<SkillUnlockPreview, "skill"> & { skill: UnifiedSkill };
type DetailTab = "details" | "spell" | "passives" | "actions" | "metadata" | "edit";
type CharacterSection = "unlocked" | "analysis" | "combat-buttons";
type SkillSearchStatus = "all" | "owned" | "available" | "locked";

const CHARACTER_GROUP = "__character__";
const SEARCH_GROUP = "__search__";

function operationLabel(operation: { target: string; operation: string; value: string; condition?: string }): string {
  const verbs: Record<string, string> = { add: "+", subtract: "−", multiply: "×", percent: "%", min: "min", max: "max", cap: "limite", set: "=", strong_set: "= forte", formula_override: "formula" };
  return `${operation.target} ${verbs[operation.operation] || operation.operation} ${operation.value}${operation.condition ? ` · se ${operation.condition}` : ""}`;
}

function ReminderModal({ reminder, onClose }: { reminder: ActiveReminder; onClose: () => void }) {
  return <Modal surface="skills-reminder" title={reminder.name} onClose={onClose} footer={<button className="button primary" onClick={onClose}>Ho letto</button>}>
    <article className="skill-reminder-sheet" data-component-type="card" data-theme="gold">
      <p className="eyebrow">{reminder.familyName || "Azione attiva"}{reminder.skillName ? ` · ${reminder.skillName}` : ""}</p>
      <p className="skill-reminder-cost">{costsLabel(reminder.costs)}</p>
      {reminder.trigger && <dl><div><dt>Quando</dt><dd>{reminder.trigger}</dd></div>{reminder.duration && <div><dt>Durata</dt><dd>{reminder.duration}</dd></div>}</dl>}
      <p>{reminder.description}</p>
      {reminder.usageNotes && <aside><strong>Promemoria</strong><p>{reminder.usageNotes}</p></aside>}
      <small>Questo pulsante ricorda la regola e non esegue automaticamente costi o conseguenze.</small>
    </article>
  </Modal>;
}

function SpellCalculator({ skill, characterId }: { skill: UnifiedSkill; characterId: number | null }) {
  const [effect, setEffect] = useState(1);
  const [power, setPower] = useState(0);
  const preview = useMutation({
    mutationFn: () => command<SkillActionData>("skills.previewSpell", { characterId, skillId: skill.id, effect, power }, "skills-spell"),
  });
  const result = preview.data?.data.spellPreview || null;
  if (!skill.spell) return null;
  return <section className="spell-calculator" data-spell-tier={skill.spell.tier}>
    <header><div><p className="eyebrow">Anteprima senza spesa</p><h3>Calcola l'incantesimo</h3></div><span>{skill.spell.tierLabel}</span></header>
    <p>{skill.spell.formula}</p>
    <div className="spell-calculator-inputs"><label>{skill.spell.effectUnit} desiderato<input type="number" min="0" step="0.01" value={effect} onChange={(event) => setEffect(Math.max(0, Number(event.target.value) || 0))} /></label><label>Potere ipotizzato<input type="number" min="0" step="1" value={power} onChange={(event) => setPower(Math.max(0, Number(event.target.value) || 0))} /></label><button className="button primary" disabled={!characterId || preview.isPending} onClick={() => preview.mutate()}>{preview.isPending ? "Calcolo…" : "Calcola costi"}</button></div>
    {preview.error && <p className="form-error">{(preview.error as Error).message}</p>}
    {result && <div className="spell-resource-options"><article><small>Mana</small><strong>{result.resourceOptions.mana}</strong></article><article><small>Energia</small><strong>{result.resourceOptions.energy ?? "—"}</strong></article><article><small>PA</small><strong>{result.resourceOptions.actionPoints ?? "—"}</strong></article><article><small>{result.effectUnit} risultante</small><strong>{result.projectedEffect}</strong></article><p>{result.note}</p></div>}
    <aside><strong>Predisposto per il combattimento</strong><p>Le tre voci si pagano insieme come nel regolamento originario: Energia e PA nascono dal Mana richiesto prima degli sconti, il Potere riduce Mana e PA. Qui nulla viene speso.</p></aside>
  </section>;
}

function UnlockModal({ preview, loading, saving, error, onClose, onConfirm, onRemove }: {
  preview: UnifiedUnlockPreview | null;
  loading: boolean;
  saving: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (spend: Record<string, number>, acceptedPassiveIds: string[], note: string) => void;
  onRemove: () => void;
}) {
  const [spend, setSpend] = useState<Record<string, number>>({ general: 0, red: 0, green: 0, blue: 0 });
  const [accepted, setAccepted] = useState<string[]>([]);
  const [note, setNote] = useState("");
  useEffect(() => {
    if (preview) {
      setSpend({ general: 0, red: 0, green: 0, blue: 0, ...(preview.skill.unlock.spentXp || {}) });
      setAccepted(preview.skill.unlock.acceptedPassiveIds || []);
      setNote(preview.skill.unlock.note || "");
    }
  }, [preview]);
  const total = Object.values(spend).reduce((sum, value) => sum + Number(value || 0), 0);
  const requiredPassiveIds = preview?.passiveConfirmations.map((passive) => String(passive.id)) || [];
  const allAccepted = requiredPassiveIds.every((id) => accepted.includes(id));
  const hasUnlockReason = total > 0 || note.trim().length > 0;
  return <Modal surface="skills-unlock" title={preview ? `Sblocco · ${preview.skill.name}` : "Preparazione dello sblocco"} onClose={onClose} wide footer={preview && <>{preview.skill.unlock.owned && <button className="button danger" disabled={saving} onClick={onRemove}>Rimuovi sblocco</button>}<button className="button secondary" disabled={saving} onClick={onClose}>Annulla</button><button className="button primary" disabled={saving || (!preview.skill.unlock.owned && !hasUnlockReason) || !allAccepted} onClick={() => onConfirm(spend, accepted, note)}>{preview.skill.unlock.owned ? "Salva sblocco" : "Sblocca abilità"}</button></>}>
    {loading && <div className="skill-unlock-loading"><span>✦</span><p>Verifica di prerequisiti e PE…</p></div>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {preview && <div className="skill-unlock-preview">
      <section><p className="eyebrow">Costo suggerito per il personaggio</p><h3>{preview.cost} PE · {preview.skill.xpTypeLabel}</h3><p>Puoi registrare qualsiasi spesa positiva, anche inferiore al costo suggerito, oppure lasciare soltanto una nota per un'abilità regalata o scontata.</p></section>
      {preview.blockedReasons.length > 0 && <aside className="skill-blocked-reasons"><strong>Avvertenze</strong><ul>{preview.blockedReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></aside>}
      <section><h3>Distribuisci i PE</h3><div className="skill-spend-grid">{Object.entries(XP_LABELS).map(([key, label]) => {
        const allowed = preview.allowedXpPools.includes(key);
        const refundable = Number(preview.skill.unlock.spentXp?.[key] || 0);
        return <label key={key} data-xp={key} data-state={allowed ? "allowed" : "blocked"}><span>{label}<small>{preview.xp[key] || 0} disponibili{refundable ? ` · ${refundable} recuperabili` : ""}</small></span><input type="number" min="0" max={(preview.xp[key] || 0) + refundable} value={spend[key] || 0} disabled={!allowed} onChange={(event) => setSpend((current) => ({ ...current, [key]: Math.max(0, Math.floor(Number(event.target.value) || 0)) }))} /></label>;
      })}</div><div className="skill-spend-total" data-state={hasUnlockReason ? "valid" : "invalid"}><span>PE spesi</span><strong>{total}</strong></div><label className="skill-unlock-note">Nota sullo sblocco<textarea rows={4} maxLength={4000} value={note} placeholder="Esempio: Insegnato da Master Kahar" onChange={(event) => setNote(event.target.value)} /></label></section>
      {preview.passiveConfirmations.length > 0 && <section><h3>Accetta gli effetti passivi</h3><p>Ogni effetto diventerà parte della scheda e dei suoi calcoli.</p><div className="skill-passive-confirmations">{preview.passiveConfirmations.map((passive) => <label key={String(passive.id)}><input type="checkbox" checked={accepted.includes(String(passive.id))} onChange={(event) => setAccepted((current) => event.target.checked ? [...current, String(passive.id)] : current.filter((id) => id !== String(passive.id)))} /><span><strong>{String(passive.name)}</strong><p>{String(passive.description)}</p><small>{Array.isArray(passive.operations) ? passive.operations.map((operation) => operationLabel(operation as never)).join(" · ") : ""}</small></span></label>)}</div></section>}
      {preview.skill.activeReminders.length > 0 && <section className="skill-grant-note"><strong>{preview.skill.activeReminders.length} azioni-promemoria</strong><p>I relativi pulsanti appariranno nel grimorio dopo lo sblocco.</p></section>}
    </div>}
  </Modal>;
}

function SkillDetailModal({ skill, catalog, saving, onClose, onUnlock, onSave, onArchive, onDelete }: {
  skill: UnifiedSkill;
  catalog: UnifiedSkillCatalog;
  saving: boolean;
  onClose: () => void;
  onUnlock: () => void;
  onSave: (values: Record<string, unknown>) => void;
  onArchive: () => void;
  onDelete?: () => void;
}) {
  const [tab, setTab] = useState<DetailTab>("details");
  const prerequisiteNames = skill.unlock.prerequisiteIds.map((id) => catalog.skillOptions.find((option) => option.id === id)?.name).filter(Boolean);
  const pricingModifier = skill.metadata?.pricingModifier && typeof skill.metadata.pricingModifier === "object" ? skill.metadata.pricingModifier as Record<string, unknown> : null;
  const managedDiscountTypes = Array.isArray(pricingModifier?.xpTypes) ? pricingModifier.xpTypes.map((value) => XP_LABELS[String(value)] || String(value)).join(", ") : "";
  const tabs: Array<[DetailTab, string, number?]> = [["details", "Dettagli"]];
  if (skill.spell) tabs.push(["spell", "Incantesimo"]);
  tabs.push(["passives", "Passivi", skill.passiveEffects.length], ["actions", "Azioni", skill.activeReminders.length], ["metadata", "Profilo"]);
  if (catalog.permissions.canManageSkills) tabs.push(["edit", "Modifica"]);
  return <Modal surface="skills-detail" title={skill.name} onClose={onClose} wide footer={tab !== "edit" && <><span className="skill-detail-status">{skill.unlock.owned ? "Abilità posseduta" : `${skill.xpCost} PE ${skill.xpTypeLabel}`}</span><button className="button primary" onClick={onUnlock}>{skill.unlock.owned ? "Già sbloccata" : "Sblocca abilità"}</button></>}>
    <article className="skill-detail-card" data-component-type="card" data-theme={skill.magic ? "arcane" : "parchment"} data-spell-tier={skill.spell?.tier || "none"}>
      <header className="skill-detail-heading"><div><p className="eyebrow">{skill.familyGroup} · {skill.familyName} · #{skill.number}</p><p>{skill.description || "Nessuna descrizione disponibile."}</p></div><div className="skill-seal" aria-hidden="true">{skill.magic ? "✧" : "✦"}</div></header>
      <nav className="skill-card-tabs" data-component-type="tabset" data-theme="gold" aria-label="Sezioni dell'abilità">{tabs.map(([id, label, count]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}{count !== undefined && <span>{count}</span>}</button>)}</nav>
      {tab === "details" && <section className="skill-tab-panel"><div className="skill-prose"><h3>Descrizione</h3><p>{skill.description || "Nessuna descrizione."}</p>{skill.rulesCost && <aside><strong>Costo d'uso</strong><p>{skill.rulesCost}</p></aside>}{skill.requirementsText && <aside><strong>Requisiti descrittivi</strong><p>{skill.requirementsText}</p></aside>}{pricingModifier && <aside><strong>Regola automatica del sistema</strong><p>Quando questa skill è sbloccata, il sistema sottrae {String(pricingModifier.amount || 0)} PE alle skill {managedDiscountTypes} con costo base di almeno {String(pricingModifier.minimumBaseCost || 0)} PE. Se la skill viene rimossa, lo sconto scompare e i prezzi tornano normali.</p></aside>}</div><dl className="skill-facts"><div><dt>Costo</dt><dd>{skill.xpCost} PE {skill.xpTypeLabel}</dd></div>{skill.pricing.ownedSkillDiscount > 0 && <div><dt>Sconto automatico</dt><dd>-{skill.pricing.ownedSkillDiscount} PE · {skill.pricing.ownedSkillDiscountSources.join(", ")}<small>Rimuovendo la skill che concede lo sconto, questo prezzo torna a {skill.pricing.calculatedBeforeOwnedSkillDiscount} PE.</small></dd></div>}<div><dt>Prerequisiti verificati</dt><dd>{prerequisiteNames.join(", ") || "Nessuno"}</dd></div>{skill.spell && <><div><dt>Tier magico</dt><dd>{skill.spell.tierLabel}</dd></div><div><dt>Raggio</dt><dd>{skill.spell.range || "—"}</dd></div></>}</dl>{skill.unlock.blockedReasons.length > 0 && !skill.unlock.owned && <aside className="skill-blocked-reasons"><strong>Avvertenze</strong><ul>{skill.unlock.blockedReasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></aside>}</section>}
      {tab === "spell" && skill.spell && <section className="skill-tab-panel"><SpellCalculator skill={skill} characterId={catalog.character?.id || null} /></section>}
      {tab === "passives" && <section className="skill-tab-panel skill-feature-list">{skill.passiveEffects.length ? skill.passiveEffects.map((passive) => <article key={passive.id} data-component-type="card" data-theme="arcane"><header><span aria-hidden="true">✧</span><div><h3>{passive.name}</h3><small>{skill.unlock.acceptedPassiveIds.includes(passive.id) ? "Accettato e applicato" : "Proposto allo sblocco"}</small></div></header><p>{passive.description}</p><ul>{passive.operations.map((operation, index) => <li key={index}>{operationLabel(operation)}</li>)}</ul></article>) : <div className="skill-empty-tab"><span>◇</span><p>Questa abilità non concede effetti passivi.</p></div>}</section>}
      {tab === "actions" && <section className="skill-tab-panel skill-feature-list">{skill.activeReminders.length ? skill.activeReminders.map((action) => <article key={action.id} data-component-type="card" data-theme="gold"><header><span aria-hidden="true">✦</span><div><h3>{action.name}</h3><small>{costsLabel(action.costs)}</small></div></header><p>{action.description}</p><dl><div><dt>Innesco</dt><dd>{action.trigger || "Uso dichiarato dal giocatore"}</dd></div><div><dt>Durata</dt><dd>{action.duration || "Istantanea"}</dd></div></dl>{action.usageNotes && <aside>{action.usageNotes}</aside>}</article>) : <div className="skill-empty-tab"><span>◇</span><p>Questa abilità non concede azioni-promemoria.</p></div>}</section>}
      {tab === "metadata" && <section className="skill-tab-panel"><h3>Profilo e classificazione</h3><div className="skill-tag-cloud">{Object.entries(skill.profileTags || {}).map(([key, value]) => <span key={key}><strong>{key}</strong>{Array.isArray(value) ? value.join(", ") : String(value)}</span>)}</div>{skill.profileNotes && <p>{skill.profileNotes}</p>}{skill.notes && catalog.permissions.canManageSkills && <aside><strong>Note interne</strong><p>{skill.notes}</p></aside>}</section>}
      {tab === "edit" && <section className="skill-tab-panel skill-edit-tab"><SkillEditor key={skill.id} skill={skill} families={catalog.families} skillOptions={catalog.skillOptions} effectConfiguration={catalog.effectConfiguration} saving={saving} onCancel={() => setTab("details")} onSave={onSave} onArchive={onArchive} onDelete={onDelete} /></section>}
    </article>
  </Modal>;
}

function CharacterActionsTab({ catalog, saving, onSave, onRead }: {
  catalog: UnifiedSkillCatalog;
  saving: boolean;
  onSave: (actions: ActiveReminder[]) => void;
  onRead: (action: ActiveReminder) => void;
}) {
  const [actions, setActions] = useState<ActiveReminder[]>(() => catalog.activeReminders.map((action, index) => ({ ...action, enabled: action.enabled !== false, order: action.order ?? index, characterNote: action.characterNote || "" })));
  useEffect(() => {
    setActions(catalog.activeReminders.map((action, index) => ({ ...action, enabled: action.enabled !== false, order: action.order ?? index, characterNote: action.characterNote || "" })));
  }, [catalog.activeReminders]);
  const updateAction = (index: number, changes: Partial<ActiveReminder>) => setActions((current) => current.map((action, currentIndex) => currentIndex === index ? { ...action, ...changes } : action));
  const moveAction = (index: number, direction: -1 | 1) => setActions((current) => {
    const destination = index + direction;
    if (destination < 0 || destination >= current.length) return current;
    const reordered = [...current];
    [reordered[index], reordered[destination]] = [reordered[destination], reordered[index]];
    return reordered.map((action, order) => ({ ...action, order }));
  });
  return <section className="skill-character-actions" data-component-type="panel" data-theme="parchment">
    <header><div><p className="eyebrow">Barra personale</p><h2>Azioni del personaggio</h2><p>Scegli quali promemoria mostrare, il loro ordine e una nota personale. Nessuna azione esegue automaticamente costi o conseguenze.</p></div><div className="skill-action-summary"><strong>{actions.filter((action) => action.enabled !== false).length}</strong><small>visibili su {actions.length}</small></div></header>
    {actions.length > 0 ? <div className="skill-character-action-list">{actions.map((action, index) => <article key={`${action.skillId}-${action.id}`} data-component-type="card" data-theme="gold" data-state={action.enabled === false ? "disabled" : "enabled"}>
      <div className="skill-character-action-order"><button type="button" aria-label={`Sposta ${action.name} su`} disabled={index === 0} onClick={() => moveAction(index, -1)}>↑</button><span>{index + 1}</span><button type="button" aria-label={`Sposta ${action.name} giù`} disabled={index === actions.length - 1} onClick={() => moveAction(index, 1)}>↓</button></div>
      <div className="skill-character-action-copy"><p className="eyebrow">{action.familyGroup} · {action.familyName}</p><h3>{action.name}</h3><small>{action.skillName} · {costsLabel(action.costs)}</small><p>{action.description}</p><button type="button" className="button secondary compact" onClick={() => onRead(action)}>Leggi la regola</button></div>
      <div className="skill-character-action-config"><label className="skill-action-enabled"><input type="checkbox" checked={action.enabled !== false} onChange={(event) => updateAction(index, { enabled: event.target.checked })} /> Mostra tra le azioni del PG</label><label>Nota personale<textarea rows={3} maxLength={1000} value={action.characterNote || ""} placeholder="Quando ricordarla, variante del tavolo…" onChange={(event) => updateAction(index, { characterNote: event.target.value })} /></label></div>
    </article>)}</div> : <div className="skill-empty-catalog"><span>◇</span><h3>Nessuna azione disponibile</h3><p>Le azioni definite nelle skill appariranno qui dopo lo sblocco.</p></div>}
    <footer><button type="button" className="button primary" disabled={saving || !actions.length} onClick={() => onSave(actions)}>{saving ? "Salvataggio…" : "Salva configurazione azioni"}</button></footer>
  </section>;
}

function SkillAnalysisTab({ catalog }: { catalog: UnifiedSkillCatalog }) {
  const analysis = catalog.characterAnalysis;
  return <section className="skill-analysis" data-component-type="panel" data-theme="parchment">
    <header><p className="eyebrow">Lettura del personaggio</p><h2>Analisi Skill PG</h2><p>Una sintesi delle skill realmente possedute da {catalog.character?.name || "questo personaggio"}.</p></header>
    <div className="skill-analysis-summary"><article><small>Skill possedute</small><strong>{analysis.ownedSkills}</strong></article><article><small>Effetti passivi</small><strong>{analysis.passiveEffects}</strong></article><article><small>Azioni disponibili</small><strong>{analysis.activeActions}</strong></article><article><small>PE registrati</small><strong>{analysis.xpSpent}</strong></article></div>
    <div className="skill-analysis-columns"><section><h3>Distribuzione per gruppo</h3>{analysis.byGroup.length ? <div className="skill-analysis-bars">{analysis.byGroup.map((row) => <article key={row.group}><header><strong>{row.group}</strong><span>{row.skills} skill</span></header><div><span style={{ width: `${Math.max(8, analysis.ownedSkills ? row.skills / analysis.ownedSkills * 100 : 0)}%` }} /></div><small>{row.passives} passivi · {row.actions} azioni</small></article>)}</div> : <p className="muted-copy">Nessuna skill posseduta da analizzare.</p>}</section><section><h3>Famiglie conosciute</h3>{analysis.byFamily.length ? <ul className="skill-analysis-families">{analysis.byFamily.map((row) => <li key={`${row.group}-${row.family}`}><span><small>{row.group}</small><strong>{row.family}</strong></span><b>{row.skills}</b></li>)}</ul> : <p className="muted-copy">Le famiglie compariranno dopo il primo sblocco.</p>}</section></div>
  </section>;
}

function ReorderableSkillCard({ skill, canReorder, onOpen }: { skill: UnifiedSkill; canReorder: boolean; onOpen: (skillId: number) => void }) {
  const draggable = useDraggable({ id: skill.id, disabled: !canReorder });
  const droppable = useDroppable({ id: skill.id, disabled: !canReorder });
  const setCardRef = useCallback((node: HTMLElement | null) => {
    draggable.setNodeRef(node);
    droppable.setNodeRef(node);
  }, [draggable.setNodeRef, droppable.setNodeRef]);
  const style = draggable.transform ? { transform: `translate3d(${draggable.transform.x}px, ${draggable.transform.y}px, 0)` } : undefined;
  return <article
    ref={setCardRef}
    style={style}
    className="skill-card"
    data-component-type="card"
    data-theme={skill.magic ? "arcane" : "parchment"}
    data-spell-tier={skill.spell?.tier || "none"}
    data-state={skill.archived ? "archived" : skill.unlock.owned ? "owned" : skill.unlock.canUnlock ? "available" : "locked"}
    data-dragging={draggable.isDragging ? "true" : "false"}
    data-drag-over={droppable.isOver ? "true" : "false"}
    role="button"
    tabIndex={0}
    aria-label={`Apri ${skill.name}`}
    onClick={() => onOpen(skill.id)}
    onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); onOpen(skill.id); } }}
  ><header><div><p>{skill.familyName}</p><h3>{skill.name}</h3></div><div className="skill-card-tools"><span className="skill-owned-mark" aria-label={skill.unlock.owned ? "Posseduta" : "Non posseduta"}>{skill.unlock.owned ? "◆" : "◇"}</span>{canReorder && <button ref={draggable.setActivatorNodeRef} type="button" className="skill-drag-handle" title={`Trascina ${skill.name} per cambiarne l'ordine`} aria-label={`Riordina ${skill.name}`} onClick={(event) => event.stopPropagation()} {...draggable.listeners} {...draggable.attributes}>⠿</button>}</div></header><p>{skill.description || "Nessuna descrizione disponibile."}</p><div className="skill-card-badges"><span>{skill.xpCost} PE {skill.xpTypeLabel}</span>{skill.spell && <span>Magia {skill.spell.tierLabel}</span>}</div><footer><small>{skill.unlock.owned ? "Nel grimorio" : skill.unlock.canUnlock ? "Sbloccabile ora" : skill.unlock.blockedReasons[0] || "Non disponibile"}</small></footer></article>;
}

function SkillCardGrid({ skills, canReorder, onOpen, onReorder }: { skills: UnifiedSkill[]; canReorder: boolean; onOpen: (skillId: number) => void; onReorder: (skillIds: number[]) => void }) {
  const [orderedSkills, setOrderedSkills] = useState(skills);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor));
  useEffect(() => setOrderedSkills(skills), [skills]);
  const dragEnd = (event: DragEndEvent) => {
    if (!canReorder || !event.over || event.active.id === event.over.id) return;
    const sourceIndex = orderedSkills.findIndex((skill) => skill.id === Number(event.active.id));
    const targetIndex = orderedSkills.findIndex((skill) => skill.id === Number(event.over?.id));
    if (sourceIndex < 0 || targetIndex < 0) return;
    const reordered = [...orderedSkills];
    const [moved] = reordered.splice(sourceIndex, 1);
    reordered.splice(targetIndex, 0, moved);
    setOrderedSkills(reordered);
    onReorder(reordered.map((skill) => skill.id));
  };
  return <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={dragEnd}>
    <section className="skill-card-grid" data-component-type="grid" data-theme="parchment">{orderedSkills.map((skill) => <ReorderableSkillCard key={skill.id} skill={skill} canReorder={canReorder} onOpen={onOpen} />)}</section>
  </DndContext>;
}

function SkillSearchWorkspace({ catalog, onOpen }: { catalog: UnifiedSkillCatalog; onOpen: (skill: UnifiedSkill) => void }) {
  const [nameQuery, setNameQuery] = useState("");
  const [cardQuery, setCardQuery] = useState("");
  const [group, setGroup] = useState("");
  const [familyId, setFamilyId] = useState("");
  const [effectTarget, setEffectTarget] = useState("");
  const [status, setStatus] = useState<SkillSearchStatus>("all");
  const [includeArchived, setIncludeArchived] = useState(false);
  const deferredName = useDeferredValue(nameQuery.trim());
  const deferredCard = useDeferredValue(cardQuery.trim());
  const availableFamilies = catalog.families.filter((family) => !group || family.group === group);
  const hasCriteria = Boolean(deferredName || deferredCard || group || familyId || effectTarget || status !== "all");
  const searchParams = new URLSearchParams({ search_mode: "true" });
  if (catalog.character?.id) searchParams.set("character_id", String(catalog.character.id));
  if (deferredName) searchParams.set("name_query", deferredName);
  if (deferredCard) searchParams.set("card_query", deferredCard);
  if (group) searchParams.set("filter_group", group);
  if (familyId) searchParams.set("filter_family_id", familyId);
  if (effectTarget) searchParams.set("effect_target", effectTarget);
  if (status !== "all") searchParams.set("unlock_status", status);
  if (includeArchived) searchParams.set("include_archived", "true");
  const searchQuery = useQuery({
    queryKey: ["skill-search", catalog.character?.id, deferredName, deferredCard, group, familyId, effectTarget, status, includeArchived],
    queryFn: () => getData<UnifiedSkillCatalog>(`/api/v1/skills?${searchParams}`),
    enabled: hasCriteria,
  });
  const filteredSkills = searchQuery.data?.skills || [];
  const reset = () => {
    setNameQuery("");
    setCardQuery("");
    setGroup("");
    setFamilyId("");
    setEffectTarget("");
    setStatus("all");
    setIncludeArchived(false);
  };

  return <section className="skill-search-workspace" data-component-type="panel" data-theme="parchment">
    <header><div><p className="eyebrow">Ricerca nel grimorio</p><h2>Cerca Abilità</h2><p>I risultati arrivano da tutti i gruppi e tutte le famiglie.</p></div><button type="button" className="button secondary" onClick={reset}>Azzera filtri</button></header>
    <div className="skill-search-primary">
      <label>Nome dell'abilità<input type="search" value={nameQuery} placeholder="Es. Maestria del corpo" onChange={(event) => setNameQuery(event.target.value)} /></label>
      <label>Qualsiasi testo nella carta<input type="search" value={cardQuery} placeholder="Descrizione, requisito, effetto, costo…" onChange={(event) => setCardQuery(event.target.value)} /></label>
    </div>
    <details className="skill-search-advanced">
      <summary>Ricerca avanzata <span>Gruppo, famiglia, stato e variabili modificate</span></summary>
      <div>
        <label>Gruppo<select value={group} onChange={(event) => { setGroup(event.target.value); setFamilyId(""); }}><option value="">Tutti i gruppi</option>{catalog.groups.map((entry) => <option key={entry.key} value={entry.name}>{entry.name}</option>)}</select></label>
        <label>Famiglia<select value={familyId} onChange={(event) => setFamilyId(event.target.value)}><option value="">Tutte le famiglie</option>{availableFamilies.map((family) => <option key={family.id} value={family.id}>{family.name}</option>)}</select></label>
        <label>Stato<select value={status} onChange={(event) => setStatus(event.target.value as SkillSearchStatus)}><option value="all">Qualsiasi stato</option><option value="owned">Possedute</option><option value="available">Sbloccabili ora</option><option value="locked">Non disponibili</option></select></label>
        <label>Variabile modificata<select value={effectTarget} onChange={(event) => setEffectTarget(event.target.value)}><option value="">Qualsiasi variabile</option>{catalog.effectConfiguration.targets.map((target) => <option key={target.value} value={target.value}>{target.label}</option>)}</select></label>
        {catalog.permissions.canManageSkills && <label className="archive-toggle"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /> Includi archiviate</label>}
      </div>
    </details>
    <div className="skill-search-results-heading"><strong>{searchQuery.isFetching ? "Ricerca…" : `${filteredSkills.length} risultati`}</strong><span>Apri una carta per leggerla, sbloccarla o modificarla normalmente.</span></div>
    {searchQuery.error && <p className="form-error">{(searchQuery.error as Error).message}</p>}
    <SkillCardGrid skills={filteredSkills} canReorder={false} onOpen={(skillId) => { const skill = filteredSkills.find((entry) => entry.id === skillId); if (skill) onOpen(skill); }} onReorder={() => undefined} />
    {!searchQuery.isFetching && !filteredSkills.length && <div className="skill-empty-catalog"><span>✧</span><h3>{hasCriteria ? "Nessuna abilità corrisponde ai filtri" : "Inizia la ricerca"}</h3><p>{hasCriteria ? "Prova ad ampliare la ricerca o ad azzerare i filtri." : "Inserisci un nome, del testo o apri la ricerca avanzata."}</p></div>}
  </section>;
}

function SkillCreationModal({ catalog, characterId, saving, onClose, onSave }: { catalog: UnifiedSkillCatalog; characterId: number | null; saving: boolean; onClose: () => void; onSave: (values: Record<string, unknown>) => void }) {
  const [exampleId, setExampleId] = useState<number | null>(null);
  const option = catalog.skillOptions.find((entry) => entry.id === exampleId) || null;
  const localExample = catalog.skills.find((entry) => entry.id === exampleId) || null;
  const exampleQuery = useQuery({
    queryKey: ["skill-example", characterId, exampleId],
    queryFn: () => {
      const params = new URLSearchParams();
      if (characterId) params.set("character_id", String(characterId));
      params.set("query", option?.name || "");
      return getData<UnifiedSkillCatalog>(`/api/v1/skills?${params}`);
    },
    enabled: Boolean(exampleId && option && !localExample),
  });
  const template = localExample || exampleQuery.data?.skills.find((entry) => entry.id === exampleId) || null;
  const suggestedNumber = Math.max(0, ...catalog.skillOptions.map((entry) => entry.number || 0)) + 1;
  const editorReady = !exampleId || Boolean(template);
  return <Modal surface="skills-create" title="Crea abilità" onClose={onClose} wide>
    <section className="skill-example-picker" data-component-type="field" data-theme="gold">
      <label>Usa un'abilità come esempio<select value={exampleId || ""} onChange={(event) => setExampleId(event.target.value ? Number(event.target.value) : null)}><option value="">Inizia da zero</option>{catalog.skillOptions.map((entry) => <option key={entry.id} value={entry.id}>{entry.familyName} · {entry.name}</option>)}</select></label>
      <p>I contenuti dell'esempio vengono copiati. Per creare la nuova abilità devi cambiarne il nome; slug e numero ricevono una nuova identità.</p>
    </section>
    {exampleQuery.isLoading && <p className="skill-example-status">Caricamento dell'esempio…</p>}
    {exampleQuery.error && <p className="form-error">{(exampleQuery.error as Error).message}</p>}
    {editorReady && <SkillEditor key={template?.id || "blank"} skill={null} templateSkill={template} suggestedNumber={suggestedNumber} families={catalog.families} skillOptions={catalog.skillOptions} effectConfiguration={catalog.effectConfiguration} saving={saving} onCancel={onClose} onSave={onSave} />}
  </Modal>;
}

function XpEditorModal({ catalog, saving, onClose, onSave }: {
  catalog: UnifiedSkillCatalog;
  saving: boolean;
  onClose: () => void;
  onSave: (xp: Record<string, number>) => void;
}) {
  const character = catalog.character;
  const [values, setValues] = useState<Record<string, number>>({ general: 0, red: 0, green: 0, blue: 0, ability: 0 });
  useEffect(() => {
    if (!character) return;
    setValues({ ...character.xp, ability: character.competenceXp || 0 });
  }, [character]);
  if (!character) return null;
  const labels = { ...XP_LABELS, ability: "Competenze" };
  return <Modal surface="skills-xp" title="Modifica Punti Esperienza" onClose={onClose} footer={<><button className="button secondary" disabled={saving} onClick={onClose}>Annulla</button><button className="button primary" disabled={saving} onClick={() => onSave(values)}>{saving ? "Salvataggio…" : "Salva PE disponibili"}</button></>}>
    <div className="skill-xp-editor"><p>Imposta i Punti Esperienza attualmente disponibili per le skill e per le Competenze.</p>{Object.entries(labels).map(([key, label]) => <label key={key} data-xp={key}><span>{label}<small>{key === "ability" ? "PE Competenze" : "PE Skill"}</small></span><input type="number" min="0" max="1000000" step="1" value={values[key] || 0} onChange={(event) => setValues((current) => ({ ...current, [key]: Math.max(0, Math.floor(Number(event.target.value) || 0)) }))} /></label>)}</div>
  </Modal>;
}

function CharacterAnalysisCards({ catalog }: { catalog: UnifiedSkillCatalog }) {
  const [openCard, setOpenCard] = useState<"progression" | "skills" | "effects" | null>(null);
  const analysis = catalog.characterAnalysis;
  const progression = analysis.progression;
  return <section className="skill-analysis-cards" data-component-type="panel" data-theme="parchment">
    <header><p className="eyebrow">Analisi PG</p><h2>{catalog.character?.name || "Personaggio"}</h2><p>Apri una carta per leggere progressione, distribuzione delle abilità ed effetti ottenuti.</p></header>
    <div><button type="button" onClick={() => setOpenCard("progression")}><small>Progressione</small><strong>Livello {progression.currentLevel}</strong><span>{progression.xpUntilNextLevel} PE al prossimo livello</span></button><button type="button" onClick={() => setOpenCard("skills")}><small>Grimorio</small><strong>{analysis.ownedSkills} skill</strong><span>{analysis.xpSpent} Punti Esperienza spesi</span></button><button type="button" onClick={() => setOpenCard("effects")}><small>Capacità ottenute</small><strong>{analysis.passiveEffects + analysis.activeActions}</strong><span>{analysis.passiveEffects} passivi · {analysis.activeActions} azioni</span></button></div>
    {openCard === "progression" && <Modal surface="skills-progression" title="Progressione del personaggio" onClose={() => setOpenCard(null)} footer={<button className="button primary" onClick={() => setOpenCard(null)}>Chiudi</button>}><dl className="skill-analysis-detail"><div><dt>Livello attuale</dt><dd>{progression.currentLevel}</dd></div><div><dt>Livello calcolato dai PE spesi</dt><dd>{progression.expectedLevel}</dd></div><div><dt>Progresso nel livello</dt><dd>{progression.xpIntoLevel} / {progression.xpForNextLevel} PE</dd></div><div><dt>Mancano</dt><dd>{progression.xpUntilNextLevel} PE</dd></div></dl><div className="skill-level-progress"><span style={{ width: `${progression.progressPercent}%` }} /></div></Modal>}
    {openCard === "skills" && <Modal surface="skills-stats" title="Statistiche delle skill" onClose={() => setOpenCard(null)} wide footer={<button className="button primary" onClick={() => setOpenCard(null)}>Chiudi</button>}><dl className="skill-analysis-detail"><div><dt>Skill possedute</dt><dd>{analysis.ownedSkills}</dd></div><div><dt>Punti Esperienza spesi</dt><dd>{analysis.xpSpent}</dd></div><div><dt>Gruppi conosciuti</dt><dd>{analysis.byGroup.length}</dd></div><div><dt>Famiglie conosciute</dt><dd>{analysis.byFamily.length}</dd></div></dl><div className="skill-analysis-columns"><section><h3>Per gruppo</h3><ul>{analysis.byGroup.map((row) => <li key={row.group}><span>{row.group}</span><strong>{row.skills}</strong></li>)}</ul></section><section><h3>Per famiglia</h3><ul>{analysis.byFamily.map((row) => <li key={`${row.group}-${row.family}`}><span>{row.family}<small>{row.group}</small></span><strong>{row.skills}</strong></li>)}</ul></section></div></Modal>}
    {openCard === "effects" && <Modal surface="skills-effects" title="Effetti e azioni dalle skill" onClose={() => setOpenCard(null)} footer={<button className="button primary" onClick={() => setOpenCard(null)}>Chiudi</button>}><dl className="skill-analysis-detail"><div><dt>Effetti passivi</dt><dd>{analysis.passiveEffects}</dd></div><div><dt>Azioni disponibili</dt><dd>{analysis.activeActions}</dd></div><div><dt>Totale capacità</dt><dd>{analysis.passiveEffects + analysis.activeActions}</dd></div></dl><p className="muted-copy">I passivi accettati contribuiscono alla scheda; le azioni restano promemoria da usare al tavolo.</p></Modal>}
  </section>;
}

const COMBAT_BUTTON_MODIFIER_FIELDS: Array<[keyof CombatButtonModifiers, string, string]> = [
  ["attackBonus", "Attacco", "Bonus al tiro e al totale di attacco"],
  ["damageBonus", "Danno", "Bonus al danno prima del moltiplicatore"],
  ["damageTierBonus", "Tier", "Modifica il tier del danno"],
  ["penetrationFlat", "Perforazione", "Ignora punti di riduzione del danno"],
  ["penetrationPercent", "Perforazione %", "Ignora una percentuale della riduzione"],
];

function combatButtonModifierSummary(button: CombatButton) {
  const labels: Record<keyof CombatButtonModifiers, string> = {
    attackBonus: "ATK",
    damageBonus: "DMG",
    damageTierBonus: "TIER",
    penetrationFlat: "PERF",
    penetrationPercent: "PERF %",
  };
  const values = COMBAT_BUTTON_MODIFIER_FIELDS
    .filter(([key]) => button.modifiers[key] !== 0)
    .map(([key]) => `${labels[key]} ${button.modifiers[key] > 0 ? "+" : ""}${button.modifiers[key]}`);
  return values.length ? values.join(" · ") : "Nessun modificatore";
}

function CombatButtonEditor({ button, saving, onClose, onSave, onDelete }: {
  button: CombatButton | null;
  saving: boolean;
  onClose: () => void;
  onSave: (values: Record<string, unknown>) => void;
  onDelete?: () => void;
}) {
  const [name, setName] = useState(button?.name || "");
  const [helpText, setHelpText] = useState(button?.helpText || "");
  const [modifiers, setModifiers] = useState<CombatButtonModifiers>(button?.modifiers || { attackBonus: 0, damageBonus: 0, damageTierBonus: 0, penetrationFlat: 0, penetrationPercent: 0 });
  const [isPublic, setIsPublic] = useState(button?.public || false);
  const [active, setActive] = useState(button?.active ?? true);
  const [keepActive, setKeepActive] = useState(button?.keepActiveInCombat || false);
  const valid = name.trim().length > 0;
  return <Modal surface="skills-button-editor" title={button ? `Modifica · ${button.name}` : "Nuovo Bottone Combat"} onClose={onClose} wide footer={<>{onDelete && <button type="button" className="button danger" disabled={saving} onClick={onDelete}>Elimina</button>}<button type="button" className="button secondary" disabled={saving} onClick={onClose}>Annulla</button><button type="button" className="button primary" disabled={saving || !valid} onClick={() => onSave({ name: name.trim(), helpText: helpText.trim(), modifiers, public: isPublic, active, keepActiveInCombat: keepActive })}>{saving ? "Salvataggio…" : "Salva bottone"}</button></>}>
    <form className="combat-button-editor" data-component-type="form" data-theme="combat" onSubmit={(event) => event.preventDefault()}>
      <section className="combat-button-editor-copy"><label>Nome<input value={name} maxLength={80} autoFocus placeholder="Es. Colpo poderoso" onChange={(event) => setName(event.target.value)} /></label><label>Testo da mostrare<textarea value={helpText} maxLength={1000} rows={5} placeholder="Testo visibile passando sul bottone…" onChange={(event) => setHelpText(event.target.value)} /></label></section>
      <section><header><div><p className="eyebrow">Fino a 5 modificatori</p><h3>Modificatori dell'attacco</h3></div></header><div className="combat-button-modifier-fields">{COMBAT_BUTTON_MODIFIER_FIELDS.map(([key, label, description]) => <label key={key}><span>{label}<small>{description}</small></span><input type="number" min="-999" max="999" step="1" value={modifiers[key]} onChange={(event) => setModifiers((current) => ({ ...current, [key]: Math.max(-999, Math.min(999, Math.trunc(Number(event.target.value) || 0))) }))} /></label>)}</div></section>
      <section className="combat-button-flags"><label><input type="checkbox" checked={isPublic} onChange={(event) => setIsPublic(event.target.checked)} /><span><strong>Pubblico</strong><small>Gli altri personaggi possono vederlo nella loro pagina.</small></span></label><label><input type="checkbox" checked={active} onChange={(event) => setActive(event.target.checked)} /><span><strong>Attivo</strong><small>Mostra il bottone nella colonna Attacco del combattimento.</small></span></label><label><input type="checkbox" checked={keepActive} onChange={(event) => setKeepActive(event.target.checked)} /><span><strong>Tieni Attivo in Combat</strong><small>Dopo un attacco applicato il bottone resta selezionato.</small></span></label></section>
    </form>
  </Modal>;
}

function CombatButtonsTab({ catalog, saving, onCreate, onUpdate, onDelete }: {
  catalog: UnifiedSkillCatalog;
  saving: boolean;
  onCreate: (values: Record<string, unknown>) => void;
  onUpdate: (button: CombatButton, values: Record<string, unknown>) => void;
  onDelete: (button: CombatButton) => void;
}) {
  const [editing, setEditing] = useState<CombatButton | "new" | null>(null);
  useEffect(() => { if (editing !== "new" && editing && !catalog.combatButtons.own.some((button) => button.id === editing.id)) setEditing(null); }, [catalog.combatButtons.own, editing]);
  const own = catalog.combatButtons.own;
  const publicButtons = catalog.combatButtons.public;
  return <section className="combat-buttons-workspace" data-component-type="panel" data-theme="combat">
    <header><div><p className="eyebrow">Scorciatoie del prossimo attacco</p><h2>Bottoni Combat</h2><p>Configura fino a {catalog.combatButtons.limit} bottoni. In combattimento puoi combinarli; quelli non persistenti si spengono quando il danno viene applicato.</p></div><div className="combat-button-capacity"><strong>{own.length}/{catalog.combatButtons.limit}</strong><small>configurati</small><button type="button" className="button primary" disabled={!catalog.combatButtons.availableSlots || saving} onClick={() => setEditing("new")}>Nuovo bottone</button></div></header>
    <div className="combat-button-config-grid">{own.map((button) => <button type="button" key={button.id} className="combat-button-config-card" data-state={button.active ? "active" : "inactive"} title={button.helpText || button.name} onClick={() => setEditing(button)}><span className="combat-button-config-index">{button.order + 1}</span><span><strong>{button.name}</strong><small>{combatButtonModifierSummary(button)}</small></span><span className="combat-button-config-badges">{button.public && <em>Pubblico</em>}{button.keepActiveInCombat && <em>Persistente</em>}{!button.active && <em>Non attivo</em>}</span></button>)}</div>
    {!own.length && <div className="skill-empty-catalog"><span>⚔</span><h3>Nessun bottone configurato</h3><p>Crea il primo modificatore rapido per il combattimento.</p></div>}
    <section className="combat-buttons-public"><header><div><p className="eyebrow">Condivisi dagli altri personaggi</p><h3>Bottoni pubblici</h3></div><span>{publicButtons.length}</span></header>{publicButtons.length ? <div className="combat-button-public-list">{publicButtons.map((button) => <article key={button.id} title={button.helpText || button.name}><div><strong>{button.name}</strong><small>{button.characterName}</small></div><p>{combatButtonModifierSummary(button)}</p>{button.helpText && <span>{button.helpText}</span>}</article>)}</div> : <p className="muted-copy">Nessun altro personaggio ha condiviso un bottone.</p>}</section>
    {editing && <CombatButtonEditor key={editing === "new" ? "new" : editing.id} button={editing === "new" ? null : editing} saving={saving} onClose={() => setEditing(null)} onSave={(values) => { if (editing === "new") onCreate(values); else onUpdate(editing, values); setEditing(null); }} onDelete={editing !== "new" ? () => { if (window.confirm(`Eliminare ${editing.name}?`)) { onDelete(editing); setEditing(null); } } : undefined} />}
  </section>;
}

export function SkillsPage() {
  const { personaggi, notify } = useApp();
  const queryClient = useQueryClient();
  const characterId = personaggi.giocatore.activePersonaggioId;
  const [selectedGroup, setSelectedGroup] = useState("");
  const [characterSection, setCharacterSection] = useState<CharacterSection>("unlocked");
  const [familyId, setFamilyId] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [searchSelectedSkill, setSearchSelectedSkill] = useState<UnifiedSkill | null>(null);
  const [creating, setCreating] = useState(false);
  const [unlockTarget, setUnlockTarget] = useState<UnifiedSkill | null>(null);
  const [unlockPreview, setUnlockPreview] = useState<UnifiedUnlockPreview | null>(null);
  const [unlockError, setUnlockError] = useState("");
  const [reminder, setReminder] = useState<ActiveReminder | null>(null);
  const [editingXp, setEditingXp] = useState(false);
  const params = new URLSearchParams();
  if (characterId) params.set("character_id", String(characterId));
  if (selectedGroup && selectedGroup !== CHARACTER_GROUP && selectedGroup !== SEARCH_GROUP) params.set("group", selectedGroup);
  if (familyId && selectedGroup !== CHARACTER_GROUP && selectedGroup !== SEARCH_GROUP) params.set("family_id", String(familyId));
  if (selectedGroup === CHARACTER_GROUP) params.set("owned_only", "true");
  if (selectedGroup === SEARCH_GROUP) params.set("search_mode", "true");
  const catalogQuery = useQuery({ queryKey: ["skills", characterId, selectedGroup, characterSection, familyId], queryFn: () => getData<UnifiedSkillCatalog>(`/api/v1/skills?${params}`) });
  const catalog = catalogQuery.data;
  useEffect(() => {
    if (!catalog) return;
    if (!selectedGroup && catalog.selectedGroup) setSelectedGroup(catalog.selectedGroup);
    if (selectedGroup !== CHARACTER_GROUP && familyId === null && catalog.selectedFamilyId) setFamilyId(catalog.selectedFamilyId);
  }, [catalog, familyId, selectedGroup]);
  const selected = catalog?.skills.find((skill) => skill.id === selectedId) || (searchSelectedSkill?.id === selectedId ? searchSelectedSkill : null);
  const selectedFamily = catalog?.families.find((family) => family.id === familyId) || null;
  const visibleFamilies = useMemo(() => catalog?.families.filter((family) => family.group === selectedGroup) || [], [catalog, selectedGroup]);
  const canReorder = Boolean(catalog?.permissions.canManageSkills && selectedGroup !== CHARACTER_GROUP && selectedGroup !== SEARCH_GROUP && familyId && (catalog?.skills.length || 0) > 1);

  const writeMutation = useMutation({
    mutationFn: ({ action, skillId, values, confirmation }: { action: "skills.create" | "skills.update" | "skills.archive" | "skills.delete"; skillId?: number; values?: Record<string, unknown>; confirmation?: string }) => command<SkillActionData>(action, action === "skills.delete" ? { skillId, confirmation } : { skillId, values: values || {} }, "skills"),
    onSuccess: async (response, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["skills"] });
      if (response.data.skill?.id) setSelectedId(response.data.skill.id);
      setCreating(false);
      if (variables.action === "skills.archive" || variables.action === "skills.delete") setSelectedId(null);
      notify(variables.action === "skills.create" ? "Abilità creata." : variables.action === "skills.archive" ? "Abilità archiviata." : variables.action === "skills.delete" ? "Abilità eliminata definitivamente." : "Abilità aggiornata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const reorderMutation = useMutation({
    mutationFn: (skillIds: number[]) => command<SkillActionData>("skills.reorder", { familyId, skillIds }, "skills-order"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["skills"] });
      notify("Ordine delle abilità aggiornato.");
    },
    onError: async (error: Error) => {
      await queryClient.invalidateQueries({ queryKey: ["skills"] });
      notify(error.message, "error");
    },
  });
  const previewMutation = useMutation({
    mutationFn: (skill: UnifiedSkill) => command<SkillActionData>("skills.previewUnlock", { characterId, skillId: skill.id }, "skills"),
    onSuccess: (response) => { setUnlockPreview(response.data.skillPreview || null); setUnlockError(""); },
    onError: (error: Error) => setUnlockError(error.message),
  });
  const unlockMutation = useMutation({
    mutationFn: ({ spend, acceptedPassiveIds, note }: { spend: Record<string, number>; acceptedPassiveIds: string[]; note: string }) => command<SkillActionData>("skills.unlock", { characterId, skillId: unlockTarget?.id, spend, acceptedPassiveIds, note }, "skills"),
    onSuccess: async (response) => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["skills"] }), queryClient.invalidateQueries({ queryKey: ["personaggi"] }), queryClient.invalidateQueries({ queryKey: ["character-sheet"] })]);
      setUnlockTarget(null); setUnlockPreview(null); notify(response.events[0]?.message || "Sblocco aggiornato.");
    },
    onError: (error: Error) => setUnlockError(error.message),
  });
  const xpMutation = useMutation({
    mutationFn: (xp: Record<string, number>) => command<SkillActionData>("skills.updateCharacterXp", { characterId, xp }, "skills-xp"),
    onSuccess: async (response) => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["skills"] }), queryClient.invalidateQueries({ queryKey: ["personaggi"] }), queryClient.invalidateQueries({ queryKey: ["character-sheet"] }), queryClient.invalidateQueries({ queryKey: ["competencies"] })]);
      setEditingXp(false);
      notify(response.events[0]?.message || "Punti Esperienza aggiornati.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const actionConfigurationMutation = useMutation({
    mutationFn: (actions: ActiveReminder[]) => command<SkillActionData>("skills.configureCharacterActions", {
      characterId,
      actions: actions.map((action, order) => ({ skillId: action.skillId, actionId: action.id, enabled: action.enabled !== false, order, note: action.characterNote || "" })),
    }, "skills-actions"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["skills"] });
      notify("Configurazione delle azioni salvata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const combatButtonMutation = useMutation({
    mutationFn: ({ action, buttonId, values }: { action: "combatButtons.create" | "combatButtons.update" | "combatButtons.delete"; buttonId?: number; values?: Record<string, unknown> }) => command<SkillActionData>(action, { characterId, buttonId, values: values || {} }, "skills-combat-buttons"),
    onSuccess: async (response) => {
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["skills"] }), queryClient.invalidateQueries({ queryKey: ["combat"] })]);
      notify(response.events[0]?.message || "Bottoni combat aggiornati.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const beginUnlock = (skill: UnifiedSkill) => { setUnlockTarget(skill); setUnlockPreview(null); setUnlockError(""); previewMutation.mutate(skill); };

  return <div className="page skills-page">
    <header className="page-header skill-page-header"><div><p className="eyebrow">Grimorio della progressione</p><h1>Abilità</h1><p>{catalog?.character ? `${catalog.character.name} · livello ${catalog.character.level}` : "Seleziona un personaggio"}</p></div><div className="button-row">{catalog?.permissions.canManageSkills && selectedGroup !== CHARACTER_GROUP && selectedGroup !== SEARCH_GROUP && <button className="button primary" onClick={() => setCreating(true)}>Crea abilità</button>}</div></header>
    {catalog?.character && <section className="skill-xp-ribbon" data-component-type="toolbar" data-theme="dark" role="button" tabIndex={0} aria-label="Modifica Punti Esperienza disponibili" onClick={() => setEditingXp(true)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setEditingXp(true); } }}><div><small>PE disponibili</small><strong>{Object.values(catalog.character.xp).reduce((sum, value) => sum + value, 0)}</strong></div>{Object.entries(XP_LABELS).map(([key, label]) => <span key={key} data-xp={key}><small>{label}</small><strong>{catalog.character?.xp[key] || 0}</strong></span>)}<div><small>Punti Esperienza Spesi</small><strong>{catalog.characterAnalysis.xpSpent}</strong></div><div><small>Skill possedute</small><strong>{catalog.characterAnalysis.ownedSkills}</strong></div></section>}
    {catalogQuery.isLoading && <section className="panel"><p>Consultazione del grimorio…</p></section>}
    {catalogQuery.error && <section className="panel danger-panel"><p>{(catalogQuery.error as Error).message}</p></section>}
    {catalog && <div className="skills-layout">
      <aside className="skill-group-rail" data-component-type="list" data-theme="dark"><header><p className="eyebrow">Navigazione</p><h2>Gruppi</h2></header>{catalog.groups.map((group) => <button key={group.key} aria-pressed={group.key === selectedGroup} className={group.key === selectedGroup ? "active" : ""} onClick={() => { setSelectedGroup(group.key); setFamilyId(catalog.families.find((family) => family.group === group.key && family.skillCount > 0)?.id || catalog.families.find((family) => family.group === group.key)?.id || null); }}><span><strong>{group.name}</strong><small>{group.familyCount} famiglie</small></span><b>{group.skillCount}</b></button>)}<button aria-pressed={selectedGroup === SEARCH_GROUP} className={selectedGroup === SEARCH_GROUP ? "active" : ""} onClick={() => { setSelectedGroup(SEARCH_GROUP); setFamilyId(null); }}><span><strong>Cerca Abilità</strong><small>Ricerca e filtri</small></span><b aria-hidden="true">⌕</b></button><button aria-pressed={selectedGroup === CHARACTER_GROUP} className={selectedGroup === CHARACTER_GROUP ? "active" : ""} onClick={() => { setSelectedGroup(CHARACTER_GROUP); setCharacterSection("unlocked"); setFamilyId(null); }}><span><strong>Personaggio</strong><small>Grimorio personale</small></span><b>{catalog.characterAnalysis.ownedSkills}</b></button></aside>
      <main className="skill-catalog" data-component-type="panel" data-theme="parchment">
        {selectedGroup !== SEARCH_GROUP && <nav className="skill-family-nav" role="tablist" aria-label={selectedGroup === CHARACTER_GROUP ? "Sezioni del personaggio" : `Famiglie del gruppo ${selectedGroup}`} data-component-type="tabset" data-theme="gold">{selectedGroup === CHARACTER_GROUP ? <><button role="tab" aria-selected={characterSection === "unlocked"} className={characterSection === "unlocked" ? "active" : ""} onClick={() => setCharacterSection("unlocked")}>Sbloccate <span>{catalog.characterAnalysis.ownedSkills}</span></button><button role="tab" aria-selected={characterSection === "analysis"} className={characterSection === "analysis" ? "active" : ""} onClick={() => setCharacterSection("analysis")}>Analisi PG</button><button role="tab" aria-selected={characterSection === "combat-buttons"} className={characterSection === "combat-buttons" ? "active" : ""} onClick={() => setCharacterSection("combat-buttons")}>Bottoni Combat <span>{catalog.combatButtons.own.length}</span></button></> : visibleFamilies.map((family) => <button key={family.id} role="tab" aria-label={`${family.name}, ${family.skillCount} skill`} aria-selected={family.id === familyId} className={family.id === familyId ? "active" : ""} data-has-art={family.imageUrl ? "true" : "false"} style={{ "--family-art": family.imageUrl ? `url(${family.imageUrl})` : "none" } as CSSProperties} onClick={() => setFamilyId(family.id)}><span><strong>{family.name}</strong><small>{family.skillCount} skill</small></span></button>)}</nav>}
        {selectedGroup === SEARCH_GROUP ? <SkillSearchWorkspace catalog={catalog} onOpen={(skill) => { setSearchSelectedSkill(skill); setSelectedId(skill.id); }} /> : selectedGroup === CHARACTER_GROUP && characterSection === "analysis" ? <CharacterAnalysisCards catalog={catalog} /> : selectedGroup === CHARACTER_GROUP && characterSection === "combat-buttons" ? <CombatButtonsTab catalog={catalog} saving={combatButtonMutation.isPending} onCreate={(values) => combatButtonMutation.mutate({ action: "combatButtons.create", values })} onUpdate={(button, values) => combatButtonMutation.mutate({ action: "combatButtons.update", buttonId: button.id, values })} onDelete={(button) => combatButtonMutation.mutate({ action: "combatButtons.delete", buttonId: button.id })} /> : <><header className="skill-catalog-toolbar" style={{ "--family-art": selectedGroup === CHARACTER_GROUP ? "none" : selectedFamily?.imageUrl ? `url(${selectedFamily.imageUrl})` : "none" } as CSSProperties}><div><p className="eyebrow">{selectedGroup === CHARACTER_GROUP ? "Personaggio" : selectedFamily?.group || "Famiglia"}</p><h2>{selectedGroup === CHARACTER_GROUP ? "Sbloccate" : selectedFamily?.name || "Abilità"}</h2>{selectedGroup === CHARACTER_GROUP ? <p>Tutte le abilità possedute, indipendentemente da gruppo e famiglia.</p> : selectedFamily?.notes ? <p>{selectedFamily.notes}</p> : canReorder ? <p>Trascina le carte per scegliere l'ordine mostrato nell'interfaccia.</p> : null}</div></header><SkillCardGrid skills={catalog.skills} canReorder={canReorder && !reorderMutation.isPending} onOpen={(skillId) => { setSearchSelectedSkill(null); setSelectedId(skillId); }} onReorder={(skillIds) => reorderMutation.mutate(skillIds)} />{!catalog.skills.length && <div className="skill-empty-catalog"><span>✧</span><h3>{selectedGroup === CHARACTER_GROUP ? "Nessuna abilità sbloccata" : "Nessuna carta in questa costellazione"}</h3><p>{selectedGroup === CHARACTER_GROUP ? "Le abilità compariranno qui dopo il primo sblocco." : "Cambia famiglia."}</p></div>}</>}
      </main>
    </div>}
    {selected && catalog && <SkillDetailModal key={selected.id} skill={selected} catalog={catalog} saving={writeMutation.isPending} onClose={() => setSelectedId(null)} onUnlock={() => beginUnlock(selected)} onSave={(values) => writeMutation.mutate({ action: "skills.update", skillId: selected.id, values })} onArchive={() => { if (window.confirm(`Archiviare ${selected.name}?`)) writeMutation.mutate({ action: "skills.archive", skillId: selected.id }); }} onDelete={catalog.permissions.canDeleteSkills ? () => { if (window.confirm(`Eliminare definitivamente ${selected.name}? Gli sblocchi collegati saranno rimossi e i PE spesi verranno restituiti ai personaggi.`)) writeMutation.mutate({ action: "skills.delete", skillId: selected.id, confirmation: selected.name }); } : undefined} />}
    {creating && catalog && <SkillCreationModal catalog={catalog} characterId={characterId} saving={writeMutation.isPending} onClose={() => setCreating(false)} onSave={(values) => writeMutation.mutate({ action: "skills.create", values })} />}
    {unlockTarget && <UnlockModal preview={unlockPreview} loading={previewMutation.isPending} saving={unlockMutation.isPending} error={unlockError} onClose={() => { setUnlockTarget(null); setUnlockPreview(null); }} onConfirm={(spend, acceptedPassiveIds, note) => unlockMutation.mutate({ spend, acceptedPassiveIds, note })} onRemove={() => unlockMutation.mutate({ spend: { general: 0, red: 0, green: 0, blue: 0 }, acceptedPassiveIds: [], note: "" })} />}
    {editingXp && catalog && <XpEditorModal catalog={catalog} saving={xpMutation.isPending} onClose={() => setEditingXp(false)} onSave={(xp) => xpMutation.mutate(xp)} />}
    {reminder && <ReminderModal reminder={reminder} onClose={() => setReminder(null)} />}
  </div>;
}
