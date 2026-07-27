import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../../App";
import { Modal } from "../../components/Modal";
import { command, getData } from "../../lib/api";
import type { Item } from "../../lib/types";

type MarketPlace = { key: string; label: string; enabled: boolean; locationKey: string; shopCount: number };
type MarketRegion = { key: string; label: string; enabled: boolean; places: MarketPlace[]; shopCount: number };
type ShopType = {
  key: string; label: string; icon: string; enabled: boolean; inventoryMultiplier: number;
  itemTypeRanks?: Record<string, number>;
};
type ShopSummary = {
  id: number; name: string; owner: string; categoryKey: string; level: number; locationKey: string;
  regionName: string; placeName: string; description: string; backgroundUrl: string; featured: boolean;
  archived: boolean; stockRevision: number; stockCount: number; distinctStockCount: number;
  priceModifierPercent: number; lastRestockedAt: string;
};
type StockLine = { item: Item; quantity: number; unitPrice: number; source: string };
type ShopDetail = ShopSummary & { seed: string; stock: StockLine[]; diagnostics: Record<string, unknown> };
type MarketData = {
  locations: MarketRegion[];
  shopTypes: ShopType[];
  shops: ShopSummary[];
  selectedShop: ShopDetail | null;
  character: { id: number; name: string; coins: number } | null;
  permissions: {
    canManage: boolean; canEditLocations: boolean; canEditShopTypes: boolean; canRegenerate: boolean;
    canTuneGenerator: boolean; canBatchCreate: boolean; canArchive: boolean; canPurchase: boolean;
  };
  configuration: {
    locations: { version: number; regions: Array<{ key: string; label: string; enabled: boolean; places: Array<{ key: string; label: string; enabled: boolean }> }> } | null;
    shopTypes: { version: number; types: ShopType[] } | null;
    generatorRules: Record<string, unknown> | null;
    itemTypes?: string[];
    limits: Record<string, number>;
  };
};
type MarketActionData = { market?: MarketData; marketQuote?: { total: number } };
type ShopDraft = {
  name: string; owner: string; locationKey: string; categoryKey: string; level: number;
  description: string; priceModifierPercent: number; featured: boolean; seed: string; generateStock: boolean;
};

export function resolveSelectedShopId(
  currentShopId: number | null,
  availableShops: Array<{ id: number }>,
  hasMarketData: boolean,
): number | null {
  if (!hasMarketData) return currentShopId;
  if (currentShopId && availableShops.some((shop) => shop.id === currentShopId)) return currentShopId;
  return availableShops[0]?.id ?? null;
}

const iconMap: Record<string, string> = {
  store: "⌂", hammer: "⚒", shield: "◈", swords: "⚔", "bow-arrow": "➶",
  flask: "⚗", sparkles: "✦", shirt: "♢", backpack: "▣", beer: "♨", tent: "△",
};
const shopIcon = (type?: ShopType) => iconMap[type?.icon || ""] || "◇";
const slug = (value: string) => value.trim().toLocaleLowerCase("it").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const itemTypeLabel = (value: string) => value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toLocaleUpperCase("it"));
const rankOptions = [
  { rank: 0, label: "Principale", short: "0", help: "Molto frequente" },
  { rank: 1, label: "Comune", short: "1", help: "Frequente" },
  { rank: 2, label: "Secondaria", short: "2", help: "Occasionale" },
  { rank: 3, label: "Rara", short: "3", help: "Poco frequente" },
  { rank: 4, label: "Eccezionale", short: "4", help: "Molto rara" },
  { rank: 5, label: "Esclusa", short: "×", help: "Mai generata" },
] as const;

function initialDraft(market: MarketData, shop?: ShopDetail | null): ShopDraft {
  return {
    name: shop?.name || "",
    owner: shop?.owner || "",
    locationKey: shop?.locationKey || market.locations[0]?.places[0]?.locationKey || "",
    categoryKey: shop?.categoryKey || market.shopTypes[0]?.key || "",
    level: shop?.level || 1,
    description: shop?.description || "",
    priceModifierPercent: shop?.priceModifierPercent || 0,
    featured: shop?.featured || false,
    seed: shop?.seed || "",
    generateStock: !shop,
  };
}

