import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import { GeneratorRulesEditor } from "./GeneratorRulesEditor";
import type {
  MarketActionData,
  MarketData,
  MarketLocationConfiguration,
  RarityChoice,
  ShopSummary,
  ShopType,
  ShopTypeConfiguration,
  StockEligibility,
} from "../market/types";
import { itemTypeLabel, rankOptions, shopIcon, shopIconOptions, uniqueSlug } from "../market/ui";

type WorkspaceTab = "territory" | "types" | "eligibility" | "generator" | "batch";

// Probabilities are stored as fractions and edited as percentages. Rounding to
// whole percents would destroy the sub-1% shares the rarest tiers rely on, and
// a distribution that no longer sums to 1 is refused on save.
function formatPercent(value: number): number {
  return Number((Number(value || 0) * 100).toFixed(2));
}

function moveItem<T>(items: T[], index: number, direction: -1 | 1): T[] {
  const target = index + direction;
  if (target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

function MoveButtons({ index, length, onMove }: { index: number; length: number; onMove: (direction: -1 | 1) => void }) {
  return <span className="shop-structure-move">
    <button type="button" disabled={index === 0} onClick={() => onMove(-1)} aria-label="Sposta prima">↑</button>
    <button type="button" disabled={index === length - 1} onClick={() => onMove(1)} aria-label="Sposta dopo">↓</button>
  </span>;
}

function TerritoryEditor({ configuration, market, onChange }: {
  configuration: MarketLocationConfiguration;
  market: MarketData;
  onChange: (value: MarketLocationConfiguration) => void;
}) {
  const [selectedKey, setSelectedKey] = useState(configuration.regions[0]?.key || "");
  const [newRegionName, setNewRegionName] = useState("");
  const [newPlaceName, setNewPlaceName] = useState("");
  const selectedIndex = configuration.regions.findIndex((region) => region.key === selectedKey);
  const selected = configuration.regions[selectedIndex] || configuration.regions[0];
  const regionOverview = market.locations.find((region) => region.key === selected?.key);
  useEffect(() => {
    if (selectedKey && !configuration.regions.some((region) => region.key === selectedKey)) {
      setSelectedKey(configuration.regions[0]?.key || "");
    }
  }, [configuration.regions, selectedKey]);

  const updateSelected = (values: Partial<MarketLocationConfiguration["regions"][number]>) => {
    if (!selected) return;
    onChange({
      ...configuration,
      regions: configuration.regions.map((region) => region.key === selected.key ? { ...region, ...values } : region),
    });
  };
  const addRegion = () => {
    const label = newRegionName.trim();
    if (!label) return;
    const key = uniqueSlug(label, configuration.regions.map((region) => region.key));
    onChange({ ...configuration, regions: [...configuration.regions, { key, label, enabled: true, places: [] }] });
    setSelectedKey(key);
    setNewRegionName("");
  };
  const duplicateRegion = () => {
    if (!selected) return;
    const key = uniqueSlug(`copia-${selected.label}`, configuration.regions.map((region) => region.key));
    onChange({
      ...configuration,
      regions: [...configuration.regions, {
        ...structuredClone(selected),
        key,
        label: `Copia di ${selected.label}`,
      }],
    });
    setSelectedKey(key);
  };
  const addPlace = () => {
    const label = newPlaceName.trim();
    if (!selected || !label) return;
    const key = uniqueSlug(label, selected.places.map((place) => place.key));
    updateSelected({ places: [...selected.places, { key, label, enabled: true, aliases: [] }] });
    setNewPlaceName("");
  };
  const duplicatePlace = (placeKey: string) => {
    if (!selected) return;
    const place = selected.places.find((entry) => entry.key === placeKey);
    if (!place) return;
    const key = uniqueSlug(`copia-${place.label}`, selected.places.map((entry) => entry.key));
    updateSelected({ places: [...selected.places, { ...structuredClone(place), key, label: `Copia di ${place.label}` }] });
  };

  return <div className="shop-structure-layout">
    <aside className="panel shop-structure-index" data-component-type="list" data-theme="dark">
      <header><div><p className="eyebrow">Struttura</p><h2>Regioni</h2></div><span>{configuration.regions.length}</span></header>
      <div>{configuration.regions.map((region, index) => <div key={region.key} className={region.key === selected?.key ? "active" : ""}>
        <button type="button" onClick={() => setSelectedKey(region.key)}><strong>{region.label}</strong><small>{region.places.length} località · {market.locations.find((entry) => entry.key === region.key)?.shopCount || 0} negozi</small></button>
        <MoveButtons index={index} length={configuration.regions.length} onMove={(direction) => onChange({ ...configuration, regions: moveItem(configuration.regions, index, direction) })} />
      </div>)}</div>
      <div className="shop-structure-add"><input value={newRegionName} placeholder="Nome nuova regione" onChange={(event) => setNewRegionName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addRegion(); }} /><button type="button" disabled={!newRegionName.trim()} onClick={addRegion}>Aggiungi</button></div>
    </aside>
    <main className="panel shop-structure-editor" data-component-type="form" data-theme="parchment">
      {selected ? <>
        <header><div><p className="eyebrow">{regionOverview?.shopCount || 0} negozi interessati</p><h2>{selected.label}</h2><small>La chiave stabile <code>{selected.key}</code> non cambia quando rinomini la regione.</small></div><div className="button-row"><button type="button" className="button secondary" onClick={duplicateRegion}>Duplica regione</button><button type="button" className={selected.enabled ? "button primary" : "button secondary"} onClick={() => updateSelected({ enabled: !selected.enabled })}>{selected.enabled ? "Regione attiva" : "Regione nascosta"}</button></div></header>
        <label className="shop-structure-name">Nome visualizzato<input value={selected.label} onChange={(event) => updateSelected({ label: event.target.value })} /></label>
        <section className="shop-place-editor">
          <header><div><h3>Località</h3><p>Rinomina, ordina, duplica o nascondi senza cambiare i collegamenti dei negozi.</p></div><span>{selected.places.length}</span></header>
          <div className="shop-place-list">{selected.places.map((place, index) => {
            const shopCount = regionOverview?.places.find((entry) => entry.key === place.key)?.shopCount || 0;
            return <article key={place.key} data-state={place.enabled ? "active" : "disabled"}>
              <span className="shop-place-order">{index + 1}</span>
              <label>Nome<input value={place.label} onChange={(event) => updateSelected({ places: selected.places.map((entry) => entry.key === place.key ? { ...entry, label: event.target.value } : entry) })} /><small><code>{selected.key}/{place.key}</code> · {shopCount} negozi</small></label>
              <MoveButtons index={index} length={selected.places.length} onMove={(direction) => updateSelected({ places: moveItem(selected.places, index, direction) })} />
              <button type="button" onClick={() => duplicatePlace(place.key)}>Duplica</button>
              <button type="button" className={place.enabled ? "active" : ""} onClick={() => updateSelected({ places: selected.places.map((entry) => entry.key === place.key ? { ...entry, enabled: !entry.enabled } : entry) })}>{place.enabled ? "Visibile" : "Nascosta"}</button>
            </article>;
          })}</div>
          <div className="shop-structure-add"><input value={newPlaceName} placeholder={`Nuova località in ${selected.label}`} onChange={(event) => setNewPlaceName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addPlace(); }} /><button type="button" disabled={!newPlaceName.trim()} onClick={addPlace}>Aggiungi località</button></div>
        </section>
      </> : <div className="management-empty-state"><strong>Nessuna regione configurata</strong><p>Aggiungi la prima regione dalla colonna a sinistra.</p></div>}
    </main>
  </div>;
}

