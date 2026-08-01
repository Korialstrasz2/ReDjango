import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../../App";
import { Modal } from "../../components/Modal";
import { command, getData } from "../../lib/api";
import type { MarketActionData, MarketData, ShopDetail, ShopDraft, StockLine } from "./types";
import { shopIcon } from "./ui";

export function resolveSelectedShopId(
  currentShopId: number | null,
  availableShops: Array<{ id: number }>,
  hasMarketData: boolean,
): number | null {
  if (!hasMarketData) return currentShopId;
  if (currentShopId && availableShops.some((shop) => shop.id === currentShopId)) return currentShopId;
  return availableShops[0]?.id ?? null;
}

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
  return <Modal surface="market-shop-editor" title={shop ? `Modifica · ${shop.name}` : "Nuovo negozio"} onClose={onClose} wide className="market-shop-modal" footer={<>
    <button type="button" className="button secondary" onClick={onClose}>Annulla</button>
    <button type="submit" form="market-shop-form" className="button primary" disabled={saving || !draft.locationKey || !draft.categoryKey}>{saving ? "Salvataggio…" : shop ? "Salva negozio" : "Crea e genera"}</button>
  </>}>
    <form id="market-shop-form" className="market-shop-editor" onSubmit={(event) => { event.preventDefault(); onSave(draft); }}>
      <section className="market-editor-copy"><label>Nome<input autoFocus value={draft.name} placeholder="Generato automaticamente se vuoto" onChange={(event) => update("name", event.target.value)} /></label><label>Proprietario<input value={draft.owner} onChange={(event) => update("owner", event.target.value)} /></label><label className="wide">Descrizione<textarea rows={3} value={draft.description} onChange={(event) => update("description", event.target.value)} /></label></section>
      <section className="market-editor-choice"><header><small>1</small><div><h3>Regione</h3><p>Scegli l'area del mondo.</p></div></header><div>{market.locations.filter((region) => region.enabled).map((region) => <button type="button" key={region.key} className={region.key === selectedRegion?.key ? "active" : ""} onClick={() => update("locationKey", region.places.find((place) => place.enabled)?.locationKey || "")}>{region.label}</button>)}</div></section>
      <section className="market-editor-choice"><header><small>2</small><div><h3>Località</h3><p>{selectedRegion?.label || "Prima scegli una regione"}.</p></div></header><div>{selectedRegion?.places.filter((place) => place.enabled).map((place) => <button type="button" key={place.locationKey} className={place.locationKey === selectedPlace?.locationKey ? "active" : ""} onClick={() => update("locationKey", place.locationKey)}>{place.label}</button>)}</div></section>
      <section className="market-editor-choice wide"><header><small>3</small><div><h3>Tipo di negozio</h3><p>Influenza la composizione delle scorte.</p></div></header><div>{market.shopTypes.filter((type) => type.enabled).map((type) => <button type="button" key={type.key} className={type.key === draft.categoryKey ? "active" : ""} onClick={() => update("categoryKey", type.key)}><span>{shopIcon(type)}</span>{type.label}</button>)}</div></section>
      <section className="market-editor-numbers wide">
        <label>Livello<input type="number" min={market.configuration.limits.minLevel || 1} max={market.configuration.limits.maxLevel || 20} value={draft.level} onChange={(event) => update("level", Number(event.target.value))} /></label>
        <label>Modifica prezzi %<input type="number" min="-50" max="100" value={draft.priceModifierPercent} onChange={(event) => update("priceModifierPercent", Number(event.target.value))} /></label>
        <label>Seed<input value={draft.seed} placeholder="Automatico" onChange={(event) => update("seed", event.target.value)} /></label>
        <label className="market-switch"><input type="checkbox" checked={draft.featured} onChange={(event) => update("featured", event.target.checked)} /><span><strong>In evidenza</strong><small>Mostralo per primo.</small></span></label>
        <label className="market-switch"><input type="checkbox" checked={draft.generateStock} onChange={(event) => update("generateStock", event.target.checked)} /><span><strong>Genera scorte</strong><small>Ricrea l'inventario al salvataggio.</small></span></label>
      </section>
    </form>
  </Modal>;
}

