import { type CSSProperties, type FormEvent, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { DndContext, DragOverlay, PointerSensor, pointerWithin, useDraggable, useSensor, useSensors, type DragEndEvent, type DragStartEvent } from "@dnd-kit/core";
import { createPortal } from "react-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Modal } from "../../components/Modal";
import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type { CharacterSheet, CharacterSlot as Slot, EffectConfiguration, Item, ItemCatalog } from "../../lib/types";
import { CharacterEffectsWorkspace } from "./CharacterEffectsWorkspace";
import { CharacterEquipment } from "./CharacterEquipment";
import { CharacterSlot } from "./CharacterSlot";
import { ItemEditorModal } from "./ItemEditorModal";
import { CarriedCoinsControl, SharedCoinsCard } from "./CoinControls";
import { SlotItemPicker } from "./SlotItemPicker";
import { SLOT_ACTIONS_HIDE_DELAY, canSwap, firstFreeSlot, fits, resolveEquipTarget, shouldCloseSlotActions } from "./inventoryRules";

type RaceConfiguration = {
  races: Array<{ value: string; label: string; subraces: Array<{ value: string; label: string }> }>;
  extraValue: string;
};
type SheetData = { character: CharacterSheet; effectCatalog: unknown[]; effectConfiguration: EffectConfiguration; raceConfiguration: RaceConfiguration; storageCatalog: Item[] };
type ActionData = { character?: CharacterSheet | null; item?: Item | null; catalog?: ItemCatalog | null };

type StatValue = CharacterSheet["characteristics"][number];
type CharacterValuesView = "primary" | "advanced";

function formatCalculationNumber(value: number, signed = false): string {
  const normalized = Object.is(value, -0) ? 0 : value;
  const display = String(Number(normalized.toFixed(6)));
  if (signed && normalized > 0) return `+${display}`;
  return display;
}

function CalculationTooltip({ id, calculation, total, totalLabel = "Totale", resourceCurrent, resourceSpent }: {
  id: string;
  calculation: StatValue["calculation"];
  total: number;
  totalLabel?: string;
  resourceCurrent?: number;
  resourceSpent?: number;
}) {
  return <div className="calculation-tooltip" id={id} role="tooltip" data-component-type="inspector" data-theme="dark">
    <p className="calculation-tooltip-title">Come viene calcolato</p>
    <dl>{calculation.map((part) => <div key={part.key}><dt>{part.label}</dt><dd>{formatCalculationNumber(part.value, part.key !== "base")}</dd></div>)}</dl>
    <p className="calculation-total">{totalLabel}: <strong>{total}</strong></p>
    {resourceCurrent != null && resourceSpent != null && <p className="calculation-current">Spesi: {resourceSpent} · Attuali: <strong>{resourceCurrent}</strong></p>}
  </div>;
}

function StatList({ stats, compact = false, modifiers }: { stats: StatValue[]; compact?: boolean; modifiers?: Record<string, number> }) {
  return <div className={`stat-list ${compact ? "compact" : ""}`}>{stats.map((stat) => {
    const modifier = modifiers?.[stat.key];
    const displayedStatValue = formatCalculationNumber(stat.value);
    const displayedValue = modifier == null ? displayedStatValue : `${displayedStatValue} (${formatCalculationNumber(modifier)})`;
    const tooltipId = `stat-calculation-${stat.key}`;
    return <div
      className="stat-value"
      key={stat.key}
      data-stat-key={stat.key}
      style={{ "--stat-color": `var(--stat-${stat.key}, var(--stat-neutral))` } as CSSProperties}
      tabIndex={0}
      aria-describedby={tooltipId}
      aria-label={`${stat.label}: ${displayedValue}. Mostra il calcolo.`}
    ><small>{stat.label}</small><strong>{displayedValue}</strong><CalculationTooltip id={tooltipId} calculation={stat.calculation} total={stat.value} /></div>;
  })}</div>;
}

function EncumbranceSummary({ encumbrance }: { encumbrance: CharacterSheet["encumbrance"] }) {
  const tooltipId = "encumbrance-calculation";
  return <div
    className="weight-summary"
    tabIndex={0}
    aria-describedby={tooltipId}
    aria-label={`Peso ${encumbrance.total}, passo di carico ${encumbrance.loadStep}, malus PA ${encumbrance.penalty}. Mostra il calcolo.`}
  >
    <span>Peso</span>
    <strong>{String(encumbrance.total)} / passo {String(encumbrance.loadStep)}</strong>
    <small>Malus PA {String(encumbrance.penalty)} · passa sopra per il calcolo</small>
    <div className="weight-tooltip" id={tooltipId} role="tooltip" data-component-type="inspector" data-theme="dark">
      <p className="weight-tooltip-title">Come viene calcolato</p>
      <dl>
        <div><dt>Equipaggiamento</dt><dd>{encumbrance.equipmentRaw} × (1 − {encumbrance.equipmentDiscountPercent}/100) = <strong>{encumbrance.equipment}</strong></dd></div>
        <div><dt>Zaino</dt><dd><strong>{encumbrance.backpack}</strong></dd></div>
        <div><dt>Faretra</dt><dd><strong>{encumbrance.quiver}</strong></dd></div>
        <div><dt>Ignorato dagli spazi magici</dt><dd><strong>{encumbrance.magicalWeightIgnored}</strong> (non conteggiato)</dd></div>
      </dl>
      <p className="weight-formula">Totale: {encumbrance.equipment} + {encumbrance.backpack} + {encumbrance.quiver} = <strong>{encumbrance.total}</strong></p>
      <p className="weight-formula">Malus: ⌊{encumbrance.total} ÷ {encumbrance.loadStep}⌋ = <strong>{encumbrance.penalty} PA</strong></p>
    </div>
  </div>;
}

function ReagentSummary({ reagents }: { reagents: CharacterSheet["reagents"] }) {
  const formatValue = (value: number) => Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
  return <section className="reagent-values" data-value-group="reagents">
    <h3>Scorte reagenti e alchimia</h3>
    <div className="reagent-capacity" aria-label="Capacità della borsa reagenti">
      <div><small>Capacità</small><strong>{formatValue(reagents.slotMax)}</strong></div>
      <div><small>Occupati</small><strong>{formatValue(reagents.occupied)}</strong></div>
      <div><small>Liberi</small><strong>{formatValue(reagents.remaining)}</strong></div>
    </div>
    <div className="reagent-columns">
      <div><h4>Ingredienti</h4>{reagents.ingredientRows.length > 0
        ? <dl>{reagents.ingredientRows.map((entry) => <div key={entry.key}><dt>{entry.label}</dt><dd>{formatValue(entry.value)}</dd></div>)}</dl>
        : <p>Nessun reagente in Alchimia&Contenitori.</p>}</div>
      <div><h4>Moltiplicatori</h4>{reagents.multiplierRows.length > 0
        ? <dl>{reagents.multiplierRows.map((entry) => <div key={entry.key}><dt>{entry.label}</dt><dd>× {formatValue(entry.value)}</dd></div>)}</dl>
        : <p>Nessun moltiplicatore configurato.</p>}</div>
    </div>
    <p className="reagent-help">La potenza alchemica e gli effetti di colore sono spiegati nella guida “Variabili del personaggio e alchimia”.</p>
  </section>;
}

function ResourceControl({ characterId, resource, onUpdate }: { characterId: number; resource: CharacterSheet["resources"][number]; onUpdate: (character: CharacterSheet) => void }) {
  const { notify } = useApp();
  const [value, setValue] = useState(resource.current);
  useEffect(() => setValue(resource.current), [resource.current]);
  const mutation = useMutation({
    mutationFn: (current: number) => command<ActionData>("character.updateResource", { characterId, resource: resource.key, current }),
    onSuccess: (result, savedValue) => { if (result.data.character) onUpdate(result.data.character); notify(`Fatto! ${resource.label} salvati a ${savedValue}.`); },
    onError: (error: Error) => notify(error.message, "error")
  });
  // Il sifone è una riserva separata: esiste soltanto sulla barra del Mana.
  const siphon = resource.key === "mana" ? resource.siphon : 0;
  const siphonMutation = useMutation({
    mutationFn: () => command<ActionData>("character.recoverManaSiphon", { characterId }),
    onSuccess: (result) => { if (result.data.character) onUpdate(result.data.character); notify(`Fatto! ${siphon} Mana recuperati dal sifone.`); },
    onError: (error: Error) => notify(error.message, "error")
  });
  const dirty = value !== resource.current;
  const progress = resource.maximum > 0 ? Math.max(0, Math.min(100, (value / resource.maximum) * 100)) : 0;
  const tooltipId = `resource-calculation-${resource.key}`;
  return <article className={`resource-card ${dirty ? "dirty" : ""} ${mutation.isPending ? "saving" : ""}`} style={{ "--resource-progress": `${progress}%`, "--resource-color": `var(${resource.colorToken})` } as CSSProperties} data-resource={resource.key} data-maximum={resource.maximum} data-dirty={dirty ? "true" : "false"}>
    <div className="resource-track" role="progressbar" aria-label={resource.label} aria-describedby={tooltipId} aria-valuemin={0} aria-valuemax={resource.maximum} aria-valuenow={value} aria-valuetext={`${value} su ${resource.maximum}`} tabIndex={0}>
      <div className="resource-fill" />
      <div className="resource-readout" aria-hidden="true"><span>0</span><strong>{value}</strong><span>{resource.maximum}</span></div>
      <div className="resource-actions" aria-label={`Modifica ${resource.label}`}>
        {[-10, -5, -1, 1, 5, 10].map((delta) => <button key={delta} type="button" disabled={mutation.isPending} onClick={() => setValue((current) => current + delta)} aria-label={`${delta > 0 ? "Aumenta" : "Riduci"} ${resource.label} di ${Math.abs(delta)}`}>{delta > 0 ? `+${delta}` : delta}</button>)}
        <button type="button" disabled={mutation.isPending} onClick={() => setValue(resource.maximum)} aria-label={`Porta ${resource.label} al massimo`}>Pieno</button>
        <button type="button" className="resource-save" disabled={mutation.isPending || !dirty} onClick={() => mutation.mutate(value)} aria-label={`Salva ${resource.label}`}>Salva</button>
        {resource.key === "mana" && <button
          type="button"
          className="resource-siphon"
          disabled={siphonMutation.isPending || siphon <= 0}
          onClick={() => siphonMutation.mutate()}
          aria-label={siphon > 0 ? `Recupera ${siphon} Mana dal sifone` : "Nessun Mana nel sifone da recuperare"}
        >Sifone: {siphon}</button>}
      </div>
    </div>
    <CalculationTooltip id={tooltipId} calculation={resource.calculation} total={resource.maximum} totalLabel="Massimo" resourceCurrent={resource.current} resourceSpent={resource.spent} />
  </article>;
}

function QuickStatControl({ characterId, stat, onUpdate }: { characterId: number; stat: StatValue; onUpdate: (character: CharacterSheet) => void }) {
  const { notify } = useApp();
  const mutation = useMutation({
    mutationFn: (delta: -1 | 1) => command<ActionData>("character.adjustQuickStat", { characterId, stat: stat.key, delta }),
    onSuccess: (result) => { if (result.data.character) onUpdate(result.data.character); },
    onError: (error: Error) => notify(error.message, "error")
  });
  const tooltipId = `quick-stat-calculation-${stat.key}`;
  return <article className={`quick-stat-control ${mutation.isPending ? "saving" : ""}`} style={{ "--quick-stat-color": `var(--stat-${stat.key}, var(--stat-neutral))` } as CSSProperties} data-stat-key={stat.key} data-component-type="card" data-theme="dark" tabIndex={0} aria-describedby={tooltipId}>
    <span>{stat.label}</span><strong aria-live="polite">{stat.value}</strong>
    <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate(-1)} aria-label={`Riduci ${stat.label} di 1`}>−</button>
    <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate(1)} aria-label={`Aumenta ${stat.label} di 1`}>+</button>
    <CalculationTooltip id={tooltipId} calculation={stat.calculation} total={stat.value} />
  </article>;
}

