import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { ImagePickerModal } from "../../components/ImagePickerModal";
import { ItemSpecialIconField } from "../../components/ItemSpecialIconField";
import { ItemEditorModal } from "../character/ItemEditorModal";
import { command, getData } from "../../lib/api";
import type { Item, ItemCatalog } from "../../lib/types";

type ItemActionData = { item?: Item | null; catalog?: ItemCatalog | null; management?: { created?: boolean } | null };
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
  effects: string;
  alchemy_profile: string;
  crafting_profile: string;
  mediaId: string;
  notes: string;
};

const EMPTY_DRAFT: ItemDraft = {
  identityId: null, identityName: "", nome: "", modello: true, temporaneo: false, archiviato: false, speciale: false,
  numero_ordine: "", icona: "", tipo_1: "", tipo_2: "", tipo_3: "", tipo_4: "",
  descrizione: "", valore: "", peso: "", rarita: "", lv_loot: "", regione_loot: "", peso_regione: "",
  tipoArmaId: "", pa_per_attacco: "", elderEffects: Array(8).fill(""), effects: "[]", alchemy_profile: "{}", crafting_profile: "{}", mediaId: "", notes: "",
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
    effects: JSON.stringify(item.effects || [], null, 2),
    alchemy_profile: JSON.stringify(item.alchemyProfile || {}, null, 2),
    crafting_profile: JSON.stringify(item.craftingProfile || {}, null, 2),
    mediaId: item.mediaId == null ? "" : String(item.mediaId),
    notes: item.notes || "",
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
    effects: JSON.parse(draft.effects || "[]"),
    alchemy_profile: JSON.parse(draft.alchemy_profile || "{}"),
    crafting_profile: JSON.parse(draft.crafting_profile || "{}"),
    mediaId: draft.mediaId || null, notes: draft.notes,
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
      <h3>Dati strutturati</h3>
      <CompareRow label="Effetti" left={left?.effects} wide><textarea className="code-input" rows={8} value={right.effects} onChange={(event) => update("effects", event.target.value)} spellCheck={false} /></CompareRow>
      <CompareRow label="Profilo alchimia" left={left?.alchemyProfile} wide><textarea className="code-input" rows={8} value={right.alchemy_profile} onChange={(event) => update("alchemy_profile", event.target.value)} spellCheck={false} /></CompareRow>
      <CompareRow label="Profilo crafting" left={left?.craftingProfile} wide><textarea className="code-input" rows={8} value={right.crafting_profile} onChange={(event) => update("crafting_profile", event.target.value)} spellCheck={false} /></CompareRow>
      <h3>Media e note</h3>
      <CompareRow label="Immagine" left={leftMedia}><button className="media-picker-trigger compact" type="button" onClick={() => setImagePickerOpen(true)}>{rightMedia ? <><img src={rightMedia.thumbnailUrl || rightMedia.url} alt="" /><span>{rightMedia.title}</span></> : "Scegli dall'archivio"}</button></CompareRow>
      <CompareRow label="Icona dedicata" left={left?.imageUrl} wide><ItemSpecialIconField itemId={right.identityId} itemName={right.nome} imageUrl={catalog.items.find((item) => item.id === right.identityId)?.imageUrl || ""} /></CompareRow>
      <CompareRow label="Note" left={left?.notes} wide><textarea rows={5} value={right.notes} onChange={(event) => update("notes", event.target.value)} /></CompareRow>
    </div>
    <div className="sticky-actions"><button className="button primary" type="button" disabled={mutation.isPending || !right.nome.trim()} onClick={save}>{right.identityId && right.nome.toLocaleLowerCase("it") === right.identityName.toLocaleLowerCase("it") ? "Aggiorna destinazione" : "Crea nuovo oggetto"}</button></div>
  </section>{imagePickerOpen && <ImagePickerModal selectedId={rightMedia?.id || null} usageType="item_icon" defaultGroup="Oggetti" defaultTitle={right.nome || "Nuovo oggetto"} onSelect={(asset) => update("mediaId", asset ? String(asset.id) : "")} onClose={() => setImagePickerOpen(false)} />}</>;
}