const UNKNOWN_FACT = "—";

/** Everything the catalogue knows about a piece, in the order a buyer asks for it. */
function stockFacts(line: StockLine): Array<{ label: string; value: string }> {
  const { item } = line;
  // Gli spazi extra accettano quasi tutto: elencarli riempirebbe la riga senza
  // dire nulla che distingua questo oggetto da quello accanto.
  const slots = item.compatibleEquipmentSlots.filter((slot) => !slot.startsWith("extra_slot_"));
  const facts = [
    { label: "Prezzo", value: `${line.unitPrice} monete` },
    { label: "Disponibili", value: String(line.quantity) },
    { label: "Rarità", value: item.rarityLabel || UNKNOWN_FACT },
    { label: "Peso", value: item.weight == null ? UNKNOWN_FACT : String(item.weight) },
    { label: "Valore di catalogo", value: item.value == null ? UNKNOWN_FACT : `${item.value} monete` },
    { label: "Livello di bottino", value: item.lootLevel || UNKNOWN_FACT },
    { label: "Provenienza", value: item.region || "Nessuna regione" },
    { label: "Slot", value: slots.length ? slots.map((slot) => slot.replace(/_/g, " ")).join(", ") : item.compatibleEquipmentSlots.length ? "Solo spazi extra" : "Non equipaggiabile" },
  ];
  if (item.actionPointCost != null) facts.push({ label: "PA per attacco", value: String(item.actionPointCost) });
  return facts;
}

