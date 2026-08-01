import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Modal } from "../../components/Modal";
import { getData } from "../../lib/api";
import type {
  CompendiumAxis,
  CompendiumItem,
  CompendiumPage,
  CompendiumReference,
  CompendiumWeaponCategory,
} from "../../lib/types";
import { InfoPopover } from "./InfoPopover";

const PAGE_SIZE = 48;

// Rispecchia backend.core.item_selectors.NONE_SENTINEL: un valore "vuoto"
// dichiarato, diverso da "" che significa filtro non applicato.
const NONE_SENTINEL = "__none__";

const RARITY_STEPS = 5;

type Filters = {
  query: string;
  category: string;
  subtype: string;
  variant: string;
  grade: string;
  weaponCategory: string;
  rarity: string;
  region: string;
  lootLevel: string;
  weightMin: string;
  weightMax: string;
  valueMin: string;
  valueMax: string;
  withEffects: boolean;
  sort: string;
};

const EMPTY_FILTERS: Filters = {
  query: "", category: "", subtype: "", variant: "", grade: "", weaponCategory: "",
  rarity: "", region: "", lootLevel: "", weightMin: "", weightMax: "", valueMin: "",
  valueMax: "", withEffects: false, sort: "",
};

function labelOf(options: Array<{ value: string; label: string }>, value: string): string {
  return options.find((option) => option.value === value)?.label || value;
}

function numberText(value: number | null | undefined, unit = ""): string {
  if (value == null) return "—";
  const text = Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
  return unit ? `${text} ${unit}` : text;
}

/** Rarità come fila di gemme: leggibile anche senza distinguere i colori. */
function RarityGems({ rarity, label }: { rarity: number | null | undefined; label: string }) {
  if (rarity == null) return <span className="compendium-rarity" data-rarity="none">Rarità non indicata</span>;
  if (rarity === 0) return <span className="compendium-rarity" data-rarity="0"><b aria-hidden="true">❖</b>{label}</span>;
  return <span className="compendium-rarity" data-rarity={rarity}>
    <b aria-hidden="true">{"◆".repeat(rarity)}{"◇".repeat(Math.max(0, RARITY_STEPS - rarity))}</b>
    Rarità {label}
  </span>;
}

function ChipRow({ children }: { children: ReactNode }) {
  return <div className="compendium-chips">{children}</div>;
}

function Chip({ label, value }: { label: string; value: ReactNode }) {
  return <span className="compendium-chip"><small>{label}</small><strong>{value}</strong></span>;
}

/** Nota di un asse della categoria d'arma (lunghezza, pesantezza, danno…). */
function AxisNote({ axis, value, fallback }: { axis: CompendiumAxis | undefined; value: string; fallback: string }) {
  const option = axis?.options.find((entry) => entry.value === value);
  if (!axis || !option) return <strong>{fallback || "—"}</strong>;
  return <InfoPopover label={option.label} title={`${axis.label}: ${option.label}`} className="codex-link-inline">
    <p>{axis.note}</p>
    {option.note && <p>{option.note}</p>}
    {option.notes.length > 0 && <ul>{option.notes.map((note) => <li key={note}>{note}</li>)}</ul>}
    {!option.notes.length && !option.note && <p className="muted-copy">Questo valore non aggiunge modificatori.</p>}
  </InfoPopover>;
}