function ShopTypesEditor({ configuration, itemTypes, shops, onChange }: {
  configuration: ShopTypeConfiguration;
  itemTypes: string[];
  shops: ShopSummary[];
  onChange: (value: ShopTypeConfiguration) => void;
}) {
  const [selectedKey, setSelectedKey] = useState(configuration.types[0]?.key || "");
  const [newTypeName, setNewTypeName] = useState("");
  const [query, setQuery] = useState("");
  const [includedOnly, setIncludedOnly] = useState(true);
  const selectedIndex = configuration.types.findIndex((type) => type.key === selectedKey);
  const selected = configuration.types[selectedIndex] || configuration.types[0];
  useEffect(() => {
    if (selectedKey && !configuration.types.some((type) => type.key === selectedKey)) {
      setSelectedKey(configuration.types[0]?.key || "");
    }
  }, [configuration.types, selectedKey]);
  const categories = useMemo(() => Array.from(new Set([
    ...itemTypes,
    ...configuration.types.flatMap((type) => Object.keys(type.itemTypeRanks || {})),
  ])).sort((left, right) => left.localeCompare(right, "it")), [configuration.types, itemTypes]);
  const visibleCategories = categories.filter((itemType) => {
    const rank = Number(selected?.itemTypeRanks?.[itemType] ?? 5);
    return (!includedOnly || rank < 5) && (!query.trim() || itemTypeLabel(itemType).toLocaleLowerCase("it").includes(query.trim().toLocaleLowerCase("it")));
  });
  const updateSelected = (values: Partial<ShopType>) => selected && onChange({
    ...configuration,
    types: configuration.types.map((type) => type.key === selected.key ? { ...type, ...values } : type),
  });
  const baseRanks = () => Object.fromEntries((categories.length ? categories : ["oggettivari"]).map((category) => [category, 5]));
  const addType = () => {
    const label = newTypeName.trim();
    if (!label) return;
    const key = uniqueSlug(label, configuration.types.map((type) => type.key));
    onChange({ ...configuration, types: [...configuration.types, { key, label, icon: "store", enabled: true, defaultBackground: "", inventoryMultiplier: 1, itemTypeRanks: baseRanks() }] });
    setSelectedKey(key);
    setNewTypeName("");
  };
  const duplicateType = () => {
    if (!selected) return;
    const key = uniqueSlug(`copia-${selected.label}`, configuration.types.map((type) => type.key));
    onChange({ ...configuration, types: [...configuration.types, { ...structuredClone(selected), key, label: `Copia di ${selected.label}` }] });
    setSelectedKey(key);
  };

  return <div className="shop-structure-layout">
    <aside className="panel shop-structure-index shop-type-index" data-component-type="list" data-theme="dark">
      <header><div><p className="eyebrow">Assortimento</p><h2>Tipi</h2></div><span>{configuration.types.length}</span></header>
      <div>{configuration.types.map((type, index) => <div key={type.key} className={type.key === selected?.key ? "active" : ""}>
        <button type="button" onClick={() => setSelectedKey(type.key)}><span>{shopIcon(type)}</span><strong>{type.label}</strong><small>{shops.filter((shop) => shop.categoryKey === type.key).length} negozi</small></button>
        <MoveButtons index={index} length={configuration.types.length} onMove={(direction) => onChange({ ...configuration, types: moveItem(configuration.types, index, direction) })} />
      </div>)}</div>
      <div className="shop-structure-add"><input value={newTypeName} placeholder="Nuovo tipo di negozio" onChange={(event) => setNewTypeName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addType(); }} /><button type="button" disabled={!newTypeName.trim()} onClick={addType}>Aggiungi</button></div>
    </aside>
    <main className="panel shop-structure-editor shop-type-editor" data-component-type="form" data-theme="parchment">
      {selected ? <>
        <header><div><p className="eyebrow">{shops.filter((shop) => shop.categoryKey === selected.key).length} negozi interessati</p><h2><span>{shopIcon(selected)}</span>{selected.label}</h2><small>Chiave stabile <code>{selected.key}</code></small></div><div className="button-row"><button type="button" className="button secondary" onClick={duplicateType}>Duplica tipo</button><button type="button" className={selected.enabled ? "button primary" : "button secondary"} onClick={() => updateSelected({ enabled: !selected.enabled })}>{selected.enabled ? "Tipo attivo" : "Tipo nascosto"}</button></div></header>
        <section className="shop-type-identity">
          <label>Nome visualizzato<input value={selected.label} onChange={(event) => updateSelected({ label: event.target.value })} /></label>
          <label>Icona<select value={selected.icon} onChange={(event) => updateSelected({ icon: event.target.value })}>{shopIconOptions.map((icon) => <option key={icon} value={icon}>{shopIcon({ ...selected, icon })} {icon}</option>)}</select></label>
          <label>Sfondo predefinito<input value={selected.defaultBackground || ""} placeholder="es. forge" onChange={(event) => updateSelected({ defaultBackground: event.target.value })} /></label>
          <label>Dimensione inventario<input type="number" min=".1" max="5" step=".05" value={selected.inventoryMultiplier} onChange={(event) => updateSelected({ inventoryMultiplier: Number(event.target.value) })} /></label>
        </section>
        <section className="market-category-rules shop-type-categories">
          <header><div><h3>Categorie degli oggetti</h3><p>0 è principale; 4 è eccezionale; × non viene mai generata.</p></div><b>{Object.values(selected.itemTypeRanks || {}).filter((rank) => rank < 5).length} incluse</b></header>
          <div className="market-category-tools"><input type="search" value={query} placeholder="Cerca categoria…" onChange={(event) => setQuery(event.target.value)} /><button type="button" className={includedOnly ? "active" : ""} onClick={() => setIncludedOnly(!includedOnly)}>{includedOnly ? "Solo incluse" : "Tutte le categorie"}</button></div>
          <div className="market-rank-legend">{rankOptions.map((option) => <span key={option.rank}><b>{option.short}</b>{option.label}</span>)}</div>
          <div className="market-category-grid">{visibleCategories.map((itemType) => {
            const rank = Number(selected.itemTypeRanks?.[itemType] ?? 5);
            return <div key={itemType} className={rank >= 5 ? "excluded" : ""}><strong>{itemTypeLabel(itemType)}</strong><div>{rankOptions.map((option) => <button type="button" key={option.rank} className={rank === option.rank ? "active" : ""} title={option.help} aria-label={`${itemTypeLabel(itemType)}: ${option.label}`} onClick={() => updateSelected({ itemTypeRanks: { ...(selected.itemTypeRanks || {}), [itemType]: option.rank } })}>{option.short}</button>)}</div></div>;
          })}</div>
          {!visibleCategories.length && <p className="market-rule-empty">Nessuna categoria corrisponde a questo filtro.</p>}
        </section>
      </> : <div className="management-empty-state"><strong>Nessun tipo configurato</strong><p>Aggiungi il primo tipo dalla colonna a sinistra.</p></div>}
    </main>
  </div>;
}