function OverviewModal({ character, raceConfiguration, saving, onClose, onSave }: { character: CharacterSheet; raceConfiguration: RaceConfiguration; saving: boolean; onClose: () => void; onSave: (values: Record<string, unknown>) => void }) {
  const initialRace = raceConfiguration.races.find((entry) => entry.value === character.race1);
  const [race1Choice, setRace1Choice] = useState(initialRace ? initialRace.value : raceConfiguration.extraValue);
  const [race1Extra, setRace1Extra] = useState(initialRace ? "" : character.race1);
  const initialSubrace = initialRace?.subraces.find((entry) => entry.value === character.race2);
  const [race2Choice, setRace2Choice] = useState(character.race2 ? (initialSubrace ? initialSubrace.value : raceConfiguration.extraValue) : "");
  const [race2Extra, setRace2Extra] = useState(initialSubrace ? "" : character.race2);
  const subraces = raceConfiguration.races.find((entry) => entry.value === race1Choice)?.subraces || [];
  const changeRace1 = (value: string) => {
    setRace1Choice(value);
    if (value !== raceConfiguration.extraValue) setRace1Extra("");
    const nextSubraces = raceConfiguration.races.find((entry) => entry.value === value)?.subraces || [];
    if (!nextSubraces.some((entry) => entry.value === race2Choice)) {
      setRace2Choice("");
      setRace2Extra("");
    }
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    onSave({ name: form.get("name"), race1: race1Choice === raceConfiguration.extraValue ? race1Extra : race1Choice, race2: race2Choice === raceConfiguration.extraValue ? race2Extra : race2Choice, race3: form.get("race3"), level: form.get("level"), age: form.get("age"), sex: form.get("sex"), coins: form.get("coins"), details: form.get("details"), critMin: form.get("critMin"), critNormal: form.get("critNormal"), critMajor: form.get("critMajor") });
  };
  return <Modal surface="character-overview" title="Modifica panoramica" onClose={onClose} footer={<><button className="button secondary" onClick={onClose}>Annulla</button><button className="button primary" type="submit" form="overview-form" disabled={saving}>Salva</button></>}><form id="overview-form" className="stacked-form" onSubmit={submit}><div className="form-grid"><label>Nome<input name="name" defaultValue={character.name} required /></label><label>Livello<input name="level" type="number" min={1} defaultValue={character.level} /></label><label>Razza 1<select value={race1Choice} onChange={(event) => changeRace1(event.target.value)}>{raceConfiguration.races.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}<option value={raceConfiguration.extraValue}>Extra…</option></select>{race1Choice === raceConfiguration.extraValue && <input value={race1Extra} onChange={(event) => setRace1Extra(event.target.value)} placeholder="Razza speciale" required />}</label><label>Razza 2<select value={race2Choice} onChange={(event) => { setRace2Choice(event.target.value); if (event.target.value !== raceConfiguration.extraValue) setRace2Extra(""); }}><option value="">Nessuna</option>{subraces.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}<option value={raceConfiguration.extraValue}>Extra…</option></select>{race2Choice === raceConfiguration.extraValue && <input value={race2Extra} onChange={(event) => setRace2Extra(event.target.value)} placeholder="Sottorazza speciale" required />}</label><label>Razza 3<input name="race3" defaultValue={character.race3} /></label><label>Età<input name="age" type="number" min={0} defaultValue={character.age ?? ""} /></label><label>Sesso<input name="sex" defaultValue={character.sex} /></label><label>Monete<input name="coins" type="number" min={0} defaultValue={character.coins} /></label><label>Critico minore<input name="critMin" defaultValue={character.criticalThresholds.minor} /></label><label>Critico normale<input name="critNormal" defaultValue={character.criticalThresholds.normal} /></label><label>Critico maggiore<input name="critMajor" defaultValue={character.criticalThresholds.major} /></label></div><label>Dettagli<textarea name="details" rows={5} defaultValue={character.details} /></label></form></Modal>;
}

