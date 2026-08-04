import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { ImagePickerModal } from "../../components/ImagePickerModal";
import { ItemSpecialIconField } from "../../components/ItemSpecialIconField";
import { ItemEditorModal } from "../character/ItemEditorModal";
import { MasterAIAssistButton } from "../master-ai/launchers";
import { command, getData } from "../../lib/api";
import type { Item, ItemCatalog } from "../../lib/types";
import { ItemBulkEditor } from "./ItemBulkEditor";

type ItemActionData = {
  item?: Item | null;
  catalog?: ItemCatalog | null;
  management?: { created?: boolean; updated?: number; checked?: number; cleared?: number; stillSpecial?: number } | null;
};
type ItemDraft = {
  identityId: number | null;
  identityName: string;
  nome: string;
  modello: boolean;
  temporaneo: boolean;
  archiviato: boolean;
  speciale: boolean;
  numero_ordine: string;
  icona: string;
  tipo_1: string;
  tipo_2: string;
  tipo_3: string;
  tipo_4: string;
  descrizione: string;
  valore: string;
  peso: string;
  rarita: string;
  lv_loot: string;
  regione_loot: string;
  peso_regione: string;
  tipoArmaId: string;
  pa_per_attacco: string;
  elderEffects: string[];
  regole_speciali: string;
  effects: string;
  mediaId: string;
};

const EMPTY_DRAFT: ItemDraft = {
  identityId: null, identityName: "", nome: "", modello: true, temporaneo: false, archiviato: false, speciale: false,
  numero_ordine: "", icona: "", tipo_1: "", tipo_2: "", tipo_3: "", tipo_4: "",
  descrizione: "", valore: "", peso: "", rarita: "", lv_loot: "", regione_loot: "", peso_regione: "",
  tipoArmaId: "", pa_per_attacco: "", elderEffects: Array(8).fill(""), regole_speciali: "", effects: "[]", mediaId: "",
};

function draftFromItem(item: Item): ItemDraft {
  return {
    identityId: item.id,
    identityName: item.name,
    nome: item.name,
    modello: item.model ?? true,
    temporaneo: item.temporary ?? false,
    archiviato: item.archived,
    speciale: item.special,
    numero_ordine: item.order == null ? "" : String(item.order),
    icona: item.icon,
    tipo_1: item.typeValues?.[0] || item.types[0] || "",
    tipo_2: item.typeValues?.[1] || item.types[1] || "",
    tipo_3: item.typeValues?.[2] || item.types[2] || "",
    tipo_4: item.typeValues?.[3] || item.types[3] || "",
    descrizione: item.description,
    valore: item.value == null ? "" : String(item.value),
    peso: item.weight == null ? "" : String(item.weight),
    rarita: item.rarity == null ? "" : String(item.rarity),
    lv_loot: item.lootLevel,
    regione_loot: item.region,
    peso_regione: item.regionWeight == null ? "" : String(item.regionWeight),
    tipoArmaId: item.weaponTypeId == null ? "" : String(item.weaponTypeId),
    pa_per_attacco: item.actionPointCost == null ? "" : String(item.actionPointCost),
    elderEffects: [...(item.elderEffects || []), "", "", "", "", "", "", "", ""].slice(0, 8),
    regole_speciali: item.specialRules || "",
    effects: JSON.stringify(item.effects || [], null, 2),
    mediaId: item.mediaId == null ? "" : String(item.mediaId),
  };
}

function valuesFromDraft(draft: ItemDraft): Record<string, unknown> {
  return {
    nome: draft.nome.trim(), modello: draft.modello, temporaneo: draft.temporaneo, archiviato: draft.archiviato, speciale: draft.speciale,
    numero_ordine: draft.numero_ordine || null, icona: draft.icona,
    tipo_1: draft.tipo_1, tipo_2: draft.tipo_2, tipo_3: draft.tipo_3, tipo_4: draft.tipo_4,
    descrizione: draft.descrizione, valore: draft.valore || null, peso: draft.peso || null, rarita: draft.rarita || null,
    lv_loot: draft.lv_loot, regione_loot: draft.regione_loot, peso_regione: draft.peso_regione || null,
    tipoArmaId: draft.tipoArmaId || null, pa_per_attacco: draft.pa_per_attacco || null,
    ...Object.fromEntries(draft.elderEffects.map((value, index) => [`effetto_${index + 1}`, value.trim()])),
    regole_speciali: draft.regole_speciali,
    effects: JSON.parse(draft.effects || "[]"),
    mediaId: draft.mediaId || null,
  };
}