function BatchCreator({ market, saving, onCreate }: { market: MarketData; saving: boolean; onCreate: (values: Record<string, unknown>) => void }) {
  const firstLocation = market.locations.flatMap((region) => region.places).find((place) => place.enabled)?.locationKey || "";
  const firstType = market.shopTypes.find((type) => type.enabled)?.key || "";
  const [batch, setBatch] = useState({ count: 3, locationKey: firstLocation, categoryKey: firstType, level: 1, name: "" });
  return <section className="panel shop-batch-workspace" data-component-type="form" data-theme="parchment">
    <header><div><p className="eyebrow">Operazione amministrativa</p><h2>Creazione multipla</h2><p>Crea fino a 20 negozi con scorte indipendenti.</p></div></header>
    <div className="market-batch-grid">
      <label>Numero<input type="number" min="1" max={market.configuration.limits.batchMaximum || 20} value={batch.count} onChange={(event) => setBatch({ ...batch, count: Number(event.target.value) })} /></label>
      <label>Prefisso nome<input value={batch.name} placeholder="Automatico" onChange={(event) => setBatch({ ...batch, name: event.target.value })} /></label>
      <label>Località<select value={batch.locationKey} onChange={(event) => setBatch({ ...batch, locationKey: event.target.value })}>{market.locations.filter((region) => region.enabled).flatMap((region) => region.places.filter((place) => place.enabled).map((place) => <option key={place.locationKey} value={place.locationKey}>{region.label} · {place.label}</option>))}</select></label>
      <label>Tipo<select value={batch.categoryKey} onChange={(event) => setBatch({ ...batch, categoryKey: event.target.value })}>{market.shopTypes.filter((type) => type.enabled).map((type) => <option key={type.key} value={type.key}>{type.label}</option>)}</select></label>
      <label>Livello<input type="number" min={market.configuration.limits.minLevel || 1} max={market.configuration.limits.maxLevel || 20} value={batch.level} onChange={(event) => setBatch({ ...batch, level: Number(event.target.value) })} /></label>
    </div>
    <footer><p>I nomi saranno numerati automaticamente. Ogni negozio riceve un seed distinto.</p><button type="button" className="button primary" disabled={saving || !batch.locationKey || !batch.categoryKey} onClick={() => onCreate({ ...batch, nameTemplate: batch.name ? `${batch.name} {number}` : undefined })}>{saving ? "Creazione…" : `Crea ${batch.count} negozi`}</button></footer>
  </section>;
}