function ShopEditor({ market, shop, saving, onClose, onSave }: {
  market: MarketData; shop?: ShopDetail | null; saving: boolean; onClose: () => void; onSave: (values: ShopDraft) => void;
}) {
  const [draft, setDraft] = useState(() => initialDraft(market, shop));
  const selectedRegion = market.locations.find((region) => region.places.some((place) => place.locationKey === draft.locationKey)) || market.locations[0];
  const selectedPlace = selectedRegion?.places.find((place) => place.locationKey === draft.locationKey);
  const update = <K extends keyof ShopDraft>(key: K, value: ShopDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  return <Modal title={shop ? `Modifica · ${shop.name}` : "Nuovo negozio"} onClose={onClose} wide className="market-shop-modal" footer={<>
    <button type="button" className="button secondary" onClick={onClose}>Annulla</button>
    <button type="submit" form="market-shop-form" className="button primary" disabled={saving || !draft.locationKey || !draft.categoryKey}>{saving ? "Salvataggio…" : shop ? "Salva negozio" : "Crea e genera"}</button>
  </>}>
    <form id="market-shop-form" className="market-shop-editor" onSubmit={(event) => { event.preventDefault(); onSave(draft); }}>
      <section className="market-editor-copy"><label>Nome<input autoFocus value={draft.name} placeholder="Generato automaticamente se vuoto" onChange={(event) => update("name", event.target.value)} /></label><label>Proprietario<input value={draft.owner} onChange={(event) => update("owner", event.target.value)} /></label><label className="wide">Descrizione<textarea rows={3} value={draft.description} onChange={(event) => update("description", event.target.value)} /></label></section>
      <section className="market-editor-choice"><header><small>1</small><div><h3>Regione</h3><p>Scegli l'area del mondo.</p></div></header><div>{market.locations.filter((region) => region.enabled).map((region) => <button type="button" key={region.key} className={region.key === selectedRegion?.key ? "active" : ""} onClick={() => update("locationKey", region.places.find((place) => place.enabled)?.locationKey || "")}>{region.label}</button>)}</div></section>
      <section className="market-editor-choice"><header><small>2</small><div><h3>Località</h3><p>{selectedRegion?.label || "Prima scegli una regione"}.</p></div></header><div>{selectedRegion?.places.filter((place) => place.enabled).map((place) => <button type="button" key={place.locationKey} className={place.locationKey === selectedPlace?.locationKey ? "active" : ""} onClick={() => update("locationKey", place.locationKey)}>{place.label}</button>)}</div></section>
      <section className="market-editor-choice wide"><header><small>3</small><div><h3>Tipo di negozio</h3><p>Influenza la composizione delle scorte.</p></div></header><div>{market.shopTypes.filter((type) => type.enabled).map((type) => <button type="button" key={type.key} className={type.key === draft.categoryKey ? "active" : ""} onClick={() => update("categoryKey", type.key)}><span>{shopIcon(type)}</span>{type.label}</button>)}</div></section>
      <section className="market-editor-numbers wide"><label>Livello<input type="number" min={market.configuration.limits.minLevel || 1} max={market.configuration.limits.maxLevel || 20} value={draft.level} onChange={(event) => update("level", Number(event.target.value))} /></label><label>Modifica prezzi %<input type="number" min="-50" max="100" value={draft.priceModifierPercent} onChange={(event) => update("priceModifierPercent", Number(event.target.value))} /></label><label>Seed<input value={draft.seed} placeholder="Automatico" onChange={(event) => update("seed", event.target.value)} /></label><label className="market-switch"><input type="checkbox" checked={draft.featured} onChange={(event) => update("featured", event.target.checked)} /><span><strong>In evidenza</strong><small>Mostralo per primo.</small></span></label><label className="market-switch"><input type="checkbox" checked={draft.generateStock} onChange={(event) => update("generateStock", event.target.checked)} /><span><strong>Genera scorte</strong><small>Ricrea l'inventario al salvataggio.</small></span></label></section>
    </form>
  </Modal>;
}

function ShopTypeRulesEditor({ shopTypes, itemTypes, onChange }: {
  shopTypes: { version: number; types: ShopType[] };
  itemTypes: string[];
  onChange: (value: { version: number; types: ShopType[] }) => void;
}) {
  const [selectedKey, setSelectedKey] = useState(shopTypes.types[0]?.key || "");
  const [query, setQuery] = useState("");
  const [includedOnly, setIncludedOnly] = useState(true);
  const selected = shopTypes.types.find((type) => type.key === selectedKey) || shopTypes.types[0];
  const update = (values: Partial<ShopType>) => selected && onChange({
    ...shopTypes,
    types: shopTypes.types.map((type) => type.key === selected.key ? { ...type, ...values } : type),
  });
  const categories = useMemo(() => Array.from(new Set([
    ...itemTypes,
    ...shopTypes.types.flatMap((type) => Object.keys(type.itemTypeRanks || {})),
  ])).sort((left, right) => left.localeCompare(right, "it")), [itemTypes, shopTypes]);
  const visibleCategories = categories.filter((itemType) => {
    const rank = Number(selected?.itemTypeRanks?.[itemType] ?? 5);
    return (!includedOnly || rank < 5) && (!query.trim() || itemTypeLabel(itemType).toLocaleLowerCase("it").includes(query.trim().toLocaleLowerCase("it")));
  });
  const setRank = (itemType: string, rank: number) => update({
    itemTypeRanks: { ...(selected?.itemTypeRanks || {}), [itemType]: rank },
  });

  return <section className="market-shop-rules">
    <header><div><p className="eyebrow">Master e Admin</p><h3>Regole per tipo di negozio</h3></div></header>
    <p>Scegli un negozio, poi definisci la dimensione delle scorte e quali categorie può generare.</p>
    <div className="market-type-settings">{shopTypes.types.map((type) => <button type="button" key={type.key} className={`${type.enabled ? "active" : ""} ${type.key === selected?.key ? "selected" : ""}`} onClick={() => setSelectedKey(type.key)}><span>{shopIcon(type)}</span><strong>{type.label}</strong><small>{type.enabled ? `${Object.values(type.itemTypeRanks || {}).filter((rank) => rank < 5).length} categorie` : "Nascosto"}</small></button>)}</div>
    {selected && <div className="market-shop-rule-editor">
      <header><div><span className="market-shop-icon">{shopIcon(selected)}</span><div><strong>{selected.label}</strong><small>Vale dalla prossima generazione o rigenerazione.</small></div></div><button type="button" className={selected.enabled ? "active" : ""} onClick={() => update({ enabled: !selected.enabled })}>{selected.enabled ? "Attivo" : "Nascosto"}</button></header>
      <section className="market-density-editor">
        <div><strong>Dimensione inventario</strong><small>Moltiplica il numero globale di oggetti.</small></div>
        <div className="market-density-buttons">{[[.6, "Piccolo"], [1, "Normale"], [1.25, "Ricco"], [1.5, "Grande"]].map(([value, label]) => <button type="button" key={String(value)} className={Math.abs(selected.inventoryMultiplier - Number(value)) < .01 ? "active" : ""} onClick={() => update({ inventoryMultiplier: Number(value) })}>{label}<small>×{value}</small></button>)}</div>
        <label>Valore preciso<input type="number" min=".1" max="5" step=".05" value={selected.inventoryMultiplier} onChange={(event) => update({ inventoryMultiplier: Number(event.target.value) })} /></label>
      </section>
      <details className="market-category-rules" open>
        <summary><div><strong>Categorie degli oggetti</strong><small>0 è principale; 4 è eccezionale; × non viene mai generata.</small></div><b>{Object.values(selected.itemTypeRanks || {}).filter((rank) => rank < 5).length} incluse</b></summary>
        <div className="market-category-tools"><input type="search" value={query} placeholder="Cerca categoria…" onChange={(event) => setQuery(event.target.value)} /><button type="button" className={includedOnly ? "active" : ""} onClick={() => setIncludedOnly(!includedOnly)}>{includedOnly ? "Solo incluse" : "Tutte le categorie"}</button></div>
        <div className="market-rank-legend">{rankOptions.map((option) => <span key={option.rank}><b>{option.short}</b>{option.label}</span>)}</div>
        <div className="market-category-grid">{visibleCategories.map((itemType) => {
          const rank = Number(selected.itemTypeRanks?.[itemType] ?? 5);
          return <div key={itemType} className={rank >= 5 ? "excluded" : ""}><strong>{itemTypeLabel(itemType)}</strong><div>{rankOptions.map((option) => <button type="button" key={option.rank} className={rank === option.rank ? "active" : ""} title={option.help} aria-label={`${itemTypeLabel(itemType)}: ${option.label}`} onClick={() => setRank(itemType, option.rank)}>{option.short}</button>)}</div></div>;
        })}</div>
        {visibleCategories.length === 0 && <p className="market-rule-empty">Nessuna categoria corrisponde a questo filtro.</p>}
      </details>
    </div>}
  </section>;
}

function GeneratorRulesEditor({ rules, onChange }: {
  rules: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
}) {
  const update = (key: string, value: unknown) => onChange({ ...rules, [key]: value });
  const rarities = (rules.rarityProbabilities || {}) as Record<string, number>;
  const rarityTotal = Object.values(rarities).reduce((total, value) => total + Number(value || 0), 0);
  const fallbacks = (rules.fallbackLevelDeltas || []) as number[];
  return <details className="market-advanced-settings">
    <summary><span>◆</span><div><strong>Regole globali del generatore · Admin</strong><small>Livelli, quantità, rarità, copie e prezzi di tutti i negozi.</small></div></summary>
    <div className="market-rule-sections">
      <section><header><strong>Livelli</strong><small>Intervallo consentito e ricerca di alternative.</small></header><div className="market-rule-grid"><label>Livello minimo<input type="number" min="1" value={Number(rules.minLevel ?? 1)} onChange={(event) => update("minLevel", Number(event.target.value))} /></label><label>Livello massimo<input type="number" min="1" value={Number(rules.maxLevel ?? 10)} onChange={(event) => update("maxLevel", Number(event.target.value))} /></label></div><div className="market-fallback-levels"><span>Se manca il livello esatto:</span>{[-3, -2, -1, 0, 1, 2, 3].map((delta) => { const active = fallbacks.includes(delta); return <button type="button" key={delta} className={active ? "active" : ""} onClick={() => update("fallbackLevelDeltas", active ? fallbacks.filter((value) => value !== delta) : [...fallbacks, delta].sort((a, b) => Math.abs(a) - Math.abs(b) || a - b))}>{delta > 0 ? `+${delta}` : delta}</button>; })}</div></section>
      <section><header><strong>Quantità</strong><small>Formula base prima della dimensione del negozio.</small></header><div className="market-rule-grid"><label>Oggetti base<input type="number" min="0" step=".5" value={Number(rules.baseCount ?? 0)} onChange={(event) => update("baseCount", Number(event.target.value))} /></label><label>Per livello<input type="number" min="0" step=".5" value={Number(rules.countPerLevel ?? 0)} onChange={(event) => update("countPerLevel", Number(event.target.value))} /></label><label>Varianza %<input type="number" min="0" max="100" value={Math.round(Number(rules.countVariance ?? 0) * 100)} onChange={(event) => update("countVariance", Number(event.target.value) / 100)} /></label><label>Copie massime<input type="number" min="1" value={Number(rules.maximumCopies ?? 1)} onChange={(event) => update("maximumCopies", Number(event.target.value))} /></label></div><p className="market-rule-formula">Stima: (base + livello × per livello) × dimensione negozio, con la varianza scelta.</p></section>
      <section><header><strong>Rarità</strong><small>Le percentuali devono totalizzare 100%.</small></header><div className="market-rarity-grid">{[["1", "Comune"], ["2", "Non comune"], ["3", "Raro"], ["4", "Pregiato"]].map(([key, label]) => <label key={key}>{label}<span><input type="number" min="0" max="100" value={Math.round(Number(rarities[key] || 0) * 100)} onChange={(event) => update("rarityProbabilities", { ...rarities, [key]: Number(event.target.value) / 100 })} />%</span></label>)}</div><p className={Math.abs(rarityTotal - 1) < .001 ? "market-rule-total valid" : "market-rule-total invalid"}>Totale: {Math.round(rarityTotal * 100)}%</p></section>
      <section><header><strong>Prezzi</strong><small>Calcolati sul valore catalogo dell'oggetto.</small></header><div className="market-rule-grid"><label>Prezzo base %<input type="number" min="0" value={Number(rules.priceBasePercent ?? 0)} onChange={(event) => update("priceBasePercent", Number(event.target.value))} /></label><label>Per livello %<input type="number" min="0" value={Number(rules.priceLevelPercent ?? 0)} onChange={(event) => update("priceLevelPercent", Number(event.target.value))} /></label><label>Trattativa massima ±%<input type="number" min="0" max="100" value={Number(rules.maximumNegotiationPercent ?? 0)} onChange={(event) => update("maximumNegotiationPercent", Number(event.target.value))} /></label></div></section>
    </div>
  </details>;
}

function MarketSettings({ market, saving, onSave, onBatch }: {
  market: MarketData; saving: boolean; onSave: (values: Record<string, unknown>) => void; onBatch: (values: Record<string, unknown>) => void;
}) {
  const [locations, setLocations] = useState(() => structuredClone(market.configuration.locations));
  const [shopTypes, setShopTypes] = useState(() => structuredClone(market.configuration.shopTypes));
  const [rules, setRules] = useState(() => structuredClone(market.configuration.generatorRules));
  const [selectedRegion, setSelectedRegion] = useState(locations?.regions[0]?.key || "");
  const [regionName, setRegionName] = useState("");
  const [placeName, setPlaceName] = useState("");
  const [batch, setBatch] = useState({ count: 3, locationKey: market.locations[0]?.places[0]?.locationKey || "", categoryKey: market.shopTypes[0]?.key || "", level: 1, name: "" });
  const addRegion = () => {
    const key = slug(regionName);
    if (!locations || !key || locations.regions.some((region) => region.key === key)) return;
    setLocations({ ...locations, regions: [...locations.regions, { key, label: regionName.trim(), enabled: true, places: [] }] });
    setSelectedRegion(key); setRegionName("");
  };
  const addPlace = () => {
    const key = slug(placeName);
    if (!locations || !key || !selectedRegion) return;
    setLocations({ ...locations, regions: locations.regions.map((region) => region.key !== selectedRegion ? region : { ...region, places: region.places.some((place) => place.key === key) ? region.places : [...region.places, { key, label: placeName.trim(), enabled: true }] }) });
    setPlaceName("");
  };
  const toggleRegion = (key: string) => locations && setLocations({ ...locations, regions: locations.regions.map((region) => region.key === key ? { ...region, enabled: !region.enabled } : region) });
  const togglePlace = (regionKey: string, placeKey: string) => locations && setLocations({ ...locations, regions: locations.regions.map((region) => region.key !== regionKey ? region : { ...region, places: region.places.map((place) => place.key === placeKey ? { ...place, enabled: !place.enabled } : place) }) });
  const activeRegion = locations?.regions.find((region) => region.key === selectedRegion);
  return <details className="market-settings panel" data-component-type="accordion" data-theme="gold">
    <summary><span aria-hidden="true">⚙</span><div><small>Master e Admin</small><strong>Impostazioni Negozi</strong><p>Luoghi, tipi, categorie degli oggetti e regole di generazione.</p></div><b>Espandi</b></summary>
    <div className="market-settings-content">
      {locations && <section className="market-location-settings"><header><div><p className="eyebrow">Master e Admin</p><h3>Regioni e località</h3></div></header><div className="market-setting-region-buttons">{locations.regions.map((region) => <button type="button" key={region.key} className={region.key === selectedRegion ? "active" : ""} onClick={() => setSelectedRegion(region.key)}><span>{region.label}</span><small>{region.places.length}</small></button>)}</div><div className="market-setting-place-list"><header><strong>{activeRegion?.label || "Regione"}</strong><button type="button" className={activeRegion?.enabled ? "active" : ""} onClick={() => activeRegion && toggleRegion(activeRegion.key)}>{activeRegion?.enabled ? "Attiva" : "Disattivata"}</button></header>{activeRegion?.places.map((place) => <button type="button" key={place.key} className={place.enabled ? "active" : ""} onClick={() => togglePlace(activeRegion.key, place.key)}>{place.label}<span>{place.enabled ? "visibile" : "nascosta"}</span></button>)}</div><div className="market-setting-add"><input value={regionName} placeholder="Nuova regione" onChange={(event) => setRegionName(event.target.value)} /><button type="button" disabled={!regionName.trim()} onClick={addRegion}>Aggiungi regione</button></div><div className="market-setting-add"><input value={placeName} placeholder={`Nuova località in ${activeRegion?.label || "…"}`} onChange={(event) => setPlaceName(event.target.value)} /><button type="button" disabled={!placeName.trim() || !activeRegion} onClick={addPlace}>Aggiungi località</button></div></section>}
      {shopTypes && <ShopTypeRulesEditor shopTypes={shopTypes} itemTypes={market.configuration.itemTypes || []} onChange={setShopTypes} />}
      {rules && <GeneratorRulesEditor rules={rules} onChange={setRules} />}
      <footer><span>Le scorte esistenti cambiano solo dopo una rigenerazione.</span><button type="button" className="button primary" disabled={saving} onClick={() => onSave({ ...(locations ? { locations } : {}), ...(shopTypes ? { shopTypes } : {}), ...(rules ? { generatorRules: rules } : {}) })}>{saving ? "Salvataggio…" : "Salva impostazioni"}</button></footer>
      {market.permissions.canBatchCreate && <details className="market-batch-settings"><summary><span>＋</span><div><strong>Creazione multipla · Admin</strong><small>Crea fino a 20 negozi con scorte indipendenti.</small></div></summary><div className="market-batch-grid"><label>Numero<input type="number" min="1" max="20" value={batch.count} onChange={(event) => setBatch({ ...batch, count: Number(event.target.value) })} /></label><label>Prefisso nome<input value={batch.name} onChange={(event) => setBatch({ ...batch, name: event.target.value })} /></label><label>Località<select value={batch.locationKey} onChange={(event) => setBatch({ ...batch, locationKey: event.target.value })}>{market.locations.flatMap((region) => region.places.map((place) => <option key={place.locationKey} value={place.locationKey}>{region.label} · {place.label}</option>))}</select></label><label>Tipo<select value={batch.categoryKey} onChange={(event) => setBatch({ ...batch, categoryKey: event.target.value })}>{market.shopTypes.map((type) => <option key={type.key} value={type.key}>{type.label}</option>)}</select></label><label>Livello<input type="number" min="1" max="20" value={batch.level} onChange={(event) => setBatch({ ...batch, level: Number(event.target.value) })} /></label><button type="button" className="button secondary" disabled={saving} onClick={() => onBatch(batch)}>Crea gruppo</button></div></details>}
    </div>
  </details>;
}

function ItemDetail({ line, quantity, onClose, onSetQuantity }: {
  line: StockLine; quantity: number; onClose: () => void; onSetQuantity: (quantity: number) => void;
}) {
  return <aside className="market-item-detail" data-component-type="panel" data-theme="gold">
    <header>{line.item.imageUrl ? <img src={line.item.imageUrl} alt="" /> : <span>◇</span>}<button type="button" onClick={onClose} aria-label="Chiudi dettaglio">×</button></header>
    <div><p className="eyebrow">{line.item.rarityLabel || line.item.types[0] || "Oggetto"}</p><h3>{line.item.name}</h3><p>{line.item.description || "Nessuna descrizione disponibile."}</p><dl><div><dt>Prezzo</dt><dd>{line.unitPrice} monete</dd></div><div><dt>Disponibili</dt><dd>{line.quantity}</dd></div>{line.item.weight != null && <div><dt>Peso</dt><dd>{line.item.weight}</dd></div>}{line.item.region && <div><dt>Provenienza</dt><dd>{line.item.region}</dd></div>}</dl>{line.item.effects.length > 0 && <section><strong>Effetti</strong><ul>{line.item.effects.map((effect, index) => <li key={index}>{String(effect.name || effect.description || "Effetto")}</li>)}</ul></section>}</div>
    <footer><div className="market-quantity"><button type="button" disabled={quantity <= 0} onClick={() => onSetQuantity(Math.max(0, quantity - 1))}>−</button><output>{quantity}</output><button type="button" disabled={quantity >= line.quantity} onClick={() => onSetQuantity(Math.min(line.quantity, quantity + 1))}>＋</button></div><button type="button" className="button primary" disabled={quantity >= line.quantity} onClick={() => onSetQuantity(Math.min(line.quantity, quantity + 1))}>{quantity ? "Aggiungi ancora" : "Aggiungi al carrello"}</button></footer>
  </aside>;
}

function PurchaseSidebar({ shop, character, cart, negotiationPercent, maximumNegotiationPercent, pending, onSetQuantity, onSetNegotiation, onClear, onPurchase }: {
  shop: ShopDetail | null;
  character: MarketData["character"];
  cart: Record<number, number>;
  negotiationPercent: number;
  maximumNegotiationPercent: number;
  pending: boolean;
  onSetQuantity: (itemId: number, quantity: number) => void;
  onSetNegotiation: (value: number) => void;
  onClear: () => void;
  onPurchase: () => void;
}) {
  const lines = shop?.stock.filter((line) => cart[line.item.id] > 0) || [];
  const itemCount = lines.reduce((total, line) => total + (cart[line.item.id] || 0), 0);
  const baseTotal = lines.reduce((total, line) => total + line.unitPrice * (cart[line.item.id] || 0), 0);
  const total = Math.max(0, Math.round(baseTotal * (100 + negotiationPercent) / 100));
  const remaining = character ? character.coins - total : null;
  const changeNegotiation = (delta: number) => onSetNegotiation(Math.max(-maximumNegotiationPercent, Math.min(maximumNegotiationPercent, negotiationPercent + delta)));

  return <aside className="market-purchase-sidebar" data-component-type="action-bar" data-theme="gold" aria-label="Acquista e contratta">
    <header><p className="eyebrow">Commercio</p><h2>Acquista e contratta</h2><small>{shop?.name || "Scegli un negozio"}</small></header>
    <section className="market-purchase-coins"><span>Monete disponibili</span><strong>{character?.coins ?? "—"}</strong><small>{character?.name || "Nessun personaggio selezionato"}</small></section>
    <section className="market-purchase-cart">
      <header><strong>Carrello</strong><small>{itemCount} {itemCount === 1 ? "articolo" : "articoli"}</small></header>
      <div>{lines.map((line) => {
        const quantity = cart[line.item.id] || 0;
        return <article key={line.item.id}><div><strong>{line.item.name}</strong><small>{line.unitPrice} × {quantity} monete</small></div><div className="market-cart-quantity"><button type="button" onClick={() => onSetQuantity(line.item.id, Math.max(0, quantity - 1))} aria-label={`Rimuovi un ${line.item.name}`}>−</button><output>{quantity}</output><button type="button" disabled={quantity >= line.quantity} onClick={() => onSetQuantity(line.item.id, Math.min(line.quantity, quantity + 1))} aria-label={`Aggiungi un ${line.item.name}`}>＋</button></div></article>;
      })}</div>
      {!lines.length && <p>Gli articoli scelti compariranno qui.</p>}
    </section>
    <section className="market-haggle">
      <header><strong>Contrattazione</strong><small>Massimo ±{maximumNegotiationPercent}%</small></header>
      <div><button type="button" disabled={!lines.length || negotiationPercent <= -maximumNegotiationPercent} onClick={() => changeNegotiation(-5)}>−5%</button><output className={negotiationPercent < 0 ? "favorable" : negotiationPercent > 0 ? "unfavorable" : ""}>{negotiationPercent > 0 ? "+" : ""}{negotiationPercent}%</output><button type="button" disabled={!lines.length || negotiationPercent >= maximumNegotiationPercent} onClick={() => changeNegotiation(5)}>+5%</button></div>
      <small>Inserisci qui l'esito della contrattazione prima dell'acquisto.</small>
    </section>
    <section className="market-purchase-total">
      {negotiationPercent !== 0 && <span><small>Prezzo iniziale</small><s>{baseTotal} monete</s></span>}
      <span><small>Totale</small><strong>{total} monete</strong></span>
      <span className={remaining != null && remaining < 0 ? "insufficient" : ""}><small>Rimanenti</small><b>{remaining ?? "—"}</b></span>
    </section>
    <footer><button type="button" className="button secondary" disabled={!lines.length} onClick={onClear}>Svuota</button><button type="button" className="button primary" disabled={pending || !shop || !character || !lines.length || (remaining ?? -1) < 0} onClick={onPurchase}>{pending ? "Acquisto…" : "Acquista"}</button></footer>
  </aside>;
}

export function MarketPage() {
  const { personaggi, notify } = useApp();
  const queryClient = useQueryClient();
  const characterId = personaggi.giocatore.activePersonaggioId;
  const [regionKey, setRegionKey] = useState("");
  const [locationKey, setLocationKey] = useState("");
  const [navigationPanel, setNavigationPanel] = useState<"regions" | "locations" | null>("regions");
  const [selectedShopId, setSelectedShopId] = useState<number | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const [shopLevelFilter, setShopLevelFilter] = useState("");
  const [shopTypeFilter, setShopTypeFilter] = useState("");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [sort, setSort] = useState<"name" | "price" | "rarity">("name");
  const [cart, setCart] = useState<Record<number, number>>({});
  const [negotiationPercent, setNegotiationPercent] = useState(0);
  const [editing, setEditing] = useState<"new" | "edit" | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const params = new URLSearchParams();
  if (selectedShopId) params.set("selected_shop_id", String(selectedShopId));
  if (characterId) params.set("character_id", String(characterId));
  if (includeArchived) params.set("include_archived", "true");
  const marketQuery = useQuery({
    queryKey: ["market", selectedShopId, characterId, includeArchived],
    queryFn: () => getData<MarketData>(`/api/v1/market?${params}`),
    placeholderData: (previous) => previous,
  });
  const market = marketQuery.data;
  useEffect(() => {
    if (!market) return;
    const activeRegion = market.locations.find((region) => region.enabled && region.key === regionKey);
    if (regionKey && !activeRegion) {
      setRegionKey(""); setLocationKey(""); setSelectedShopId(null); setNavigationPanel("regions");
      return;
    }
    if (locationKey && !activeRegion?.places.some((place) => place.enabled && place.locationKey === locationKey)) {
      setLocationKey(""); setSelectedShopId(null); setNavigationPanel(activeRegion ? "locations" : "regions");
    }
  }, [market, regionKey, locationKey]);
  const regions = useMemo(() => (market?.locations || []).filter((region) => region.enabled).sort((left, right) => left.label.localeCompare(right.label, "it", { sensitivity: "base" })), [market]);
  const activeRegion = regions.find((region) => region.key === regionKey);
  const locations = useMemo(() => (activeRegion?.places || []).filter((place) => place.enabled).sort((left, right) => left.label.localeCompare(right.label, "it", { sensitivity: "base" })), [activeRegion]);
  const activeLocation = locations.find((place) => place.locationKey === locationKey);
  const locationShops = useMemo(() => (market?.shops || []).filter((shop) => shop.locationKey === locationKey).sort((left, right) => left.name.localeCompare(right.name, "it", { sensitivity: "base" })), [market, locationKey]);
  const shopLevels = useMemo(() => [...new Set(locationShops.map((shop) => shop.level))].sort((left, right) => left - right), [locationShops]);
  const locationShopTypes = useMemo(() => [...new Set(locationShops.map((shop) => shop.categoryKey))].sort((left, right) => (market?.shopTypes.find((type) => type.key === left)?.label || left).localeCompare(market?.shopTypes.find((type) => type.key === right)?.label || right, "it", { sensitivity: "base" })), [locationShops, market]);
  const shops = useMemo(() => locationShops.filter((shop) => (!shopLevelFilter || shop.level === Number(shopLevelFilter)) && (!shopTypeFilter || shop.categoryKey === shopTypeFilter)), [locationShops, shopLevelFilter, shopTypeFilter]);
  useEffect(() => {
    const nextShopId = resolveSelectedShopId(selectedShopId, shops, Boolean(market));
    if (nextShopId !== selectedShopId) setSelectedShopId(nextShopId);
  }, [market, shops, selectedShopId]);
  useEffect(() => { setCart({}); setSelectedItemId(null); setNegotiationPercent(0); }, [selectedShopId]);
  const selectedShop = market?.selectedShop?.id === selectedShopId ? market.selectedShop : null;
  const availableTypes = useMemo(() => [...new Set((selectedShop?.stock || []).flatMap((line) => line.item.types).filter(Boolean))].sort(), [selectedShop]);
  const visibleStock = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("it");
    return (selectedShop?.stock || []).filter((line) => (!normalized || `${line.item.name} ${line.item.description} ${line.item.rarityLabel}`.toLocaleLowerCase("it").includes(normalized)) && (!typeFilter || line.item.types.includes(typeFilter)) && (!maxPrice || line.unitPrice <= Number(maxPrice))).sort((a, b) => sort === "price" ? a.unitPrice - b.unitPrice : sort === "rarity" ? Number(b.item.rarity || 0) - Number(a.item.rarity || 0) : a.item.name.localeCompare(b.item.name));
  }, [selectedShop, query, typeFilter, maxPrice, sort]);
  const selectedLine = selectedShop?.stock.find((line) => line.item.id === selectedItemId) || null;
  const cartLines = selectedShop?.stock.filter((line) => cart[line.item.id] > 0).map((line) => ({ itemId: line.item.id, quantity: cart[line.item.id] })) || [];
  const maximumNegotiationPercent = Number(market?.configuration.limits.maximumNegotiationPercent || 0);
  const actionMutation = useMutation({
    mutationFn: ({ action, payload }: { action: string; payload: Record<string, unknown> }) => command<MarketActionData>(action, payload, "market"),
    onSuccess: async (response) => {
      if (response.data.market?.selectedShop) setSelectedShopId(response.data.market.selectedShop.id);
      setEditing(null); setCart({});
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["market"] }), queryClient.invalidateQueries({ queryKey: ["personaggi"] }), queryClient.invalidateQueries({ queryKey: ["character-sheet"] })]);
      notify(response.events[0]?.message || "Mercato aggiornato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  if (marketQuery.isLoading || !market) return <div className="page"><section className="panel"><p>Apertura del Mercato…</p></section></div>;
  if (marketQuery.error) return <div className="page"><section className="panel danger-panel"><p>{(marketQuery.error as Error).message}</p></section></div>;
  const selectedType = market.shopTypes.find((type) => type.key === selectedShop?.categoryKey);
  const saveShop = (values: ShopDraft) => actionMutation.mutate({ action: "market.shop.save", payload: { values: { ...values, shopId: editing === "edit" ? selectedShop?.id : undefined } } });
  return <div className="page market-page">
    <header className="page-header market-page-header"><div><p className="eyebrow">Commercio del mondo</p><h1>Mercato</h1><p>{market.character ? `${market.character.name} · ${market.character.coins} monete` : "Seleziona un personaggio per acquistare"}</p></div><div className="button-row">{market.permissions.canManage && <button className="button primary" onClick={() => setEditing("new")}>Nuovo negozio</button>}</div></header>
    {market.permissions.canManage && <MarketSettings market={market} saving={actionMutation.isPending} onSave={(values) => actionMutation.mutate({ action: "market.settings.save", payload: { values } })} onBatch={(values) => actionMutation.mutate({ action: "market.shop.batchCreate", payload: { values: { ...values, nameTemplate: values.name ? `${values.name} {number}` : undefined }, confirm: true } })} />}
    <div className="market-layout">
      <aside className="market-world-nav" data-component-type="accordion" data-theme="dark" aria-label="Regioni e località">
        <section className={navigationPanel === "regions" ? "market-nav-section active" : "market-nav-section compact"}>
          <button type="button" className="market-nav-heading" aria-expanded={navigationPanel === "regions"} onClick={() => setNavigationPanel("regions")}>
            {navigationPanel === "regions" ? <span><small>Navigazione</small><strong>Regioni</strong></span> : <span><small>Regione</small><strong>{activeRegion?.label || "Regioni"}</strong></span>}<b aria-hidden="true">⌄</b>
          </button>
          {navigationPanel === "regions" && <div className="market-nav-list" role="listbox" aria-label="Regioni">{regions.map((region) => <button type="button" role="option" key={region.key} className={region.key === regionKey ? "active" : ""} aria-selected={region.key === regionKey} onClick={() => { setRegionKey(region.key); setLocationKey(""); setSelectedShopId(null); setShopLevelFilter(""); setShopTypeFilter(""); setNavigationPanel("locations"); }}><span><strong>{region.label}</strong><small>{region.places.filter((place) => place.enabled).length} località</small></span><b>{region.shopCount}</b></button>)}</div>}
        </section>
        <section className={`${navigationPanel === "locations" ? "market-nav-section active" : "market-nav-section compact"} ${!activeRegion ? "disabled" : ""}`}>
          <button type="button" className="market-nav-heading" disabled={!activeRegion} aria-expanded={navigationPanel === "locations"} onClick={() => activeRegion && setNavigationPanel("locations")}>
            {navigationPanel === "locations" ? <span><small>{activeRegion?.label}</small><strong>Località</strong></span> : <span><small>Località</small><strong>{activeLocation?.label || "Scegli una regione"}</strong></span>}<b aria-hidden="true">⌄</b>
          </button>
          {navigationPanel === "locations" && <div className="market-nav-list" role="listbox" aria-label={`Località di ${activeRegion?.label || ""}`}>{locations.map((place) => <button type="button" role="option" key={place.locationKey} className={place.locationKey === locationKey ? "active" : ""} aria-selected={place.locationKey === locationKey} onClick={() => { setLocationKey(place.locationKey); setSelectedShopId(null); setShopLevelFilter(""); setShopTypeFilter(""); setNavigationPanel(null); }}><span><strong>{place.label}</strong><small>{place.shopCount} negozi</small></span><b>{place.shopCount}</b></button>)}</div>}
        </section>
      </aside>
      <main className="market-catalog" data-component-type="panel" data-theme="parchment">
        {activeLocation && <section className="market-shop-browser">
          <header><div><p className="eyebrow">{activeRegion?.label}</p><h2>Negozi · {activeLocation.label}</h2><small>{shops.length} di {locationShops.length} visibili</small></div><div className="market-shop-filters"><label>Grado<select value={shopLevelFilter} onChange={(event) => setShopLevelFilter(event.target.value)}><option value="">Tutti</option>{shopLevels.map((level) => <option key={level} value={level}>Livello {level}</option>)}</select></label><label>Tipo<select value={shopTypeFilter} onChange={(event) => setShopTypeFilter(event.target.value)}><option value="">Tutti</option>{locationShopTypes.map((key) => <option key={key} value={key}>{market.shopTypes.find((type) => type.key === key)?.label || key}</option>)}</select></label></div></header>
          <nav className="market-shop-nav market-location-nav skill-family-nav" aria-label={`Negozi di ${activeLocation.label}`} data-component-type="tabset" data-theme="gold">{shops.map((shop) => { const type = market.shopTypes.find((entry) => entry.key === shop.categoryKey); return <button type="button" key={shop.id} className={shop.id === selectedShopId ? "active" : ""} aria-pressed={shop.id === selectedShopId} onClick={() => setSelectedShopId(shop.id)}><span className="market-shop-icon">{shopIcon(type)}</span><span><strong>{shop.name}</strong><small>{type?.label || shop.categoryKey} · liv. {shop.level}</small></span><b>{shop.stockCount}</b>{shop.featured && <em>★</em>}</button>; })}</nav>
          {!shops.length && <p className="market-shop-filter-empty">{locationShops.length ? "Nessun negozio corrisponde ai filtri scelti." : "Non ci sono negozi in questa località."}</p>}
        </section>}
        {selectedShop ? <div className="market-shop-workspace">
          <header className="market-shop-heading" style={{ "--shop-art": selectedShop.backgroundUrl ? `url(${selectedShop.backgroundUrl})` : "none" } as CSSProperties}><div><p className="eyebrow">{selectedShop.regionName} · {selectedShop.placeName}</p><h2><span>{shopIcon(selectedType)}</span>{selectedShop.name}</h2><p>{selectedShop.owner ? `Gestito da ${selectedShop.owner}. ` : ""}{selectedShop.description || "Le merci disponibili cambiano con il livello e la regione."}</p><div className="market-shop-facts"><span>Livello {selectedShop.level}</span><span>{selectedShop.stockCount} oggetti</span><span>Scorte #{selectedShop.stockRevision}</span>{selectedShop.priceModifierPercent !== 0 && <span>Prezzi {selectedShop.priceModifierPercent > 0 ? "+" : ""}{selectedShop.priceModifierPercent}%</span>}</div></div>{market.permissions.canManage && <div className="market-shop-management"><button type="button" onClick={() => setEditing("edit")}>Modifica</button>{market.permissions.canRegenerate && <button type="button" disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ action: "market.shop.regenerate", payload: { shopId: selectedShop.id } })}>Rigenera</button>}{market.permissions.canArchive && <button type="button" className="danger" disabled={actionMutation.isPending} onClick={() => actionMutation.mutate({ action: "market.shop.state", payload: { shopId: selectedShop.id, archived: !selectedShop.archived } })}>{selectedShop.archived ? "Ripristina" : "Archivia"}</button>}</div>}</header>
          <details className="market-filters"><summary><span>⌕</span><strong>Cerca e filtra</strong><small>{visibleStock.length} di {selectedShop.stock.length}</small></summary><div><label className="market-search">Cerca<input type="search" value={query} placeholder="Nome, descrizione, rarità…" onChange={(event) => setQuery(event.target.value)} /></label><label>Prezzo massimo<input type="number" min="0" value={maxPrice} placeholder="Qualsiasi" onChange={(event) => setMaxPrice(event.target.value)} /></label><div className="market-filter-buttons"><button type="button" className={!typeFilter ? "active" : ""} onClick={() => setTypeFilter("")}>Tutti</button>{availableTypes.map((type) => <button type="button" key={type} className={typeFilter === type ? "active" : ""} onClick={() => setTypeFilter(type)}>{type}</button>)}</div><div className="market-sort-buttons"><span>Ordina</span><button type="button" className={sort === "name" ? "active" : ""} onClick={() => setSort("name")}>Nome</button><button type="button" className={sort === "price" ? "active" : ""} onClick={() => setSort("price")}>Prezzo</button><button type="button" className={sort === "rarity" ? "active" : ""} onClick={() => setSort("rarity")}>Rarità</button></div>{market.permissions.canManage && <label className="market-switch"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} /><span><strong>Mostra archiviati</strong></span></label>}</div></details>
          <div className={selectedLine ? "market-stock-layout has-detail" : "market-stock-layout"}><section className="market-stock-grid">{visibleStock.map((line) => <button type="button" key={line.item.id} className={`market-item-card ${selectedItemId === line.item.id ? "active" : ""}`} onClick={() => setSelectedItemId(line.item.id)}>{line.item.imageUrl ? <img src={line.item.imageUrl} alt="" /> : <span className="market-item-placeholder">◇</span>}<span className="market-item-copy"><small>{line.item.rarityLabel || line.item.types[0] || "Oggetto"}</small><strong>{line.item.name}</strong><span>{line.unitPrice} monete</span></span><span className="market-item-stock">{line.quantity}</span>{cart[line.item.id] > 0 && <b>{cart[line.item.id]} nel carrello</b>}</button>)}</section>{selectedLine && <ItemDetail line={selectedLine} quantity={cart[selectedLine.item.id] || 0} onClose={() => setSelectedItemId(null)} onSetQuantity={(quantity) => setCart((current) => ({ ...current, [selectedLine.item.id]: quantity }))} />}</div>
          {!visibleStock.length && <div className="market-empty"><span>◇</span><h3>Nessun oggetto trovato</h3><p>Prova a cambiare i filtri o chiedi al Master di rigenerare le scorte.</p></div>}
        </div> : <div className="market-empty"><span>⌂</span><h3>{activeLocation ? "Nessun negozio selezionato" : activeRegion ? "Scegli una località" : "Scegli una regione"}</h3><p>{activeLocation ? (market.permissions.canManage ? "Crea il primo negozio oppure modifica i filtri." : "Modifica i filtri o scegli un'altra località.") : "Usa i due elenchi a sinistra per entrare nel mercato."}</p>{activeLocation && market.permissions.canManage && !locationShops.length && <button className="button primary" onClick={() => setEditing("new")}>Crea negozio</button>}</div>}
      </main>
      <PurchaseSidebar shop={selectedShop} character={market.character} cart={cart} negotiationPercent={negotiationPercent} maximumNegotiationPercent={maximumNegotiationPercent} pending={actionMutation.isPending} onSetQuantity={(itemId, quantity) => setCart((current) => ({ ...current, [itemId]: quantity }))} onSetNegotiation={setNegotiationPercent} onClear={() => { setCart({}); setNegotiationPercent(0); }} onPurchase={() => actionMutation.mutate({ action: "market.purchase", payload: { characterId: market.character?.id, shopId: selectedShop?.id, stockRevision: selectedShop?.stockRevision, lines: cartLines, negotiationPercent } })} />
    </div>
    {editing && <ShopEditor key={`${editing}-${selectedShop?.id || "new"}`} market={market} shop={editing === "edit" ? selectedShop : null} saving={actionMutation.isPending} onClose={() => setEditing(null)} onSave={saveShop} />}
  </div>;
}