function ItemDetail({ line, quantity, position, total, onClose, onSetQuantity, onStep }: {
  line: StockLine; quantity: number; position: number; total: number;
  onClose: () => void; onSetQuantity: (quantity: number) => void; onStep: (delta: number) => void;
}) {
  const { item } = line;
  const weapon = [
    { label: "Categoria", value: item.weaponType },
    { label: "Lunghezza", value: item.weaponLength },
    { label: "Potenza", value: item.weaponPower },
  ].filter((entry) => entry.value);
  const add = () => onSetQuantity(Math.min(line.quantity, quantity + 1));
  // La scheda vive in una finestra invece che in una terza colonna: il banco
  // resta largo quanto la pagina e la merce ha lo spazio per raccontarsi.
  return <Modal surface="market-item" title={item.name} onClose={onClose} wide className="market-item-modal" footer={<>
    <div className="market-item-paging"><button type="button" disabled={total < 2} onClick={() => onStep(-1)} aria-label="Oggetto precedente">‹</button><small>{position} di {total}</small><button type="button" disabled={total < 2} onClick={() => onStep(1)} aria-label="Oggetto successivo">›</button></div>
    <div className="market-quantity"><button type="button" disabled={quantity <= 0} onClick={() => onSetQuantity(Math.max(0, quantity - 1))} aria-label="Togli una unità">−</button><output>{quantity}</output><button type="button" disabled={quantity >= line.quantity} onClick={add} aria-label="Aggiungi una unità">＋</button></div>
    <button type="button" className="button primary" disabled={quantity >= line.quantity} onClick={add}>{quantity ? "Aggiungi ancora" : "Aggiungi al carrello"}</button>
  </>}>
    <div className="market-item-sheet">
      <aside className="market-item-portrait">
        {item.imageUrl ? <img src={item.imageUrl} alt="" /> : <span className="market-item-placeholder">◇</span>}
        <p className="eyebrow">{item.rarityLabel || "Oggetto"}</p>
        {item.types.filter(Boolean).length > 0 && <ul>{item.types.filter(Boolean).map((type) => <li key={type}>{type}</li>)}</ul>}
      </aside>
      <div className="market-item-body">
        <p className="market-item-description">{item.description || "Nessuna descrizione disponibile."}</p>
        <dl className="market-item-data">{stockFacts(line).map((fact) => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>
        {item.effectSummaries.length > 0 && <section className="market-item-effects"><strong>Effetti</strong><ul>{item.effectSummaries.map((effect, index) => <li key={index}><span>{effect.label}</span><b>{effect.value}</b>{effect.condition && <small>se {effect.condition}</small>}</li>)}</ul></section>}
        {weapon.length > 0 && <section className="market-item-effects"><strong>Profilo d'arma</strong><ul>{weapon.map((entry) => <li key={entry.label}><span>{entry.label}</span><b>{entry.value}</b></li>)}</ul></section>}
        {item.specialRules?.trim() && <section className="item-special-rules"><strong>Regole speciali</strong><p>{item.specialRules}</p></section>}
      </div>
    </div>
  </Modal>;
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
  const regions = useMemo(() => (market?.locations || []).filter((region) => region.enabled), [market]);
  const activeRegion = regions.find((region) => region.key === regionKey);
  const locations = useMemo(() => (activeRegion?.places || []).filter((place) => place.enabled), [activeRegion]);
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
  const detailIndex = visibleStock.findIndex((line) => line.item.id === selectedItemId);
  const selectedLine = detailIndex < 0 ? null : visibleStock[detailIndex];
  const stepDetail = (delta: number) => setSelectedItemId(visibleStock[(detailIndex + delta + visibleStock.length) % visibleStock.length].item.id);
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
          <section className="market-stock-grid">{visibleStock.map((line) => <button type="button" key={line.item.id} title={line.item.name} className={`market-item-card ${selectedItemId === line.item.id ? "active" : ""}`} onClick={() => setSelectedItemId(line.item.id)}>{line.item.imageUrl ? <img src={line.item.imageUrl} alt="" /> : <span className="market-item-placeholder">◇</span>}<span className="market-item-copy"><small>{line.item.rarityLabel || line.item.types[0] || "Oggetto"}</small><strong>{line.item.name}</strong><span>{line.unitPrice} monete</span></span><span className="market-item-stock">{line.quantity}</span>{cart[line.item.id] > 0 && <b>{cart[line.item.id]} nel carrello</b>}</button>)}</section>
          {!visibleStock.length && <div className="market-empty"><span>◇</span><h3>Nessun oggetto trovato</h3><p>Prova a cambiare i filtri o chiedi al Master di rigenerare le scorte.</p></div>}
        </div> : <div className="market-empty"><span>⌂</span><h3>{activeLocation ? "Nessun negozio selezionato" : activeRegion ? "Scegli una località" : "Scegli una regione"}</h3><p>{activeLocation ? (market.permissions.canManage ? "Crea il primo negozio oppure modifica i filtri." : "Modifica i filtri o scegli un'altra località.") : "Usa i due elenchi a sinistra per entrare nel mercato."}</p>{activeLocation && market.permissions.canManage && !locationShops.length && <button className="button primary" onClick={() => setEditing("new")}>Crea negozio</button>}</div>}
      </main>
      <PurchaseSidebar shop={selectedShop} character={market.character} cart={cart} negotiationPercent={negotiationPercent} maximumNegotiationPercent={maximumNegotiationPercent} pending={actionMutation.isPending} onSetQuantity={(itemId, quantity) => setCart((current) => ({ ...current, [itemId]: quantity }))} onSetNegotiation={setNegotiationPercent} onClear={() => { setCart({}); setNegotiationPercent(0); }} onPurchase={() => actionMutation.mutate({ action: "market.purchase", payload: { characterId: market.character?.id, shopId: selectedShop?.id, stockRevision: selectedShop?.stockRevision, lines: cartLines, negotiationPercent } })} />
    </div>
    {selectedLine && <ItemDetail line={selectedLine} quantity={cart[selectedLine.item.id] || 0} position={detailIndex + 1} total={visibleStock.length} onStep={stepDetail} onClose={() => setSelectedItemId(null)} onSetQuantity={(quantity) => setCart((current) => ({ ...current, [selectedLine.item.id]: quantity }))} />}
    {editing && <ShopEditor key={`${editing}-${selectedShop?.id || "new"}`} market={market} shop={editing === "edit" ? selectedShop : null} saving={actionMutation.isPending} onClose={() => setEditing(null)} onSave={saveShop} />}
  </div>;
}