/** Il potere unico e il profilo completo della categoria a cui appartiene l'arma. */
function WeaponCategoryNote({ category, axes, compact = false }: {
  category: CompendiumWeaponCategory;
  axes: Record<string, CompendiumAxis>;
  compact?: boolean;
}) {
  return <InfoPopover
    label={compact ? <>❖ {category.label}</> : category.label}
    title={`Categoria d'arma: ${category.label}`}
    className={compact ? "codex-link-chip" : "codex-link-inline"}
  >
    {category.uniquePowers.length > 0
      ? <><strong className="codex-note-lead">Potere unico</strong><ul>{category.uniquePowers.map((power) => <li key={power}>{power}</li>)}</ul></>
      : <p className="muted-copy">Questa categoria non ha un potere unico dichiarato.</p>}
    <dl className="codex-note-data">
      {category.combatModeLabel && <div><dt>Uso</dt><dd>{category.combatModeLabel}</dd></div>}
      {category.lengthLabel && <div><dt>Lunghezza</dt><dd>{category.lengthLabel}{category.lengthNote ? ` · ${category.lengthNote}` : ""}</dd></div>}
      {category.heavinessLabel && <div><dt>Pesantezza</dt><dd>{category.heavinessLabel}{category.heavinessNotes.length ? ` · ${category.heavinessNotes.join(", ")}` : ""}</dd></div>}
      {category.powerLabel && <div><dt>Precisione</dt><dd>{category.powerLabel}{axes.power?.note ? "" : ""}</dd></div>}
      {category.damageTypeLabel && <div><dt>Danno</dt><dd>{category.damageTypeLabel}{category.damageNotes.length ? ` · ${category.damageNotes.join(", ")}` : ""}</dd></div>}
      {category.handlingLabel && <div><dt>Impugnatura</dt><dd>{category.handlingLabel}</dd></div>}
      {category.actionPointCost != null && <div><dt>PA per attacco</dt><dd>{category.actionPointCost}</dd></div>}
      {category.baseRangeMeters != null && <div><dt>Gittata base</dt><dd>{category.baseRangeMeters} m</dd></div>}
      {category.ammunitionLabel && <div><dt>Munizioni</dt><dd>{category.ammunitionLabel}</dd></div>}
      {category.magazineSize != null && <div><dt>Caricatore</dt><dd>{category.magazineSize}</dd></div>}
      {category.reloadBaseCost != null && <div><dt>Ricarica</dt><dd>{category.reloadBaseCost} PA{category.reloadPerProjectileCost != null ? ` + ${category.reloadPerProjectileCost} PA per proiettile` : ""}</dd></div>}
      {category.costBandLabel && <div><dt>Banda di prezzo</dt><dd>{category.costBand} · {category.costBandLabel}</dd></div>}
    </dl>
    {category.specialRules.length > 0 && <>
      <strong className="codex-note-lead">Regole della modalità</strong>
      <ul>{category.specialRules.map((rule) => <li key={rule}>{rule}</li>)}</ul>
    </>}
    {category.incomplete && <p className="muted-copy">Il profilo di questa categoria è incompleto: il Master applica le sue regole a mano.</p>}
  </InfoPopover>;
}

function ProfileRows({ profile }: { profile: Record<string, unknown> }) {
  return <dl className="compendium-data">
    {Object.entries(profile).map(([key, value]) => <div key={key}>
      <dt>{key}</dt>
      <dd>{Array.isArray(value) ? value.join(", ") : typeof value === "object" && value !== null ? JSON.stringify(value) : String(value)}</dd>
    </div>)}
  </dl>;
}