const EXCLUSION_HINTS: Record<string, string> = {
  notTemplate: "Sono copie assegnate, non modelli di catalogo. Normale per gli oggetti già in mano ai personaggi.",
  archived: "Voluto se l'oggetto è fuori uso; toglilo dall'archivio per rimetterlo in circolazione.",
  special: "Marcati come anomali o da rivedere. È la causa più frequente: controlla se il flag è ancora giustificato.",
  unique: "I pezzi Unici sono esclusi per scelta: vanno assegnati a mano.",
  missingRarity: "Senza rarità l'oggetto non appartiene a nessuna estrazione. Assegnagli una rarità da 1 a 5.",
  unreachableRarity: "La rarità esiste ma nessun profilo attivo le assegna una probabilità. Aggiungila nella scheda Profili.",
  noLootLevel: "Basta compilare lv_loot con un livello (3) o una fascia (4-6).",
  unconfiguredType: "Il tipo_1 non compare in nessuna categoria di negozio. Aggiungilo in Tipi e assortimento, con rango 5 se non deve mai essere venduto.",
};

function StockEligibilityPanel({ report }: { report: StockEligibility }) {
  const [reason, setReason] = useState<string>("");
  const samples = reason ? report.samples.filter((item) => item.reasons.includes(reason)) : report.samples;
  const total = report.eligibleCount + report.excludedCount;
  return <section className="panel stock-eligibility-panel" data-component-type="report" data-theme="parchment">
    <div className="callout guide-warning stock-eligibility-alert" role="alert">
      <strong>{report.excludedCount} oggetti su {total} non possono comparire in nessun negozio</strong>
      <p>Il generatore delle scorte scarta in silenzio ogni oggetto che non superi tutti i filtri. Un oggetto escluso non verrà mai generato, in nessuna categoria e a nessun livello.</p>
    </div>
    <p className="stock-eligibility-summary">Idonei alla generazione: <strong>{report.eligibleCount}</strong>. Un oggetto può essere escluso per più motivi contemporaneamente.</p>
    <ul className="stock-eligibility-reasons">
      {report.reasons.map((entry) => <li key={entry.key}>
        <button type="button" className={reason === entry.key ? "active" : ""} aria-pressed={reason === entry.key} onClick={() => setReason(reason === entry.key ? "" : entry.key)}>
          <strong>{entry.count}</strong><span>{entry.label}</span>
        </button>
        <small>{EXCLUSION_HINTS[entry.key]}</small>
      </li>)}
    </ul>
    <h3>Oggetti esclusi{reason ? ` — ${report.reasons.find((entry) => entry.key === reason)?.label}` : ""}</h3>
    <p className="stock-eligibility-summary">Elenco limitato ai primi {report.sampleLimit} oggetti esclusi. Mostrati: {samples.length}.</p>
    <div className="table-scroll">
      <table className="data-table stock-eligibility-table">
        <thead><tr><th>Oggetto</th><th>tipo_1</th><th>lv_loot</th><th>Motivi</th></tr></thead>
        <tbody>
          {samples.map((item) => <tr key={item.id}>
            <td>{item.name}</td>
            <td>{item.itemType || <em>vuoto</em>}</td>
            <td>{item.lootLevel || <em>vuoto</em>}</td>
            <td>{item.reasons.map((key) => report.reasons.find((entry) => entry.key === key)?.label || key).join(" · ")}</td>
          </tr>)}
        </tbody>
      </table>
    </div>
  </section>;
}