/** A catalogue row that can be clicked to arm an item or dragged straight onto a slot. */
function CatalogSuggestion({ item, compatible, selected, keyboardActive, reason, onHover, onChoose }: {
  item: Item;
  compatible: boolean;
  selected: boolean;
  keyboardActive: boolean;
  reason: string;
  onHover: () => void;
  onChoose: () => void;
}) {
  const draggable = useDraggable({ id: `catalog:${item.id}`, data: { catalogItem: item } });
  return <button
    id={`character-item-suggestion-${item.id}`}
    ref={draggable.setNodeRef}
    {...draggable.listeners}
    {...draggable.attributes}
    type="button"
    role="option"
    aria-selected={selected}
    className={`${selected ? "active" : ""} ${keyboardActive ? "keyboard-active" : ""} ${compatible ? "" : "incompatible"} ${draggable.isDragging ? "dragging" : ""}`}
    style={draggable.transform ? { transform: `translate3d(${draggable.transform.x}px, ${draggable.transform.y}px, 0)` } : undefined}
    onMouseEnter={onHover}
    onClick={onChoose}
  >
    {item.imageUrl ? <img src={item.imageUrl} alt="" loading="lazy" /> : <span className="suggestion-glyph" aria-hidden="true">◆</span>}
    <strong>{item.name}</strong>
    <span>{compatible ? `${item.types.join(" · ") || "Oggetto"} · peso ${item.weight ?? 0}` : reason}</span>
  </button>;
}