function shortValue(value: unknown): string {
  if (value === true) return "Sì";
  if (value === false) return "No";
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.length ? JSON.stringify(value) : "Nessuno";
  if (typeof value === "object") return Object.keys(value as object).length ? JSON.stringify(value) : "Nessuno";
  return String(value);
}

function CompareRow({ label, left, children, wide = false }: { label: string; left: unknown; children: ReactNode; wide?: boolean }) {
  return <div className={`compare-row${wide ? " wide" : ""}`}><strong>{label}</strong><div className="compare-source">{shortValue(left)}</div><div className="compare-target">{children}</div></div>;
}

function ItemComparer({ catalog, onSaved }: { catalog: ItemCatalog; onSaved: (item: Item, created: boolean) => void }) {
  const { media, notify } = useApp();
  const [leftId, setLeftId] = useState<number | null>(catalog.items[0]?.id || null);
  const [right, setRight] = useState<ItemDraft>(() => catalog.items[1] ? draftFromItem(catalog.items[1]) : { ...EMPTY_DRAFT });
  const [error, setError] = useState("");
  const [imagePickerOpen, setImagePickerOpen] = useState(false);
  const left = catalog.items.find((item) => item.id === leftId) || null;
  useEffect(() => {
    if (leftId && !catalog.items.some((item) => item.id === leftId)) setLeftId(catalog.items[0]?.id || null);
  }, [catalog.items, leftId]);
  const mutation = useMutation({
    mutationFn: () => command<ItemActionData>("items.compareSave", {
      itemId: right.identityId,
      identityName: right.identityName,
      values: valuesFromDraft(right),
    }, "management-items"),
    onSuccess: (response) => {
      if (response.data.item) {
        const created = Boolean(response.data.management?.created);
        onSaved(response.data.item, created);
        setRight(draftFromItem(response.data.item));
        setError("");
        notify(created ? "Nuovo oggetto creato dal confronto." : "Oggetto aggiornato dal confronto.");
      }
    },
    onError: (caught: Error) => { setError(caught.message); notify(caught.message, "error"); },
  });
  const update = <K extends keyof ItemDraft>(key: K, value: ItemDraft[K]) => setRight((current) => ({ ...current, [key]: value }));
  const selectRight = (value: string) => {
    const item = catalog.items.find((entry) => entry.id === Number(value));
    setRight(item ? draftFromItem(item) : { ...EMPTY_DRAFT });
    setError("");
  };
  const copyLeft = () => {
    if (!left) return;
    const copied = draftFromItem(left);
    if (right.identityId) {
      setRight({ ...copied, identityId: right.identityId, identityName: right.identityName });
    } else {
      setRight({ ...copied, identityId: null, identityName: "" });
    }
  };
  const leftTypes = left?.types || [];
  const leftWeapon = catalog.weaponTypes.find((weapon) => weapon.id === left?.weaponTypeId)?.name || "";
  const leftMedia = media.find((asset) => asset.id === left?.mediaId)?.title || "";
  const rightMedia = media.find((asset) => asset.id === Number(right.mediaId)) || null;
  const save = () => {
    try {
      valuesFromDraft(right);
      mutation.mutate();
    } catch (caught) {
      setError(caught instanceof Error ? `JSON non valido: ${caught.message}` : "Controlla i dati strutturati.");
    }
  };

  return <><section className="item-comparer" data-component-type="panel" data-theme="default">
    <div className="callout guide-warning legacy-tool-notice" role="note">
      <strong>Strumento storico, non più il modo normale di lavorare</strong>
      <p>
        Il confronto affiancato è nato per la migrazione da Elder Django: serviva a mettere una riga importata
        accanto a una già sistemata e ricopiarne i valori campo per campo. Oggi il catalogo si modifica dalla
        scheda <em>Catalogo</em>, con l'editor completo.
      </p>
      <p>
        Resta qui perché è ancora comodo per allineare due record simili, ma copre solo i campi che esistevano
        allora: non tocca il profilo arma e carica l'intero catalogo in memoria. Per creare o modificare un
        oggetto usa <em>Crea oggetto</em> o <em>Modifica</em>.
      </p>
    </div>
    <header className="comparer-toolbar"><div><p className="eyebrow">Confronto affiancato</p><h2>Sinistra: riferimento · Destra: destinazione</h2></div><div className="button-row"><button className="button secondary" type="button" onClick={() => { setRight({ ...EMPTY_DRAFT }); setError(""); }}>Nuovo oggetto</button><button className="button secondary" type="button" disabled={!left} onClick={copyLeft}>Copia i valori →</button></div></header>
    <div className="comparer-selectors"><label>Oggetto a sinistra<select value={leftId || ""} onChange={(event) => setLeftId(Number(event.target.value) || null)}>{catalog.items.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.name}</option>)}</select></label><label>Oggetto o bozza a destra<select value={right.identityId || ""} onChange={(event) => selectRight(event.target.value)}><option value="">Nuovo oggetto</option>{catalog.items.map((item) => <option key={item.id} value={item.id}>#{item.id} · {item.name}</option>)}</select></label></div>
    <div className="identity-rule" data-state={right.identityId && right.nome.toLocaleLowerCase("it") === right.identityName.toLocaleLowerCase("it") ? "update" : "create"}>
      <strong>{right.identityId && right.nome.toLocaleLowerCase("it") === right.identityName.toLocaleLowerCase("it") ? `Aggiornamento #${right.identityId}` : "Creazione nuovo oggetto"}</strong>
      <span>Il confronto aggiorna solo quando ID e nome restano quelli della destinazione. Con un nome diverso crea un nuovo record; i nomi duplicati sono sempre bloccati.</span>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div className="compare-grid" aria-label="Campi a confronto">
      <div className="compare-head"><span>Campo</span><strong>Sinistra</strong><strong>Destra modificabile</strong></div>
      <h3>Identità</h3>
      <CompareRow label="ID" left={left?.id}>{right.identityId || "Nuovo"}</CompareRow>
      <CompareRow label="Nome" left={left?.name}><input value={right.nome} onChange={(event) => update("nome", event.target.value)} required /></CompareRow>
      <CompareRow label="Icona" left={left?.icon}><input value={right.icona} onChange={(event) => update("icona", event.target.value)} /></CompareRow>
      <CompareRow label="Ordine" left={left?.order}><input type="number" value={right.numero_ordine} onChange={(event) => update("numero_ordine", event.target.value)} /></CompareRow>
      <CompareRow label="Modello" left={left?.model}><input type="checkbox" checked={right.modello} onChange={(event) => update("modello", event.target.checked)} /></CompareRow>
      <CompareRow label="Temporaneo" left={left?.temporary}><input type="checkbox" checked={right.temporaneo} onChange={(event) => update("temporaneo", event.target.checked)} /></CompareRow>
      <CompareRow label="Archiviato" left={left?.archived}><input type="checkbox" checked={right.archiviato} onChange={(event) => update("archiviato", event.target.checked)} /></CompareRow>
      <CompareRow label="Speciale" left={left?.special}><input type="checkbox" checked={right.speciale} onChange={(event) => update("speciale", event.target.checked)} /></CompareRow>
      <CompareRow label="Descrizione" left={left?.description} wide><textarea rows={4} value={right.descrizione} onChange={(event) => update("descrizione", event.target.value)} /></CompareRow>
      <h3>Classificazione</h3>
      {[1, 2, 3, 4].map((index) => {
        const key = `tipo_${index}` as keyof ItemDraft;
        const current = String(right[key]);
        const options = catalog.typeOptions.filter((option) => option.position === index);
        return <CompareRow key={key} label={`Tipo ${index}`} left={left?.typeValues?.[index - 1] || leftTypes[index - 1]}><select value={current} onChange={(event) => update(key, event.target.value as never)}><option value="">Nessuno</option>{current && !options.some((option) => option.value === current) && <option value={current}>{current} · non configurato</option>}{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></CompareRow>;
      })}
      <CompareRow label="Tipo arma" left={leftWeapon}><select value={right.tipoArmaId} onChange={(event) => update("tipoArmaId", event.target.value)}><option value="">Nessuno</option>{catalog.weaponTypes.map((weapon) => <option key={weapon.id} value={weapon.id}>{weapon.name}</option>)}</select></CompareRow>
      <h3>Economia, peso e loot</h3>
      <CompareRow label="Valore" left={left?.value}><input type="number" min="0" value={right.valore} onChange={(event) => update("valore", event.target.value)} /></CompareRow>
      <CompareRow label="Peso" left={left?.weight}><input type="number" min="0" step="0.01" value={right.peso} onChange={(event) => update("peso", event.target.value)} /></CompareRow>
      <CompareRow label="Rarità" left={left?.rarityLabel || left?.rarity}><select value={right.rarita} onChange={(event) => update("rarita", event.target.value)}><option value="">Non specificata</option>{catalog.rarityChoices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select></CompareRow>
      <CompareRow label="Livello loot" left={left?.lootLevel}><input value={right.lv_loot} onChange={(event) => update("lv_loot", event.target.value)} /></CompareRow>
      <CompareRow label="Regione" left={left?.region}><input value={right.regione_loot} onChange={(event) => update("regione_loot", event.target.value)} /></CompareRow>
      <CompareRow label="Peso regione" left={left?.regionWeight}><input type="number" min="0" step="0.1" value={right.peso_regione} onChange={(event) => update("peso_regione", event.target.value)} /></CompareRow>
      <CompareRow label="PA per attacco" left={left?.actionPointCost}><input type="number" min="0" value={right.pa_per_attacco} onChange={(event) => update("pa_per_attacco", event.target.value)} /></CompareRow>
      <h3>Effetti Elder conservati</h3>
      {right.elderEffects.map((value, index) => <CompareRow key={index} label={`Effetto ${index + 1}`} left={left?.elderEffects?.[index]} wide><textarea rows={2} maxLength={255} value={value} onChange={(event) => update("elderEffects", right.elderEffects.map((entry, effectIndex) => effectIndex === index ? event.target.value : entry))} /></CompareRow>)}
      <CompareRow label="Regole speciali" left={left?.specialRules} wide><textarea rows={4} value={right.regole_speciali} onChange={(event) => update("regole_speciali", event.target.value)} /></CompareRow>
      <h3>Dati strutturati</h3>
      <CompareRow label="Effetti" left={left?.effects} wide><textarea className="code-input" rows={8} value={right.effects} onChange={(event) => update("effects", event.target.value)} spellCheck={false} /></CompareRow>
      <h3>Media</h3>
      <CompareRow label="Immagine" left={leftMedia}><button className="media-picker-trigger compact" type="button" onClick={() => setImagePickerOpen(true)}>{rightMedia ? <><img src={rightMedia.thumbnailUrl || rightMedia.url} alt="" /><span>{rightMedia.title}</span></> : "Scegli dall'archivio"}</button></CompareRow>
      <CompareRow label="Icona dedicata" left={left?.imageUrl} wide><ItemSpecialIconField itemId={right.identityId} itemName={right.nome} imageUrl={catalog.items.find((item) => item.id === right.identityId)?.imageUrl || ""} /></CompareRow>
    </div>
    <div className="sticky-actions"><button className="button primary" type="button" disabled={mutation.isPending || !right.nome.trim()} onClick={save}>{right.identityId && right.nome.toLocaleLowerCase("it") === right.identityName.toLocaleLowerCase("it") ? "Aggiorna destinazione" : "Crea nuovo oggetto"}</button></div>
  </section>{imagePickerOpen && <ImagePickerModal selectedId={rightMedia?.id || null} usageType="item_icon" defaultGroup="Oggetti" defaultTitle={right.nome || "Nuovo oggetto"} onSelect={(asset) => update("mediaId", asset ? String(asset.id) : "")} onClose={() => setImagePickerOpen(false)} />}</>;
}

// The comparer predates paging and drives both of its dropdowns from one
// in-memory list. It keeps its own unpaged query so the catalogue tab can page
// properly without changing how the legacy tool behaves.
function LegacyComparerTab({ onSaved }: { onSaved: (item: Item, created: boolean) => void }) {
  const comparerQuery = useQuery({
    queryKey: ["management-items-comparer"],
    queryFn: () => getData<ItemCatalog>("/api/v1/management/items?limit=10000"),
  });
  const queryClient = useQueryClient();
  if (comparerQuery.isLoading) return <section className="panel"><p>Caricamento dell'intero catalogo…</p></section>;
  if (comparerQuery.error) return <section className="panel danger-panel"><p>{(comparerQuery.error as Error).message}</p></section>;
  if (!comparerQuery.data) return null;
  return <ItemComparer catalog={comparerQuery.data} onSaved={(item, created) => {
    void queryClient.invalidateQueries({ queryKey: ["management-items-comparer"] });
    onSaved(item, created);
  }} />;
}

function SpecialReasonChips({ item }: { item: Item }) {
  if (!item.specialReasons.length) {
    return <small className="item-special-reason-chips" data-empty="true">Nessun motivo rilevato · ricontrolla o verifica a mano</small>;
  }
  return <small className="item-special-reason-chips">{item.specialReasons.map((reason) => <span key={reason.code} className="item-special-reason-chip">{reason.label}</span>)}</small>;
}

const PAGE_SIZE = 100;

// Mirrors backend.core.item_selectors.NONE_SENTINEL: an explicit "empty" value,
// distinct from "" which means the filter is not applied at all.
const NONE_SENTINEL = "__none__";

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Ordine catalogo" },
  { value: "name", label: "Nome (A → Z)" },
  { value: "name_desc", label: "Nome (Z → A)" },
  { value: "rarity", label: "Rarità (crescente)" },
  { value: "rarity_desc", label: "Rarità (decrescente)" },
  { value: "weight", label: "Peso (crescente)" },
  { value: "weight_desc", label: "Peso (decrescente)" },
  { value: "value", label: "Valore (crescente)" },
  { value: "value_desc", label: "Valore (decrescente)" },
];

export function ItemManagementPage() {
  const { media, notify } = useApp();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"catalog" | "bulk" | "compare">("catalog");
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [type2Filter, setType2Filter] = useState("");
  const [type3Filter, setType3Filter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [stateFilter, setStateFilter] = useState<"active" | "archived" | "all">("active");
  const [specialFilter, setSpecialFilter] = useState<"all" | "special" | "standard">("all");
  const [rarityFilter, setRarityFilter] = useState("");
  const [weaponTypeFilter, setWeaponTypeFilter] = useState("");
  const [weightMin, setWeightMin] = useState("");
  const [weightMax, setWeightMax] = useState("");
  const [valueMin, setValueMin] = useState("");
  const [valueMax, setValueMax] = useState("");
  const [sort, setSort] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editorItem, setEditorItem] = useState<Item | null | undefined>(undefined);
  const [cloning, setCloning] = useState(false);
  const [triageSelection, setTriageSelection] = useState<number[]>([]);

  // The catalogue is far too large to filter in the browser, so the search box
  // drives the query itself; debouncing keeps a request per keystroke away.
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(queryInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [queryInput]);
  const filterDependencies = [
    query, typeFilter, type2Filter, type3Filter, regionFilter, stateFilter, specialFilter,
    rarityFilter, weaponTypeFilter, weightMin, weightMax, valueMin, valueMax, sort,
  ];
  useEffect(() => setOffset(0), filterDependencies);
  useEffect(() => setTriageSelection([]), [...filterDependencies, offset]);

  const catalogParameters = new URLSearchParams({
    limit: String(PAGE_SIZE),
    offset: String(offset),
    query,
    type_1: typeFilter,
    region: regionFilter,
    state: stateFilter === "all" ? "" : stateFilter,
    special: specialFilter === "all" ? "" : specialFilter,
  });
  if (type2Filter) catalogParameters.set("type_2", type2Filter);
  if (type3Filter) catalogParameters.set("type_3", type3Filter);
  if (rarityFilter) catalogParameters.set("rarity", rarityFilter);
  if (weaponTypeFilter) catalogParameters.set("weapon_type_id", weaponTypeFilter);
  if (weightMin) catalogParameters.set("weight_min", weightMin);
  if (weightMax) catalogParameters.set("weight_max", weightMax);
  if (valueMin) catalogParameters.set("value_min", valueMin);
  if (valueMax) catalogParameters.set("value_max", valueMax);
  if (sort) catalogParameters.set("sort", sort);
  const catalogQuery = useQuery({
    queryKey: ["management-items", catalogParameters.toString()],
    queryFn: () => getData<ItemCatalog>(`/api/v1/management/items?${catalogParameters}`),
    placeholderData: (previous) => previous,
  });
  const catalog = catalogQuery.data;
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["management-items"] });
  const mutation = useMutation({
    mutationFn: ({ action, itemId, values }: { action: "items.create" | "items.update" | "items.archive"; itemId?: number; values?: Record<string, unknown> }) => command<ItemActionData>(action, { itemId, values: values || {} }, "management-items"),
    onSuccess: async (_, variables) => {
      await invalidate();
      setEditorItem(undefined);
      setCloning(false);
      notify(variables.action === "items.archive" ? "Oggetto archiviato." : "Catalogo oggetti aggiornato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const triageMutation = useMutation({
    mutationFn: (itemIds: number[]) => command<ItemActionData>("items.setSpecial", { itemIds, special: false }, "management-items"),
    onSuccess: async (response) => {
      await invalidate();
      setTriageSelection([]);
      notify(`${response.data.management?.updated ?? 0} oggetti non sono più Speciali.`);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const recheckMutation = useMutation({
    mutationFn: (itemIds: number[]) => command<ItemActionData>("items.recheckSpecial", { itemIds }, "management-items"),
    onSuccess: async (response) => {
      await invalidate();
      setTriageSelection([]);
      const { cleared = 0, stillSpecial = 0 } = response.data.management || {};
      notify(`${cleared} oggetti non sono più Speciali, ${stillSpecial} hanno ancora un motivo aperto.`);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const types = useMemo(() => (catalog?.typeOptions || []).filter((option) => option.position === 1), [catalog]);
  const types2 = useMemo(() => (catalog?.typeOptions || []).filter((option) => option.position === 2), [catalog]);
  const types3 = useMemo(() => (catalog?.typeOptions || []).filter((option) => option.position === 3), [catalog]);
  const items = catalog?.items || [];
  const total = catalog?.total ?? 0;
  useEffect(() => {
    const visibleSelection = items.find((item) => item.id === selectedId)?.id ?? items[0]?.id ?? null;
    if (visibleSelection !== selectedId) setSelectedId(visibleSelection);
  }, [items, selectedId]);
  const selected = items.find((item) => item.id === selectedId) || null;
  const saveEditor = (values: Record<string, unknown>) => mutation.mutate({ action: editorItem && !cloning ? "items.update" : "items.create", itemId: editorItem && !cloning ? editorItem.id : undefined, values });
  const archiveEditor = () => {
    if (editorItem && window.confirm(`Archiviare ${editorItem.name}?`)) mutation.mutate({ action: "items.archive", itemId: editorItem.id });
  };
  const toggleTriage = (itemId: number) => setTriageSelection((current) => current.includes(itemId) ? current.filter((entry) => entry !== itemId) : [...current, itemId]);
  const resetFilters = () => {
    setQueryInput("");
    setTypeFilter("");
    setType2Filter("");
    setType3Filter("");
    setRegionFilter("");
    setStateFilter("active");
    setSpecialFilter("all");
    setRarityFilter("");
    setWeaponTypeFilter("");
    setWeightMin("");
    setWeightMax("");
    setValueMin("");
    setValueMax("");
    setSort("");
  };
  const hasActiveFilters = Boolean(
    queryInput || typeFilter || type2Filter || type3Filter || regionFilter
    || stateFilter !== "active" || specialFilter !== "all" || rarityFilter || weaponTypeFilter
    || weightMin || weightMax || valueMin || valueMax || sort,
  );

  return <div className="page management-page">
    <header className="page-header"><div><p className="eyebrow">Gestione del gioco</p><h1>Catalogo oggetti</h1></div><div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link><MasterAIAssistButton entityType="item" sourceSurface="item-management" defaultPrompt="Aiutami a creare o aggiornare un oggetto del catalogo. Prepara soltanto una proposta da revisionare.">AI Assist</MasterAIAssistButton><button className="button secondary" disabled={!selected} onClick={() => { if (selected) { setCloning(true); setEditorItem(selected); } }}>Clona selezionato</button><button className="button primary" onClick={() => { setCloning(false); setEditorItem(null); }}>Crea oggetto</button></div></header>
    <div className="management-mode-tabs" role="tablist"><button role="tab" aria-selected={mode === "catalog"} className={mode === "catalog" ? "active" : ""} onClick={() => setMode("catalog")}>Catalogo</button><button role="tab" aria-selected={mode === "bulk"} className={mode === "bulk" ? "active" : ""} onClick={() => setMode("bulk")}>Modifica di massa</button><button role="tab" aria-selected={mode === "compare"} className={mode === "compare" ? "active" : ""} onClick={() => setMode("compare")}>Confronta e copia</button></div>
    {mode === "catalog" && catalogQuery.isLoading && <section className="panel"><p>Caricamento catalogo…</p></section>}
    {mode === "catalog" && catalogQuery.error && <section className="panel danger-panel"><p>{(catalogQuery.error as Error).message}</p></section>}
    {mode === "catalog" && catalog && <>
      <section className="panel management-filterbar item-filters" data-component-type="toolbar" data-theme="default">
        <label>Cerca<input type="search" value={queryInput} onChange={(event) => setQueryInput(event.target.value)} placeholder="Nome, descrizione, tipo…" /></label>
        <label>Tipo 1<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">Tutti</option><option value={NONE_SENTINEL}>Senza tipo</option>{types.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
        <label>Tipo 2<select value={type2Filter} onChange={(event) => setType2Filter(event.target.value)}><option value="">Tutti</option><option value={NONE_SENTINEL}>Senza tipo</option>{types2.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
        <label>Tipo 3<select value={type3Filter} onChange={(event) => setType3Filter(event.target.value)}><option value="">Tutti</option><option value={NONE_SENTINEL}>Senza tipo</option>{types3.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
        <label>Tipo arma<select value={weaponTypeFilter} onChange={(event) => setWeaponTypeFilter(event.target.value)}><option value="">Tutti</option>{catalog.weaponTypes.map((weapon) => <option key={weapon.id} value={weapon.id}>{weapon.name}</option>)}</select></label>
        <label>Rarità<select value={rarityFilter} onChange={(event) => setRarityFilter(event.target.value)}><option value="">Tutte</option>{catalog.rarityChoices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</select></label>
        <label>Regione<select value={regionFilter} onChange={(event) => setRegionFilter(event.target.value)}><option value="">Tutte</option><option value={NONE_SENTINEL}>Senza regione</option>{(catalog.regions || []).map((region) => <option key={region}>{region}</option>)}</select></label>
        <label>Stato<select value={stateFilter} onChange={(event) => setStateFilter(event.target.value as typeof stateFilter)}><option value="active">Attivi</option><option value="archived">Archiviati</option><option value="all">Tutti</option></select></label>
        <label>Revisione<select value={specialFilter} onChange={(event) => setSpecialFilter(event.target.value as typeof specialFilter)}><option value="all">Tutti</option><option value="special">Solo Speciali</option><option value="standard">Solo standard</option></select></label>
        <label>Ordina per<select value={sort} onChange={(event) => setSort(event.target.value)}>{SORT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
        <label className="filter-range">Peso<span><input type="number" min="0" step="0.01" value={weightMin} onChange={(event) => setWeightMin(event.target.value)} placeholder="min" /><input type="number" min="0" step="0.01" value={weightMax} onChange={(event) => setWeightMax(event.target.value)} placeholder="max" /></span></label>
        <label className="filter-range">Valore<span><input type="number" min="0" value={valueMin} onChange={(event) => setValueMin(event.target.value)} placeholder="min" /><input type="number" min="0" value={valueMax} onChange={(event) => setValueMax(event.target.value)} placeholder="max" /></span></label>
        <button type="button" className="button secondary" disabled={!hasActiveFilters} onClick={resetFilters}>Reset filtri</button>
      </section>
      {specialFilter === "special" && <section className="panel item-triage-bar" data-component-type="toolbar" data-theme="gold">
        <div>
          <strong>{catalog.specialCount ?? 0} oggetti sono marcati Speciali</strong>
          <p>Il flag li esclude da ogni negozio. <em>Ricontrolla</em> lo toglie solo dove il motivo originale (tipo mancante, effetti Elder non convertiti, non modello, temporaneo) risulta davvero risolto; <em>Forza rimozione</em> lo toglie comunque, senza verifica.</p>
        </div>
        <div className="button-row">
          <button type="button" className="button secondary" disabled={!items.length} onClick={() => setTriageSelection(triageSelection.length === items.length ? [] : items.map((item) => item.id))}>{triageSelection.length === items.length && items.length ? "Deseleziona pagina" : "Seleziona pagina"}</button>
          <button type="button" className="button secondary" disabled={!triageSelection.length || recheckMutation.isPending} onClick={() => recheckMutation.mutate(triageSelection)}>{recheckMutation.isPending ? "Verifica…" : `Ricontrolla (${triageSelection.length})`}</button>
          <button type="button" className="button primary" disabled={!triageSelection.length || triageMutation.isPending} onClick={() => { if (window.confirm(`Forzare la rimozione del flag Speciale da ${triageSelection.length} oggetti, anche se il motivo non risulta risolto?`)) triageMutation.mutate(triageSelection); }}>{triageMutation.isPending ? "Aggiornamento…" : `Forza rimozione (${triageSelection.length})`}</button>
        </div>
      </section>}
      <div className="item-management-layout"><section className="panel managed-item-list"><header><strong>{total} oggetti</strong><small>{total ? `${offset + 1}–${offset + items.length}` : "nessun risultato"}{catalogQuery.isFetching ? " · aggiornamento…" : ""}</small></header>{items.map((item) => <button key={item.id} className={item.id === selectedId ? "active" : ""} data-state={item.archived ? "archived" : "active"} onClick={() => setSelectedId(item.id)}>{specialFilter === "special" && <input type="checkbox" aria-label={`Seleziona ${item.name}`} checked={triageSelection.includes(item.id)} onClick={(event) => event.stopPropagation()} onChange={() => toggleTriage(item.id)} />}<span><strong>{item.name}</strong><small>#{item.id} · {item.types.join(" / ") || "Senza tipo"}</small>{specialFilter === "special" && <SpecialReasonChips item={item} />}</span><b>{item.weight ?? "—"}</b></button>)}{!items.length && !catalogQuery.isFetching && <div className="management-empty-state"><strong>Nessun oggetto</strong><p>Cambia ricerca o filtri.</p></div>}<footer className="managed-item-pager"><button type="button" className="button secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Precedenti</button><span>{Math.floor(offset / PAGE_SIZE) + 1} / {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span><button type="button" className="button secondary small" disabled={!catalog.hasMore} onClick={() => setOffset(offset + PAGE_SIZE)}>Successivi →</button></footer></section><section className="panel item-management-inspector">{selected ? <><header><div><p className="eyebrow">Oggetto #{selected.id}{selected.archived ? " · archiviato" : ""}{selected.special ? " · speciale" : ""}</p><h2>{selected.name}</h2></div><button className="button primary" onClick={() => setEditorItem(selected)}>Modifica</button></header><div className="button-row master-ai-record-actions"><MasterAIAssistButton entityType="item" targetId={selected.id} recordLabel={selected.name} sourceSurface="item-management" defaultPrompt={`Rivedi «${selected.name}» e proponi le modifiche necessarie senza applicarle.`}>Chiedi al Master AI</MasterAIAssistButton><MasterAIAssistButton entityType="item" sourceId={selected.id} recordLabel={selected.name} sourceSurface="item-management" defaultPrompt={`Crea un nuovo oggetto simile a «${selected.name}», ma attendi le mie indicazioni per le differenze.`}>Crea simile con AI</MasterAIAssistButton></div>{selected.imageUrl && <img src={selected.imageUrl} alt="" />}<p>{selected.description || "Nessuna descrizione."}</p>{selected.special && <aside className="item-special-evidence"><strong>Perché è marcato Speciale</strong>{selected.specialReasons.length ? <ul>{selected.specialReasons.map((reason) => <li key={reason.code}><strong>{reason.label}</strong><span>{reason.hint}</span></li>)}</ul> : <p>Nessun motivo automatico rilevato: probabilmente il flag è stato impostato a mano, oppure la causa originale è già stata risolta. Prova <em>Ricontrolla</em> nell'elenco, oppure togli il flag da qui sotto.</p>}</aside>}<dl><div><dt>Tipi</dt><dd>{selected.types.join(" / ") || "—"}</dd></div><div><dt>Peso</dt><dd>{selected.weight ?? "—"}</dd></div><div><dt>Valore</dt><dd>{selected.value ?? "—"}</dd></div><div><dt>Rarità</dt><dd>{selected.rarityLabel || "—"}</dd></div><div><dt>Regione</dt><dd>{selected.region || "—"}</dd></div><div><dt>Effetti strutturati</dt><dd>{selected.effects.length}</dd></div><div><dt>Effetti Elder</dt><dd>{selected.elderEffects.filter(Boolean).length}</dd></div></dl>{selected.specialRules && <aside><strong>Regole speciali</strong><p>{selected.specialRules}</p></aside>}</> : <div className="management-empty-state"><strong>Nessun oggetto selezionato</strong></div>}</section></div>
    </>}
    {mode === "bulk" && <ItemBulkEditor onApplied={() => setTriageSelection([])} />}
    {mode === "compare" && <LegacyComparerTab onSaved={(item) => { setSelectedId(item.id); void invalidate(); }} />}
    {editorItem !== undefined && catalog && <ItemEditorModal item={editorItem} clone={cloning} catalog={catalog} media={media} saving={mutation.isPending} onClose={() => { setEditorItem(undefined); setCloning(false); }} onSave={saveEditor} onArchive={editorItem && !cloning ? archiveEditor : undefined} />}
  </div>;
}