function ShopManagementWorkspace({ market, saving, onSave, onBatch }: {
  market: MarketData;
  saving: boolean;
  onSave: (values: Record<string, unknown>) => void;
  onBatch: (values: Record<string, unknown>) => void;
}) {
  const [tab, setTab] = useState<WorkspaceTab>("territory");
  const [locations, setLocations] = useState(() => structuredClone(market.configuration.locations!));
  const [shopTypes, setShopTypes] = useState(() => structuredClone(market.configuration.shopTypes!));
  const [rules, setRules] = useState(() => structuredClone(market.configuration.generatorRules));
  const initialConfiguration = useState(() => JSON.stringify({ locations, shopTypes, rules }))[0];
  const isDirty = initialConfiguration !== JSON.stringify({ locations, shopTypes, rules });
  const tabs: Array<{ key: WorkspaceTab; label: string; count?: number }> = [
    { key: "territory", label: "Territorio", count: locations.regions.length },
    { key: "types", label: "Tipi e assortimento", count: shopTypes.types.length },
    ...(market.stockEligibility ? [{ key: "eligibility" as const, label: "Oggetti esclusi", count: market.stockEligibility.excludedCount }] : []),
    ...(market.permissions.canTuneGenerator ? [{ key: "generator" as const, label: "Generatore" }] : []),
    ...(market.permissions.canBatchCreate ? [{ key: "batch" as const, label: "Operazioni multiple" }] : []),
  ];
  const save = () => onSave({
    locations,
    shopTypes,
    ...(market.permissions.canTuneGenerator && rules ? { generatorRules: rules } : {}),
  });

  return <>
    <nav className="management-mode-tabs shop-management-tabs" role="tablist" aria-label="Aree Gestione Negozi" data-component-type="tabset" data-theme="gold">
      {tabs.map((entry) => <button key={entry.key} type="button" role="tab" aria-selected={tab === entry.key} className={tab === entry.key ? "active" : ""} onClick={() => setTab(entry.key)}>{entry.label}{entry.count != null && <span>{entry.count}</span>}</button>)}
    </nav>
    {tab === "territory" && <TerritoryEditor configuration={locations} market={market} onChange={setLocations} />}
    {tab === "types" && <ShopTypesEditor configuration={shopTypes} itemTypes={market.configuration.itemTypes || []} shops={market.shops} onChange={setShopTypes} />}
    {tab === "eligibility" && market.stockEligibility && <StockEligibilityPanel report={market.stockEligibility} />}
    {tab === "generator" && rules && <section className="panel shop-generator-workspace" data-component-type="form" data-theme="parchment"><GeneratorRulesEditor rules={rules} onChange={setRules} /></section>}
    {tab === "batch" && <BatchCreator market={market} saving={saving} onCreate={onBatch} />}
    {tab !== "batch" && <footer className="sticky-actions shop-management-savebar" data-component-type="toolbar" data-theme="dark"><span>{isDirty ? "Modifiche non ancora salvate" : "Configurazione aggiornata"}</span><button type="button" className="button primary" disabled={saving || !isDirty} onClick={save}>{saving ? "Salvataggio…" : "Salva configurazione"}</button></footer>}
  </>;
}