function ItemSheet({ item, reference, onClose }: {
  item: CompendiumItem;
  reference: CompendiumReference;
  onClose: () => void;
}) {
  const glossary = (key: string) => reference.glossary.find((entry) => entry.key === key);
  const rarity = reference.rarityChoices.find((choice) => choice.value === item.rarity);
  const category = reference.weaponCategories.find((entry) => entry.key === item.weaponCategory);
  const targetLabel = (value: string) => labelOf(reference.effectTargets, value);
  const operationLabel = (value: string) => reference.effectOperations.find((entry) => entry.value === value)?.label || value;
  const typeGroups = reference.typeGroups;
  const primary = typeGroups[0]?.options.find((option) => option.value === item.typeValues[0]);

  const note = (key: string) => {
    const entry = glossary(key);
    return entry ? <InfoPopover label={entry.title} title={entry.title} className="codex-link-label"><p>{entry.text}</p></InfoPopover> : entry;
  };

  return <Modal surface="item-detail" title={item.name} wide className="compendium-sheet" onClose={onClose} footer={
    <button type="button" className="button secondary" onClick={onClose}>Chiudi</button>
  }>
    <header className="compendium-sheet-heading">
      <img src={item.imageUrl} alt="" />
      <div>
        <p className="eyebrow">{primary?.label || item.typeValues[0] || "Oggetto"}</p>
        <h3>{item.name}</h3>
        <RarityGems rarity={item.rarity} label={item.rarityLabel} />
        {item.description && <p className="compendium-flavour">{item.description}</p>}
      </div>
    </header>

    <section className="compendium-sheet-section">
      <h4>Dati</h4>
      <dl className="compendium-data">
        <div><dt>{note("valore") || "Valore"}</dt><dd>{item.value == null ? "—" : `${item.value} monete`}</dd></div>
        <div><dt>{note("peso") || "Peso"}</dt><dd>{numberText(item.weight)}</dd></div>
        <div>
          <dt>{rarity
            ? <InfoPopover label="Rarità" title={`Rarità ${rarity.label}`} className="codex-link-label">
              <p>{rarity.note}</p>
              {rarity.shopShare != null && <p>Nelle scorte generate di un negozio questa fascia copre circa il {Math.round(rarity.shopShare * 100)}% dei pezzi.</p>}
            </InfoPopover>
            : "Rarità"}</dt>
          <dd>{item.rarityLabel || "—"}</dd>
        </div>
        <div>
          <dt>{note("lv_loot") || "Livello di bottino"}</dt>
          <dd>{item.lootLevel || "—"}{item.lootLevels.length > 1 ? ` · livelli ${item.lootLevels.join(", ")}` : ""}</dd>
        </div>
        <div>
          <dt>{note("regione") || "Regione"}</dt>
          <dd>{item.region || "Nessuna regione"}{item.regionWeight != null ? ` · peso ${numberText(item.regionWeight)}` : ""}</dd>
        </div>
        {item.actionPointCost != null && <div>
          <dt>{note("pa") || "PA per attacco"}</dt>
          <dd>{item.actionPointCost}</dd>
        </div>}
        <div>
          <dt>{note("slot") || "Slot"}</dt>
          <dd>{item.equipmentSlots.length ? item.equipmentSlots.join(", ") : "Non equipaggiabile"}</dd>
        </div>
      </dl>
    </section>

    <section className="compendium-sheet-section">
      <h4>Classificazione</h4>
      <dl className="compendium-data">
        {typeGroups.map((group, index) => {
          const value = item.typeValues[index] || "";
          const option = group.options.find((entry) => entry.value === value);
          return <div key={group.position}>
            <dt><InfoPopover label={group.label} title={group.label} className="codex-link-label"><p>{group.note}</p></InfoPopover></dt>
            <dd>{option?.label || value || "—"}</dd>
          </div>;
        })}
      </dl>
    </section>

    {category && <section className="compendium-sheet-section compendium-weapon-section" data-component-type="card" data-theme="combat">
      <h4>Categoria d'arma · <WeaponCategoryNote category={category} axes={reference.weaponAxes} /></h4>
      {category.uniquePowers.length > 0
        ? <aside className="compendium-unique-power"><strong>Potere unico della categoria</strong><ul>{category.uniquePowers.map((power) => <li key={power}>{power}</li>)}</ul></aside>
        : <p className="muted-copy">Questa categoria non dichiara un potere unico.</p>}
      <ChipRow>
        {category.combatModeLabel && <Chip label="Uso" value={category.combatModeLabel} />}
        <Chip label="Lunghezza" value={<AxisNote axis={reference.weaponAxes.length} value={category.length} fallback={category.lengthLabel} />} />
        <Chip label="Pesantezza" value={<AxisNote axis={reference.weaponAxes.heaviness} value={category.heaviness} fallback={category.heavinessLabel} />} />
        <Chip label="Precisione" value={<AxisNote axis={reference.weaponAxes.power} value={category.power} fallback={category.powerLabel} />} />
        <Chip label="Danno" value={<AxisNote axis={reference.weaponAxes.damageType} value={category.damageType} fallback={category.damageTypeLabel} />} />
        {category.handlingLabel && <Chip label="Impugnatura" value={category.handlingLabel} />}
        {category.actionPointCost != null && <Chip label="PA della categoria" value={category.actionPointCost} />}
        {category.baseRangeMeters != null && <Chip label="Gittata base" value={`${category.baseRangeMeters} m`} />}
        {category.ammunitionLabel && <Chip label="Munizioni" value={category.ammunitionLabel} />}
        {category.magazineSize != null && <Chip label="Caricatore" value={category.magazineSize} />}
        {category.costBandLabel && <Chip label="Banda" value={`${category.costBand} · ${category.costBandLabel}`} />}
      </ChipRow>
      {category.specialRules.length > 0 && <ul className="compendium-rule-list">{category.specialRules.map((rule) => <li key={rule}>{rule}</li>)}</ul>}
    </section>}

    <section className="compendium-sheet-section">
      <h4>{note("effetti") || "Effetti automatici"}</h4>
      {item.operations.length ? <ul className="compendium-effect-list">
        {item.operations.map((operation, index) => <li key={index}>
          <strong>{targetLabel(operation.target)}</strong>
          <span>{operationLabel(operation.operation)} {operation.value}</span>
          {operation.condition && <small>solo se {operation.condition}</small>}
        </li>)}
      </ul> : <p className="muted-copy">Nessun effetto calcolato automaticamente.</p>}
    </section>

    {item.specialRules.trim() && <section className="compendium-sheet-section">
      <h4>{note("regole_speciali") || "Regole speciali"}</h4>
      <p className="compendium-rule-text">{item.specialRules}</p>
    </section>}

    {item.elderEffects.length > 0 && <section className="compendium-sheet-section">
      <h4>{note("effetti_elder") || "Effetti descritti a testo"}</h4>
      <ul className="compendium-rule-list">{item.elderEffects.map((text, index) => <li key={index}>{text}</li>)}</ul>
    </section>}

    {Object.keys(item.weaponProfile).length > 0 && <section className="compendium-sheet-section">
      <h4>Profilo d'arma dell'oggetto</h4>
      <p className="muted-copy">Questo pezzo salva un profilo proprio, che sostituisce quello della sua categoria.</p>
      <ProfileRows profile={item.weaponProfile as Record<string, unknown>} />
    </section>}
  </Modal>;
}