export function ItemManagementPage() {
  const { media, notify } = useApp();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"catalog" | "compare">("catalog");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [stateFilter, setStateFilter] = useState<"active" | "archived" | "all">("active");
  const [specialFilter, setSpecialFilter] = useState<"all" | "special" | "standard">("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editorItem, setEditorItem] = useState<Item | null | undefined>(undefined);
  const [cloning, setCloning] = useState(false);
  const catalogQuery = useQuery({ queryKey: ["management-items"], queryFn: () => getData<ItemCatalog>("/api/v1/management/items?limit=10000") });
  const catalog = catalogQuery.data;
  const mutation = useMutation({
    mutationFn: ({ action, itemId, values }: { action: "items.create" | "items.update" | "items.archive"; itemId?: number; values?: Record<string, unknown> }) => command<ItemActionData>(action, { itemId, values: values || {} }, "management-items"),
    onSuccess: async (_, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["management-items"] });
      setEditorItem(undefined);
      setCloning(false);
      notify(variables.action === "items.archive" ? "Oggetto archiviato." : "Catalogo oggetti aggiornato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const types = useMemo(() => [...new Set(catalog?.items.flatMap((item) => item.types) || [])].sort((a, b) => a.localeCompare(b, "it")), [catalog]);
  const regions = useMemo(() => [...new Set(catalog?.items.map((item) => item.region).filter(Boolean) || [])].sort((a, b) => a.localeCompare(b, "it")), [catalog]);
  const normalized = query.trim().toLocaleLowerCase("it");
  const filtered = (catalog?.items || []).filter((item) => {
    const searchable = `${item.name} ${item.description} ${item.types.join(" ")} ${item.region}`.toLocaleLowerCase("it");
    return (!normalized || searchable.includes(normalized))
      && (!typeFilter || item.types.includes(typeFilter))
      && (!regionFilter || item.region === regionFilter)
      && (specialFilter === "all" || (specialFilter === "special" ? item.special : !item.special))
      && (stateFilter === "all" || (stateFilter === "archived" ? item.archived : !item.archived));
  });
  useEffect(() => {
    const visibleSelection = filtered.find((item) => item.id === selectedId)?.id ?? filtered[0]?.id ?? null;
    if (visibleSelection !== selectedId) setSelectedId(visibleSelection);
  }, [filtered, selectedId]);
  const selected = filtered.find((item) => item.id === selectedId) || null;
  const saveEditor = (values: Record<string, unknown>) => mutation.mutate({ action: editorItem && !cloning ? "items.update" : "items.create", itemId: editorItem && !cloning ? editorItem.id : undefined, values });
  const archiveEditor = () => {
    if (editorItem && window.confirm(`Archiviare ${editorItem.name}?`)) mutation.mutate({ action: "items.archive", itemId: editorItem.id });
  };

  return <div className="page management-page">
    <header className="page-header"><div><p className="eyebrow">Gestione del gioco</p><h1>Catalogo oggetti</h1></div><div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link><button className="button secondary" disabled={!selected} onClick={() => { if (selected) { setCloning(true); setEditorItem(selected); } }}>Clona selezionato</button><button className="button primary" onClick={() => { setCloning(false); setEditorItem(null); }}>Crea oggetto</button></div></header>
    <div className="management-mode-tabs" role="tablist"><button role="tab" aria-selected={mode === "catalog"} className={mode === "catalog" ? "active" : ""} onClick={() => setMode("catalog")}>Catalogo</button><button role="tab" aria-selected={mode === "compare"} className={mode === "compare" ? "active" : ""} onClick={() => setMode("compare")}>Confronta e copia</button></div>
    {catalogQuery.isLoading && <section className="panel"><p>Caricamento catalogo…</p></section>}
    {catalogQuery.error && <section className="panel danger-panel"><p>{(catalogQuery.error as Error).message}</p></section>}
    {mode === "catalog" && catalog && <>
      <section className="panel management-filterbar item-filters" data-component-type="toolbar" data-theme="default"><label>Cerca<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nome, descrizione, tipo…" /></label><label>Tipo<select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">Tutti</option>{types.map((type) => <option key={type}>{type}</option>)}</select></label><label>Regione<select value={regionFilter} onChange={(event) => setRegionFilter(event.target.value)}><option value="">Tutte</option>{regions.map((region) => <option key={region}>{region}</option>)}</select></label><label>Stato<select value={stateFilter} onChange={(event) => setStateFilter(event.target.value as typeof stateFilter)}><option value="active">Attivi</option><option value="archived">Archiviati</option><option value="all">Tutti</option></select></label></section>
      <div className="item-management-layout"><section className="panel managed-item-list"><header><strong>{filtered.length} oggetti</strong><small>{catalog.items.length} record totali</small></header>{filtered.map((item) => <button key={item.id} className={item.id === selectedId ? "active" : ""} data-state={item.archived ? "archived" : "active"} onClick={() => setSelectedId(item.id)}><span><strong>{item.name}</strong><small>#{item.id} · {item.types.join(" / ") || "Senza tipo"}</small></span><b>{item.weight ?? "—"}</b></button>)}</section><section className="panel item-management-inspector">{selected ? <><header><div><p className="eyebrow">Oggetto #{selected.id}{selected.archived ? " · archiviato" : ""}</p><h2>{selected.name}</h2></div><button className="button primary" onClick={() => setEditorItem(selected)}>Modifica</button></header>{selected.imageUrl && <img src={selected.imageUrl} alt="" />}<p>{selected.description || "Nessuna descrizione."}</p><dl><div><dt>Tipi</dt><dd>{selected.types.join(" / ") || "—"}</dd></div><div><dt>Peso</dt><dd>{selected.weight ?? "—"}</dd></div><div><dt>Valore</dt><dd>{selected.value ?? "—"}</dd></div><div><dt>Rarità</dt><dd>{selected.rarityLabel || "—"}</dd></div><div><dt>Regione</dt><dd>{selected.region || "—"}</dd></div><div><dt>Effetti strutturati</dt><dd>{selected.effects.length}</dd></div><div><dt>Effetti Elder</dt><dd>{selected.elderEffects.filter(Boolean).length}</dd></div></dl>{selected.notes && <aside><strong>Note</strong><p>{selected.notes}</p></aside>}</> : <div className="management-empty-state"><strong>Nessun oggetto selezionato</strong></div>}</section></div>
    </>}
    {mode === "catalog" && catalog && <section className="panel management-filterbar"><label>Revisione<select value={specialFilter} onChange={(event) => setSpecialFilter(event.target.value as typeof specialFilter)}><option value="all">Tutti</option><option value="special">Solo Speciali</option><option value="standard">Solo standard</option></select></label><small>Gli oggetti Speciali includono anomalie legacy ed effetti descrittivi conservati.</small></section>}
    {mode === "compare" && catalog && <ItemComparer catalog={catalog} onSaved={(item) => { setSelectedId(item.id); queryClient.invalidateQueries({ queryKey: ["management-items"] }); }} />}
    {editorItem !== undefined && catalog && <ItemEditorModal item={editorItem} clone={cloning} catalog={catalog} media={media} saving={mutation.isPending} onClose={() => { setEditorItem(undefined); setCloning(false); }} onSave={saveEditor} onArchive={editorItem && !cloning ? archiveEditor : undefined} />}
  </div>;
}