export function ShopManagementPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const managementQuery = useQuery({
    queryKey: ["market-management"],
    queryFn: () => getData<MarketData>("/api/v1/management/shops"),
  });
  const mutation = useMutation({
    mutationFn: ({ action, payload }: { action: string; payload: Record<string, unknown> }) => command<MarketActionData>(action, payload, "market-management"),
    onSuccess: async (response) => {
      if (response.data.market) queryClient.setQueryData(["market-management"], response.data.market);
      await queryClient.invalidateQueries({ queryKey: ["market"] });
      notify(response.events[0]?.message || "Gestione Negozi aggiornata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const market = managementQuery.data;

  return <div className="page management-page shop-management-page">
    <header className="page-header"><div><p className="eyebrow">Gestione del gioco</p><h1>Gestione Negozi</h1><p>Struttura del mondo commerciale e assortimenti in un'unica postazione.</p></div><div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link><Link className="button secondary" to="/market">Apri Mercato</Link></div></header>
    {market?.stockEligibility && market.stockEligibility.excludedCount > 0 && <section className="panel danger-panel stock-eligibility-banner" role="alert">
      <p><strong>{market.stockEligibility.excludedCount} oggetti non possono comparire in nessun negozio.</strong> Il generatore li scarta senza avvisare: mancano i requisiti di modello, archiviazione, rarità, lv_loot o tipo_1.</p>
    </section>}
    {managementQuery.isLoading && <section className="panel"><p>Preparazione della gestione negozi…</p></section>}
    {managementQuery.error && <section className="panel danger-panel"><p>{(managementQuery.error as Error).message}</p></section>}
    {market?.configuration.locations && market.configuration.shopTypes && <ShopManagementWorkspace
      key={market.configuration.hash || "market-management"}
      market={market}
      saving={mutation.isPending}
      onSave={(values) => mutation.mutate({ action: "market.settings.save", payload: { values } })}
      onBatch={(values) => mutation.mutate({ action: "market.shop.batchCreate", payload: { values, confirm: true } })}
    />}
  </div>;
}