function ItemCard({ item, reference, onOpen }: {
  item: CompendiumItem;
  reference: CompendiumReference;
  onOpen: () => void;
}) {
  const primary = reference.typeGroups[0]?.options.find((option) => option.value === item.typeValues[0]);
  const secondary = reference.typeGroups[1]?.options.find((option) => option.value === item.typeValues[1]);
  const category = reference.weaponCategories.find((entry) => entry.key === item.weaponCategory);
  return <article className="compendium-card" data-component-type="card" data-theme="parchment" data-rarity={item.rarity ?? "none"}>
    <button type="button" className="compendium-card-open" onClick={onOpen}>
      <img src={item.imageUrl} alt="" loading="lazy" />
      <span className="compendium-card-copy">
        <small>{primary?.label || item.typeValues[0] || "Oggetto"}{secondary ? ` · ${secondary.label}` : ""}</small>
        <strong>{item.name}</strong>
        <RarityGems rarity={item.rarity} label={item.rarityLabel} />
      </span>
    </button>
    <footer className="compendium-card-footer">
      <span title="Valore in monete">¤ {item.value ?? "—"}</span>
      <span title="Peso">⚖ {numberText(item.weight)}</span>
      {item.lootLevel && <span title="Livello di bottino">lv {item.lootLevel}</span>}
      {item.operations.length > 0 && <span title={`${item.operations.length} effetti automatici`}>✦ {item.operations.length}</span>}
      {category && <WeaponCategoryNote category={category} axes={reference.weaponAxes} compact />}
    </footer>
  </article>;
}