export function CharacterPage() {
  const { characterId } = useParams();
  const { personaggi, media, notify } = useApp();
  const id = Number(characterId || personaggi.giocatore.activePersonaggioId);
  const queryClient = useQueryClient();
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search.trim());
  const sheetQuery = useQuery({ queryKey: ["character-sheet", id], queryFn: () => getData<SheetData>(`/api/v1/characters/${id}/sheet`), enabled: Number.isFinite(id) });
  const catalogQuery = useQuery({
    queryKey: ["item-catalog-config"],
    queryFn: () => getData<ItemCatalog>("/api/v1/items?limit=0"),
    staleTime: 5 * 60 * 1000,
  });
  const itemSearchQuery = useQuery({
    queryKey: ["item-search", deferredSearch],
    queryFn: () => getData<ItemCatalog>(`/api/v1/items?limit=50&query=${encodeURIComponent(deferredSearch)}`),
    enabled: deferredSearch.length >= 2,
    placeholderData: (previous) => previous,
  });
  const [selectedSlotId, setSelectedSlotId] = useState<string | null>(null);
  const [selectedCatalogItemId, setSelectedCatalogItemId] = useState<number | null>(null);
  const [moveSourceId, setMoveSourceId] = useState<string | null>(null);
  const [dragLabel, setDragLabel] = useState<string | null>(null);
  // The drop target follows the cursor hotspot, so drags render their own arrow at that
  // exact point: without it the browser cursor and the highlighted slot look unrelated.
  const [dragging, setDragging] = useState(false);
  const [dragPointer, setDragPointer] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [picker, setPicker] = useState<{ slot: Slot; anchor: { x: number; y: number } } | null>(null);
  const [equipChoice, setEquipChoice] = useState<{ item: Item; candidateIds: string[] } | null>(null);
  const [autocompleteOpen, setAutocompleteOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0);
  const [containerView, setContainerView] = useState<"backpack" | "quiver" | "utility" | "campaign">("backpack");
  const [storageQuantity, setStorageQuantity] = useState(1);
  const [characterValuesView, setCharacterValuesView] = useState<CharacterValuesView>("primary");
  const [overviewOpen, setOverviewOpen] = useState(false);
  const [restOpen, setRestOpen] = useState(false);
  const [effectsOpen, setEffectsOpen] = useState(false);
  const [itemEditor, setItemEditor] = useState<{ item: Item | null } | null>(null);
  const slotActionsHideTimer = useRef<ReturnType<typeof window.setTimeout> | null>(null);
  const quantitySaveTimers = useRef(new Map<string, ReturnType<typeof window.setTimeout>>());
  const [pendingQuantities, setPendingQuantities] = useState<Record<string, number>>({});

  const character = sheetQuery.data?.character;
  const catalog = catalogQuery.data;
  const allSlots = useMemo(() => character ? [
    ...character.equipment.slots,
    ...character.inventory.slots,
    ...character.quiver.slots,
    ...character.utilityContainer.slots,
    ...character.campaignContainer.slots,
  ] : [], [character]);
  const selectedSlot = allSlots.find((slot) => slot.id === selectedSlotId) || null;
  const moveSource = allSlots.find((slot) => slot.id === moveSourceId) || null;
  const searchableItems = useMemo(() => {
    const query = deferredSearch.toLocaleLowerCase("it");
    const storageItems = sheetQuery.data?.storageCatalog || [];
    return [
      ...(itemSearchQuery.data?.items || []),
      ...storageItems.filter((item) => !query || [item.name, item.description, ...item.types].some((value) => value.toLocaleLowerCase("it").includes(query))),
    ].filter((item) => !item.systemManaged);
  }, [deferredSearch, itemSearchQuery.data?.items, sheetQuery.data?.storageCatalog]);
  const selectedCatalogItem = searchableItems.find((item) => item.id === selectedCatalogItemId) || null;
  const selectedItem = selectedCatalogItem || selectedSlot?.item || null;
  // With a slot selected the catalogue is scoped to it: what fits is listed first and the rest
  // stays visible while saying, in words, why it cannot go there.
  const scopedSuggestions = useMemo(() => {
    const visible = searchableItems.slice(0, 40);
    if (!selectedSlot) return visible.slice(0, 12).map((item) => ({ item, compatible: true }));
    const decorated = visible.map((item) => ({ item, compatible: fits(item, selectedSlot) }));
    return [...decorated.filter((entry) => entry.compatible), ...decorated.filter((entry) => !entry.compatible)].slice(0, 12);
  }, [searchableItems, selectedSlot]);

  const cancelSlotActionsHide = () => {
    if (slotActionsHideTimer.current !== null) {
      window.clearTimeout(slotActionsHideTimer.current);
      slotActionsHideTimer.current = null;
    }
  };
  const scheduleSlotActionsHide = () => {
    cancelSlotActionsHide();
    const slotId = selectedSlotId;
    if (!slotId) return;
    slotActionsHideTimer.current = window.setTimeout(() => {
      setSelectedSlotId((current) => current === slotId ? null : current);
      slotActionsHideTimer.current = null;
    }, SLOT_ACTIONS_HIDE_DELAY);
  };

  useEffect(() => () => {
    cancelSlotActionsHide();
    quantitySaveTimers.current.forEach((timer) => window.clearTimeout(timer));
  }, []);
  useEffect(() => {
    if (!selectedSlotId) return;
    const closeWhenClickingOutside = (event: PointerEvent) => {
      if (shouldCloseSlotActions(event.target, selectedSlotId)) {
        cancelSlotActionsHide();
        setSelectedSlotId(null);
      }
    };
    document.addEventListener("pointerdown", closeWhenClickingOutside, true);
    return () => document.removeEventListener("pointerdown", closeWhenClickingOutside, true);
  }, [selectedSlotId]);

  const actionMutation = useMutation({
    mutationFn: ({ action, payload }: { action: string; payload: Record<string, unknown> }) => command<ActionData>(action, payload),
    onSuccess: async (result) => {
      if (result.data.character) queryClient.setQueryData<SheetData>(["character-sheet", id], (current) => current ? { ...current, character: result.data.character! } : current);
      await queryClient.invalidateQueries({ queryKey: ["creation", id] });
      if (result.data.catalog) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["item-catalog-config"] }),
          queryClient.invalidateQueries({ queryKey: ["item-search"] }),
        ]);
      }
      cancelSlotActionsHide(); setSelectedSlotId(null); setMoveSourceId(null); setItemEditor(null);
      const warning = result.warnings[0]?.message;
      notify(warning || result.events[0]?.message || "Modifica salvata.", warning ? "info" : "success");
      if (result.data.item) { setSelectedCatalogItemId(result.data.item.id); await queryClient.invalidateQueries({ queryKey: ["character-sheet", id] }); }
    },
    onError: (error: Error) => notify(error.message, "error")
  });
  const quantityMutation = useMutation({
    mutationFn: ({ slot, quantity }: { slot: Slot; quantity: number }) => command<ActionData>("inventory.setQuantity", {
      characterId: id,
      target: { group: slot.group, slot: slot.slot },
      quantity,
    }),
    onSuccess: (result, variables) => {
      if (result.data.character) updateCharacter(result.data.character);
      setPendingQuantities((current) => {
        if (current[variables.slot.id] !== variables.quantity) return current;
        const { [variables.slot.id]: _, ...remaining } = current;
        return remaining;
      });
    },
    onError: (error: Error, variables) => {
      setPendingQuantities((current) => {
        if (current[variables.slot.id] !== variables.quantity) return current;
        const { [variables.slot.id]: _, ...remaining } = current;
        return remaining;
      });
      notify(error.message, "error");
    },
  });

  useEffect(() => {
    if (!dragging) return;
    const track = (event: PointerEvent) => setDragPointer({ x: event.clientX, y: event.clientY });
    window.addEventListener("pointermove", track);
    return () => window.removeEventListener("pointermove", track);
  }, [dragging]);

  if (!Number.isFinite(id)) return <div className="page"><p>Nessun personaggio selezionato.</p><Link to="/characters">Scegli personaggio</Link></div>;
  if (sheetQuery.isLoading || catalogQuery.isLoading) return <div className="page character-loading">Caricamento della scheda…</div>;
  if (sheetQuery.error || catalogQuery.error || !character || !catalog) {
    const error = sheetQuery.error || catalogQuery.error;
    return <div className="page"><h1>Impossibile aprire la scheda</h1><p>{error instanceof Error ? error.message : "Dati non disponibili."}</p></div>;
  }

  const updateCharacter = (updated: CharacterSheet) => queryClient.setQueryData<SheetData>(["character-sheet", id], (current) => current ? { ...current, character: updated } : current);
  const slotCompatibility = (slot: Slot): "valid" | "invalid" | "neutral" => {
    if (equipChoice) return equipChoice.candidateIds.includes(slot.id) ? "valid" : "invalid";
    if (moveSource) return canSwap(moveSource, slot) ? "valid" : "invalid";
    if (selectedCatalogItem) return fits(selectedCatalogItem, slot) ? "valid" : "invalid";
    return "neutral";
  };
  const assignItemToSlot = (slot: Slot, item: Item) => {
    const metadata = item.metadata as Record<string, unknown> | undefined;
    const stockKey = typeof metadata?.storageStockKey === "string" ? metadata.storageStockKey : "";
    actionMutation.mutate({
      action: "inventory.assignItem",
      payload: {
        characterId: id,
        target: { group: slot.group, slot: slot.slot },
        itemId: stockKey ? null : item.id,
        stockKey,
        quantity: slot.stackable ? storageQuantity : 1,
      },
    });
  };
  const selectSlot = (slot: Slot) => {
    if (equipChoice) {
      if (!equipChoice.candidateIds.includes(slot.id)) return;
      const replaced = equipChoice.item;
      setEquipChoice(null);
      assignItemToSlot(slot, replaced);
      return;
    }
    if (moveSource) { if (slot.id === moveSource.id) { setMoveSourceId(null); return; } actionMutation.mutate({ action: "inventory.swapItems", payload: { characterId: id, source: { group: moveSource.group, slot: moveSource.slot }, target: { group: slot.group, slot: slot.slot } } }); return; }
    cancelSlotActionsHide();
    setSelectedSlotId((current) => current === slot.id ? null : slot.id);
  };
  const equipSelectedItem = (slot: Slot) => {
    if (!selectedCatalogItem) {
      notify("Seleziona prima un oggetto dalla ricerca.", "info");
      return;
    }
    assignItemToSlot(slot, selectedCatalogItem);
  };
  /**
   * "Equipaggia" resolves its own destination: the first free compatible slot wins, a single
   * compatible slot is replaced outright, and only a real tie hands the choice back to the player.
   */
  const equipAutomatically = (item: Item) => {
    const resolution = resolveEquipTarget(item, character.equipment.slots);
    if (resolution.kind === "assign") { assignItemToSlot(resolution.slot, item); return; }
    if (resolution.kind === "choose") {
      setEquipChoice({ item, candidateIds: resolution.candidates.map((slot) => slot.id) });
      cancelSlotActionsHide();
      setSelectedSlotId(null);
      return;
    }
    notify(`${item.name} non ha uno slot compatibile: usa uno Slot extra o lo zaino.`, "info");
  };
  const stashItem = (item: Item) => {
    const target = firstFreeSlot(item, character.inventory.slots);
    if (!target) { notify("Lo zaino è pieno: libera uno spazio prima di aggiungere altro.", "info"); return; }
    assignItemToSlot(target, item);
  };
  const emptySlot = (slot: Slot) => actionMutation.mutate({
    action: "inventory.assignItem",
    payload: { characterId: id, target: { group: slot.group, slot: slot.slot }, itemId: null },
  });
  const changeSlotQuantity = (slot: Slot, delta: -1 | 1) => {
    const currentQuantity = pendingQuantities[slot.id] ?? slot.quantity;
    const quantity = Math.max(0, Math.min(9999, currentQuantity + delta));
    if (quantity === currentQuantity) return;
    const existingTimer = quantitySaveTimers.current.get(slot.id);
    if (existingTimer) window.clearTimeout(existingTimer);
    setPendingQuantities((current) => ({ ...current, [slot.id]: quantity }));
    quantitySaveTimers.current.set(slot.id, window.setTimeout(() => {
      quantitySaveTimers.current.delete(slot.id);
      quantityMutation.mutate({ slot, quantity });
    }, 1000));
  };
  const changeSlotQuantityImmediately = (slot: Slot, delta: -1 | 1) => actionMutation.mutate({
    action: "inventory.setQuantity",
    payload: { characterId: id, target: { group: slot.group, slot: slot.slot }, quantity: Math.max(0, Math.min(9999, slot.quantity + delta)) },
  });
  // Choosing arms the item without overwriting the query, so the same search can fill several
  // slots: focusing the field again reopens the very same list.
  const chooseCatalogItem = (item: Item) => {
    setSelectedCatalogItemId(item.id);
    setAutocompleteOpen(false);
    setActiveSuggestionIndex(0);
  };
  const dragStart = (event: DragStartEvent) => {
    const activator = event.activatorEvent as PointerEvent | undefined;
    if (activator && "clientX" in activator) setDragPointer({ x: activator.clientX, y: activator.clientY });
    setDragging(true);
    const catalogItem = event.active.data.current?.catalogItem as Item | undefined;
    if (catalogItem) {
      setSelectedCatalogItemId(catalogItem.id);
      setDragLabel(catalogItem.name);
      return;
    }
    const source = event.active.data.current?.slot as Slot | undefined;
    setDragLabel(source?.item?.name || null);
    setMoveSourceId(source?.id || null);
  };
  const dragEnd = (event: DragEndEvent) => {
    setDragging(false);
    setDragLabel(null);
    setMoveSourceId(null);
    const target = event.over?.data.current?.slot as Slot | undefined;
    if (!target) return;
    const catalogItem = event.active.data.current?.catalogItem as Item | undefined;
    if (catalogItem) {
      if (!fits(catalogItem, target)) { notify(`${catalogItem.name} non può essere messo in ${target.label}.`, "info"); return; }
      assignItemToSlot(target, catalogItem);
      return;
    }
    const source = event.active.data.current?.slot as Slot | undefined;
    if (source && source.id !== target.id) actionMutation.mutate({ action: "inventory.swapItems", payload: { characterId: id, source: { group: source.group, slot: source.slot }, target: { group: target.group, slot: target.slot } } });
  };
  const suggestions = scopedSuggestions.map((entry) => entry.item);
  const visibleContainer = {
    backpack: character.inventory,
    quiver: character.quiver,
    utility: character.utilityContainer,
    campaign: character.campaignContainer,
  }[containerView];
  const containerSlots = visibleContainer.slots
    .map((slot) => pendingQuantities[slot.id] == null ? slot : { ...slot, quantity: pendingQuantities[slot.id] })
    .filter((slot) => !slot.isLocked)
    .sort((left, right) => Number(right.isMagical) - Number(left.isMagical) || Number(left.slot) - Number(right.slot));
  const characteristicModifiers = Object.fromEntries(character.diceModifiers.map((stat) => [stat.key.replace(/^mod_/, ""), stat.value]));
  const quickStats = character.combat.filter((stat) => stat.key === "stanchezza" || stat.key === "modificatore_generale");
  const actionPoints = character.combat.find((stat) => stat.key === "pa");
  const actionPointsMaximum = actionPoints?.value ?? 0;
  const actionPointsTooltipId = "action-points-maximum-calculation";

  const openPicker = (slot: Slot, anchor: { x: number; y: number }) => {
    setEquipChoice(null);
    setPicker({ slot, anchor });
  };

  // pointerWithin resolves the drop by the cursor hotspot alone, matching the arrow the drag
  // renders: overlapping figure slots no longer steal a drop from the slot under the tip.
  return <DndContext sensors={sensors} collisionDetection={pointerWithin} onDragStart={dragStart} onDragEnd={dragEnd} onDragCancel={() => { setDragging(false); setDragLabel(null); setMoveSourceId(null); }}>
    <div className="page character-page">
      <header className="character-hud" data-component-type="toolbar" data-theme="default">
        <div className="character-identity">
          <h1>{character.name}</h1>
          <p><span>{character.races.join(" / ") || "Razza sconosciuta"}</span><span>Livello {character.level}</span><span>{character.age ?? "—"} anni</span></p>
        </div>
        <section className="character-resource-section" aria-label="Risorse del personaggio">
          <div className="resource-toolbar"><div className="quick-stat-grid">{quickStats.map((stat) => <QuickStatControl key={stat.key} characterId={id} stat={stat} onUpdate={updateCharacter} />)}</div><div className="hud-actions"><button className="button primary" onClick={() => setRestOpen(true)}>Riposa</button><button className="button secondary" onClick={() => setOverviewOpen(true)}>Modifica</button></div></div>
          <div className="resource-grid">{character.resources.map((resource) => <ResourceControl key={resource.key} characterId={id} resource={resource} onUpdate={updateCharacter} />)}<div className="action-points-maximum" tabIndex={0} aria-describedby={actionPoints ? actionPointsTooltipId : undefined} aria-label={`Punti Azione massimi: ${actionPointsMaximum}. Mostra il calcolo.`}><span>PA max</span><strong>{actionPointsMaximum}</strong>{actionPoints && <CalculationTooltip id={actionPointsTooltipId} calculation={actionPoints.calculation} total={actionPoints.value} totalLabel="Massimo" />}</div></div>
        </section>
      </header>
      {moveSource && <div className="interaction-banner"><strong>{`Scegli la destinazione di ${moveSource.item?.name}`}</strong><span>Gli spazi compatibili sono evidenziati.</span><button onClick={() => setMoveSourceId(null)}>Annulla</button></div>}
      {equipChoice && <div className="interaction-banner" data-theme="gold"><strong>{`Quale slot vuoi sostituire con ${equipChoice.item.name}?`}</strong><span>Sono tutti occupati: gli slot evidenziati sono compatibili e quello scelto manda il suo oggetto nello zaino.</span><button onClick={() => setEquipChoice(null)}>Annulla</button></div>}

      <div className={`items-effects-stage ${effectsOpen ? "effects-open" : ""}`} data-component-type="workspace" data-theme="dark">
      <div className="items-stage-object">
      <button className="objects-spine" type="button" onClick={() => setEffectsOpen(false)} aria-label="Torna a equipaggiamento e inventario"><span>OGGETTI</span></button>
      <section className="items-workspace panel"><header className="panel-header"><div><p className="eyebrow">Oggetti</p><h2>Equipaggiamento e inventario</h2></div><div className="button-row">{character.permissions.canManageItems && <button className="button secondary" onClick={() => setItemEditor({ item: null })}>Crea oggetto</button>}</div></header><div className="items-columns">
        <section className="equipment-column"><CharacterEquipment character={character} selectedSlotId={selectedSlotId} moveSourceId={moveSourceId} equipItem={selectedCatalogItem} actionPending={actionMutation.isPending} compatibility={slotCompatibility} onSelect={selectSlot} onMoveStart={(entry) => setMoveSourceId((current) => current === entry.id ? null : entry.id)} onEquip={equipSelectedItem} onEmpty={emptySlot} onPick={openPicker} onSwitchPrimary={() => actionMutation.mutate({ action: "equipment.switchPrimaryWeapon", payload: { characterId: id } })} onActionsEnter={cancelSlotActionsHide} onActionsLeave={scheduleSlotActionsHide} coinsControl={<CarriedCoinsControl character={character} onUpdate={updateCharacter} />} /></section>
        <section className="container-column">
          <div className="container-tabs">
            <button className={containerView === "backpack" ? "active" : ""} onClick={() => setContainerView("backpack")}>Zaino <span>{character.inventory.occupied}/{character.inventory.capacity}{character.inventory.magicalSlots > 0 ? ` (${character.inventory.magicalSlots} magici)` : ""}</span></button>
            <button className={containerView === "quiver" ? "active" : ""} onClick={() => setContainerView("quiver")}>Faretra <span>{character.quiver.occupied}/{character.quiver.capacity}</span></button>
            <button className={containerView === "utility" ? "active" : ""} onClick={() => setContainerView("utility")}><span className="container-tab-label container-tab-label-compact">Alchimia&Contenitori</span><span>{character.utilityContainer.occupied}/{character.utilityContainer.capacity}</span></button>
            <button className={containerView === "campaign" ? "active" : ""} disabled={!character.campaignContainer.available} onClick={() => setContainerView("campaign")}>Risorse gruppo <span>{character.campaignContainer.available ? `${character.campaignContainer.occupied}/${character.campaignContainer.capacity}` : "senza campagna"}</span></button>
          </div>
          {containerView === "quiver" && <div className="capacity-note"><strong>Capacità dai contenitori equipaggiati</strong><span>Solo frecce, dardi e proiettili.</span></div>}
          {(containerView === "utility" || containerView === "campaign") && <div className="capacity-note"><strong>{visibleContainer.shared ? "Condiviso con la campagna" : "Alchimia, pozioni e pergamene"}</strong><span>Le pile occupano uno spazio e il peso non viene conteggiato.</span></div>}
          <div className="container-grid">{containerView === "campaign" && <SharedCoinsCard character={character} onUpdate={updateCharacter} />}{containerSlots.map((slot) => <CharacterSlot key={slot.id} slot={slot} selected={selectedSlotId === slot.id} moveSource={moveSourceId === slot.id} compatibility={slotCompatibility(slot)} equipItem={selectedCatalogItem} actionsVisible={selectedSlotId === slot.id} actionPending={actionMutation.isPending} onSelect={selectSlot} onMoveStart={(entry) => setMoveSourceId((current) => current === entry.id ? null : entry.id)} onEquip={equipSelectedItem} onEmpty={emptySlot} onPick={openPicker} onQuantityChange={containerView === "utility" || containerView === "campaign" ? changeSlotQuantity : changeSlotQuantityImmediately} onActionsEnter={cancelSlotActionsHide} onActionsLeave={scheduleSlotActionsHide} />)}</div>
        </section>
        <aside className="item-inspector">
          <h3>Ricerca Oggetto</h3>
          <div
            className="item-autocomplete"
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setAutocompleteOpen(false);
            }}
          >
            <label className="sr-only" htmlFor="character-item-search">Ricerca Oggetto</label>
            <div className="item-search-row">
              <input
              id="character-item-search"
              className="search-input"
              type="text"
              role="combobox"
              autoComplete="off"
              aria-autocomplete="list"
              aria-expanded={autocompleteOpen && search.trim().length > 0}
              aria-controls="character-item-suggestions"
              aria-activedescendant={autocompleteOpen && suggestions[activeSuggestionIndex] ? `character-item-suggestion-${suggestions[activeSuggestionIndex].id}` : undefined}
              placeholder="Inizia a digitare il nome…"
              value={search}
              onFocus={() => search.trim() && setAutocompleteOpen(true)}
              onChange={(event) => {
                const value = event.target.value;
                setSearch(value);
                setAutocompleteOpen(value.trim().length > 0);
                setActiveSuggestionIndex(0);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  setAutocompleteOpen(false);
                  return;
                }
                if (!autocompleteOpen || suggestions.length === 0) return;
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveSuggestionIndex((current) => (current + 1) % suggestions.length);
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveSuggestionIndex((current) => (current - 1 + suggestions.length) % suggestions.length);
                } else if (event.key === "Enter") {
                  event.preventDefault();
                  chooseCatalogItem(suggestions[activeSuggestionIndex] || suggestions[0]);
                }
              }}
              />
              <button
                type="button"
                className="button secondary small item-search-clear"
                disabled={!search && !selectedCatalogItemId}
                onClick={() => {
                  setSearch("");
                  setSelectedCatalogItemId(null);
                  setAutocompleteOpen(false);
                  setActiveSuggestionIndex(0);
                }}
              >Svuota</button>
            </div>
            {(containerView === "utility" || containerView === "campaign") && <label className="storage-quantity">Quantità da inserire<input type="number" min={1} max={9999} value={storageQuantity} onChange={(event) => setStorageQuantity(Math.max(1, Math.min(9999, Number(event.target.value) || 1)))} /></label>}
            {autocompleteOpen && search.trim().length > 0 && <div id="character-item-suggestions" className="catalog-results autocomplete-results" role="listbox">
              {scopedSuggestions.length > 0
                ? scopedSuggestions.map((entry, index) => <CatalogSuggestion
                    key={entry.item.id}
                    item={entry.item}
                    compatible={entry.compatible}
                    selected={selectedCatalogItem?.id === entry.item.id}
                    keyboardActive={activeSuggestionIndex === index}
                    reason={selectedSlot ? `Non compatibile con ${selectedSlot.label}` : ""}
                    onHover={() => setActiveSuggestionIndex(index)}
                    onChoose={() => chooseCatalogItem(entry.item)}
                  />)
                : <p className="autocomplete-empty">Nessun oggetto trovato.</p>}
            </div>}
          </div>
          {selectedCatalogItem && <div className="selected-item-hint" data-retain-slot-selection="" onPointerEnter={cancelSlotActionsHide}>
            <strong>{selectedCatalogItem.name}</strong>
            <div className="selected-item-actions">
              <button type="button" className="button primary small" disabled={actionMutation.isPending} onClick={() => equipAutomatically(selectedCatalogItem)}>Equipaggia</button>
              <button type="button" className="button secondary small" disabled={actionMutation.isPending} onClick={() => stashItem(selectedCatalogItem)}>Nello zaino</button>
            </div>
            <span>Oppure trascinalo su uno slot, o apri il menu di uno slot col tasto destro.</span>
          </div>}
          {selectedItem ? <div className="item-detail" data-retain-slot-selection="" onPointerEnter={cancelSlotActionsHide}><p className="eyebrow">{selectedItem.types.join(" / ")}</p><h3>{selectedItem.name}</h3>{selectedItem.imageUrl && <img src={selectedItem.imageUrl} alt={selectedItem.name} />}<p>{selectedItem.description || "Nessuna descrizione."}</p><dl><div><dt>Peso</dt><dd>{selectedItem.weight ?? 0}</dd></div><div><dt>Valore</dt><dd>{selectedItem.value ?? 0}</dd></div><div><dt>Rarità</dt><dd>{selectedItem.rarityLabel || "—"}</dd></div><div><dt>Loot</dt><dd>{selectedItem.lootLevel || "—"}</dd></div></dl>{selectedItem.effectSummaries.length > 0 && <div className="item-effects"><strong>Effetti</strong>{selectedItem.effectSummaries.map((effect, index) => <span key={index}>{effect.text}</span>)}</div>}{selectedItem.specialRules?.trim() && <div className="item-special-rules"><strong>Regole speciali</strong><p>{selectedItem.specialRules}</p></div>}<div className="inspector-actions">{character.permissions.canManageItems && <button className="button secondary small" data-retain-slot-selection="" onClick={() => setItemEditor({ item: selectedItem })}>Modifica oggetto</button>}</div></div> : <p className="empty-copy">Cerca un oggetto oppure seleziona uno slot.</p>}
        </aside>
      </div></section>
      </div>
      <CharacterEffectsWorkspace
        characterId={id}
        effects={character.effects}
        configuration={sheetQuery.data!.effectConfiguration}
        open={effectsOpen}
        saving={actionMutation.isPending}
        onOpenChange={setEffectsOpen}
        onAction={(action, payload) => actionMutation.mutateAsync({ action, payload })}
      />
      </div>

      <section className="overview-effects-grid">
        <article className="panel overview-panel">
          <header className="panel-header values-panel-header">
            <div><p className="eyebrow">Panoramica</p><h2>Valori del personaggio</h2></div>
            <div className="values-panel-tools">
              <EncumbranceSummary encumbrance={character.encumbrance} />
              <div className="equipment-view-switch character-values-switch" role="tablist" aria-label="Pagine dei valori" data-component-type="tabset" data-theme="dark">
                <button type="button" role="tab" aria-selected={characterValuesView === "primary"} aria-controls="character-values-primary" className={characterValuesView === "primary" ? "active" : ""} onClick={() => setCharacterValuesView("primary")}>Principali</button>
                <button type="button" role="tab" aria-selected={characterValuesView === "advanced"} aria-controls="character-values-advanced" className={characterValuesView === "advanced" ? "active" : ""} onClick={() => setCharacterValuesView("advanced")}>Altri valori</button>
              </div>
            </div>
          </header>
          {characterValuesView === "primary" ? <div id="character-values-primary" role="tabpanel" className="stat-groups">
            <div><h3>Caratteristiche</h3><StatList stats={character.characteristics} modifiers={characteristicModifiers} /></div>
            <div><h3>Combattimento</h3><StatList stats={character.combat} /></div>
            <div><h3>Resistenze</h3><StatList stats={character.resistances} compact /></div>
          </div> : <div id="character-values-advanced" role="tabpanel" className="advanced-stat-groups">
            {character.valueGroups.map((group) => <section key={group.key} data-value-group={group.key}>
              <h3>{group.label}</h3>
              <StatList stats={group.values} />
            </section>)}
            <ReagentSummary reagents={character.reagents} />
          </div>}
        </article>
      </section>

    </div>
    <DragOverlay>{dragLabel ? <div className="drag-overlay">{dragLabel}</div> : null}</DragOverlay>
    {dragging && createPortal(<div className="drag-cursor" style={{ left: dragPointer.x, top: dragPointer.y }} aria-hidden="true">
      <svg viewBox="0 0 14 22" width={22} height={34}><path d="M14 0 L14 18 L9 13.6 L6 20.6 L2.6 19 L5.7 12.3 L0 12.3 Z" /></svg>
    </div>, document.body)}
    {picker && <SlotItemPicker
      slot={picker.slot}
      anchor={picker.anchor}
      catalog={catalog}
      storageCatalog={sheetQuery.data?.storageCatalog || []}
      pending={actionMutation.isPending}
      onPick={(item) => { assignItemToSlot(picker.slot, item); setPicker(null); }}
      onEmpty={() => { emptySlot(picker.slot); setPicker(null); }}
      onClose={() => setPicker(null)}
    />}
    {overviewOpen && <OverviewModal character={character} raceConfiguration={sheetQuery.data!.raceConfiguration} saving={actionMutation.isPending} onClose={() => setOverviewOpen(false)} onSave={(values) => actionMutation.mutate({ action: "character.updateOverview", payload: { characterId: id, values } }, { onSuccess: () => setOverviewOpen(false) })} />}
    {restOpen && <Modal surface="character-rest" title="Riposa" onClose={() => setRestOpen(false)} footer={<><button className="button secondary" onClick={() => setRestOpen(false)}>Annulla</button><button className="button primary" type="submit" form="rest-form">Conferma riposo</button></>}><form id="rest-form" className="stacked-form" onSubmit={(event) => { event.preventDefault(); const recovery = Number(new FormData(event.currentTarget).get("recovery")); actionMutation.mutate({ action: "character.rest", payload: { characterId: id, fatigueRecovery: recovery } }, { onSuccess: () => setRestOpen(false) }); }}><p>Il riposo recupera PF, Mana e Potere. Recupera Stanchezza fino al numero scelto, partendo da quella accumulata e poi dagli effetti attivi; Energia torna al massimo solo se la Stanchezza ha raggiunto il minimo e resta recupero disponibile.</p><label>Recupero stanchezza<input name="recovery" type="number" min={0} max={5} defaultValue={1} /></label></form></Modal>}
    {itemEditor && <ItemEditorModal item={itemEditor.item} catalog={catalog} media={media} saving={actionMutation.isPending} onClose={() => setItemEditor(null)} onSave={(values) => actionMutation.mutate({ action: itemEditor.item ? "items.update" : "items.create", payload: { itemId: itemEditor.item?.id, values } })} onArchive={itemEditor.item ? () => { if (window.confirm(`Archiviare ${itemEditor.item!.name}? L'oggetto non apparirà più nel catalogo, ma resterà negli inventari esistenti.`)) actionMutation.mutate({ action: "items.archive", payload: { itemId: itemEditor.item!.id } }); } : undefined} />}
  </DndContext>;
}