export function ItemCompendium() {
  const [draft, setDraft] = useState("");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [offset, setOffset] = useState(0);
  const [openItem, setOpenItem] = useState<CompendiumItem | null>(null);

  // Il catalogo è troppo grande per filtrarlo nel browser: la ricerca guida la
  // richiesta e il ritardo evita una chiamata per ogni tasto premuto.
  useEffect(() => {
    const timer = window.setTimeout(() => setFilters((current) => ({ ...current, query: draft.trim() })), 300);
    return () => window.clearTimeout(timer);
  }, [draft]);

  const referenceQuery = useQuery({
    queryKey: ["compendium-reference"],
    queryFn: () => getData<CompendiumReference>("/api/v1/compendium/items/reference"),
    staleTime: 10 * 60 * 1000,
  });

  const parameters = useMemo(() => {
    const search = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    const entries: Array<[string, string]> = [
      ["query", filters.query],
      ["type_1", filters.category],
      ["type_2", filters.subtype],
      ["type_3", filters.variant],
      ["type_4", filters.grade],
      ["weapon_category", filters.weaponCategory],
      ["rarity", filters.rarity],
      ["region", filters.region],
      ["loot_level", filters.lootLevel],
      ["weight_min", filters.weightMin],
      ["weight_max", filters.weightMax],
      ["value_min", filters.valueMin],
      ["value_max", filters.valueMax],
      ["sort", filters.sort],
    ];
    entries.forEach(([key, value]) => { if (value) search.set(key, value); });
    if (filters.withEffects) search.set("with_effects", "true");
    return search;
  }, [filters, offset]);

  const pageQuery = useQuery({
    queryKey: ["compendium-items", parameters.toString()],
    queryFn: () => getData<CompendiumPage>(`/api/v1/compendium/items?${parameters}`),
    placeholderData: (previous) => previous,
    enabled: referenceQuery.isSuccess,
  });

  const update = <Key extends keyof Filters>(key: Key, value: Filters[Key]) => {
    setOffset(0);
    // Cambiare categoria azzera il sottotipo: le opzioni disponibili cambiano.
    setFilters((current) => ({ ...current, [key]: value, ...(key === "category" ? { subtype: "" } : {}) }));
  };
  const reset = () => { setDraft(""); setFilters(EMPTY_FILTERS); setOffset(0); };

  const reference = referenceQuery.data;
  const page = pageQuery.data;
  const items = page?.items || [];
  const total = page?.total ?? 0;
  const subtypeOptions = useMemo(() => {
    const all = reference?.typeGroups[1]?.options || [];
    const allowed = filters.category ? reference?.subtypesByCategory[filters.category] : undefined;
    return allowed ? all.filter((option) => allowed.includes(option.value)) : all;
  }, [reference, filters.category]);
  const hasFilters = draft !== "" || JSON.stringify(filters) !== JSON.stringify(EMPTY_FILTERS);

  if (referenceQuery.isLoading) return <p className="muted-copy">Apertura del compendio…</p>;
  if (referenceQuery.error || !reference) {
    return <aside className="callout guide-warning">
      <strong>Compendio non disponibile</strong>
      <p>{(referenceQuery.error as Error | null)?.message || "Il catalogo degli oggetti non ha risposto."}</p>
    </aside>;
  }

  return <div className="item-compendium">
    <div className="compendium-toolbar" data-component-type="toolbar" data-theme="parchment">
      <label className="compendium-search">
        <span>Cerca nel compendio</span>
        <input type="search" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Nome, descrizione, categoria…" />
      </label>
      <label>
        <span>Ordina</span>
        <select value={filters.sort} onChange={(event) => update("sort", event.target.value)}>
          {reference.sortOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <p className="compendium-count">
        <strong>{total.toLocaleString("it-IT")}</strong>
        <span>{total === 1 ? "oggetto" : "oggetti"}{pageQuery.isFetching ? " · consultazione…" : ""}</span>
      </p>
      <button type="button" className="button secondary" disabled={!hasFilters} onClick={reset}>Azzera i filtri</button>
    </div>

    <div className="compendium-filters" data-component-type="toolbar" data-theme="default">
      {reference.typeGroups.map((group, index) => {
        const keys: Array<keyof Filters> = ["category", "subtype", "variant", "grade"];
        const key = keys[index];
        const options = index === 1 ? subtypeOptions : group.options;
        return <label key={group.position}>
          <span><InfoPopover label={group.label} title={group.label} className="codex-link-label"><p>{group.note}</p></InfoPopover></span>
          <select value={String(filters[key])} onChange={(event) => update(key, event.target.value as never)}>
            <option value="">Tutte</option>
            <option value={NONE_SENTINEL}>Non indicato</option>
            {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>;
      })}
      <label>
        <span>Categoria d'arma</span>
        <select value={filters.weaponCategory} onChange={(event) => update("weaponCategory", event.target.value)}>
          <option value="">Tutte</option>
          {reference.weaponCategories.map((entry) => <option key={entry.key} value={entry.key}>{entry.label}</option>)}
        </select>
      </label>
      <label>
        <span>Rarità</span>
        <select value={filters.rarity} onChange={(event) => update("rarity", event.target.value)}>
          <option value="">Tutte</option>
          {reference.rarityChoices.map((choice) => <option key={choice.value} value={String(choice.value)}>{choice.label}</option>)}
        </select>
      </label>
      <label>
        <span>Regione</span>
        <select value={filters.region} onChange={(event) => update("region", event.target.value)}>
          <option value="">Tutte</option>
          <option value={NONE_SENTINEL}>Nessuna regione</option>
          {reference.regions.map((region) => <option key={region} value={region}>{region}</option>)}
        </select>
      </label>
      <label>
        <span>Livello di bottino</span>
        <select value={filters.lootLevel} onChange={(event) => update("lootLevel", event.target.value)}>
          <option value="">Tutti</option>
          {reference.lootLevels.map((level) => <option key={level} value={String(level)}>Livello {level}</option>)}
        </select>
      </label>
      <label className="compendium-range">
        <span>Valore</span>
        <span>
          <input type="number" min="0" value={filters.valueMin} onChange={(event) => update("valueMin", event.target.value)} placeholder="min" aria-label="Valore minimo" />
          <input type="number" min="0" value={filters.valueMax} onChange={(event) => update("valueMax", event.target.value)} placeholder="max" aria-label="Valore massimo" />
        </span>
      </label>
      <label className="compendium-range">
        <span>Peso</span>
        <span>
          <input type="number" min="0" step="0.1" value={filters.weightMin} onChange={(event) => update("weightMin", event.target.value)} placeholder="min" aria-label="Peso minimo" />
          <input type="number" min="0" step="0.1" value={filters.weightMax} onChange={(event) => update("weightMax", event.target.value)} placeholder="max" aria-label="Peso massimo" />
        </span>
      </label>
      <label className="compendium-switch">
        <input type="checkbox" checked={filters.withEffects} onChange={(event) => update("withEffects", event.target.checked)} />
        <span>Solo con effetti automatici</span>
      </label>
    </div>

    {pageQuery.error && <aside className="callout guide-warning"><strong>Consultazione interrotta</strong><p>{(pageQuery.error as Error).message}</p></aside>}

    <div className="compendium-grid">
      {items.map((item) => <ItemCard key={item.id} item={item} reference={reference} onOpen={() => setOpenItem(item)} />)}
    </div>

    {!items.length && !pageQuery.isFetching && <div className="compendium-empty">
      <span aria-hidden="true">◇</span>
      <strong>Nessun oggetto corrisponde alla ricerca</strong>
      <p>Cambia i filtri oppure azzerali per tornare al catalogo completo.</p>
    </div>}

    {total > PAGE_SIZE && <footer className="compendium-pager">
      <button type="button" className="button secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Pagina precedente</button>
      <span>Pagina {Math.floor(offset / PAGE_SIZE) + 1} di {Math.max(1, Math.ceil(total / PAGE_SIZE))}</span>
      <button type="button" className="button secondary small" disabled={!page?.hasMore} onClick={() => setOffset(offset + PAGE_SIZE)}>Pagina successiva →</button>
    </footer>}

    {openItem && <ItemSheet item={openItem} reference={reference} onClose={() => setOpenItem(null)} />}
  </div>;
}
