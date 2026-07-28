import { useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";

import { getData } from "../../lib/api";
import type { CharacterSlot as Slot, Item, ItemCatalog } from "../../lib/types";
import { fits } from "./inventoryRules";

type FilterKey = "type1" | "type2" | "type3" | "rarity" | "weaponType";
type Filters = Record<FilterKey, string>;
type FilterDefinition = { key: FilterKey; label: string; options: Array<{ value: string; label: string }> };

const EMPTY_FILTERS: Filters = { type1: "", type2: "", type3: "", rarity: "", weaponType: "" };
const RESULT_LIMIT = 60;
const MENU_MARGIN = 8;

type Props = {
  slot: Slot;
  anchor: { x: number; y: number };
  catalog: ItemCatalog;
  storageCatalog: Item[];
  pending: boolean;
  onPick: (item: Item) => void;
  onEmpty: () => void;
  onClose: () => void;
};

/**
 * Contextual item picker anchored to one slot. It opens already scoped to what the slot
 * accepts, so the common case is "right click, read, click" without typing anything.
 */
export function SlotItemPicker({ slot, anchor, catalog, storageCatalog, pending, onPick, onEmpty, onClose }: Props) {
  const menuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [openFilter, setOpenFilter] = useState<FilterKey | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [position, setPosition] = useState({ left: anchor.x, top: anchor.y });
  const query = useDeferredValue(text.trim());

  const definitions = useMemo<FilterDefinition[]>(() => {
    const typeOptions = (position: number) => catalog.typeOptions
      .filter((option) => option.position === position)
      .map((option) => ({ value: option.value, label: option.label || option.value }));
    const available: FilterDefinition[] = [
      { key: "type1", label: "Tipo 1", options: typeOptions(1) },
      { key: "type2", label: "Tipo 2", options: typeOptions(2) },
      { key: "type3", label: "Tipo 3", options: typeOptions(3) },
      { key: "rarity", label: "Rarità", options: catalog.rarityChoices.map((choice) => ({ value: String(choice.value), label: choice.label })) },
      { key: "weaponType", label: "Tipo arma", options: catalog.weaponTypes.map((weapon) => ({ value: String(weapon.id), label: weapon.name })) },
    ];
    return available.filter((definition) => definition.options.length > 0);
  }, [catalog]);

  const searchParams = useMemo(() => {
    const params = new URLSearchParams({ limit: String(RESULT_LIMIT), group: slot.group, slot: slot.slot });
    if (query) params.set("query", query);
    if (filters.type1) params.set("type_1", filters.type1);
    if (filters.type2) params.set("type_2", filters.type2);
    if (filters.type3) params.set("type_3", filters.type3);
    if (filters.rarity) params.set("rarity", filters.rarity);
    if (filters.weaponType) params.set("weapon_type_id", filters.weaponType);
    return params.toString();
  }, [filters, query, slot.group, slot.slot]);

  const catalogQuery = useQuery({
    queryKey: ["slot-item-picker", searchParams],
    queryFn: () => getData<ItemCatalog>(`/api/v1/items?${searchParams}`),
    placeholderData: (previous) => previous,
  });

  // Stock entries are synthesized per character and never reach the catalogue endpoint.
  const results = useMemo(() => {
    const lowered = query.toLocaleLowerCase("it");
    const stock = storageCatalog.filter((item) => fits(item, slot)
      && (!lowered || [item.name, item.description, ...item.types].some((value) => value.toLocaleLowerCase("it").includes(lowered))));
    return [...(catalogQuery.data?.items || []), ...stock].filter((item) => !item.systemManaged).slice(0, RESULT_LIMIT);
  }, [catalogQuery.data?.items, query, slot, storageCatalog]);

  useEffect(() => setActiveIndex(0), [searchParams]);
  useEffect(() => searchRef.current?.focus(), []);

  useLayoutEffect(() => {
    const node = menuRef.current;
    if (!node) return;
    const { width, height } = node.getBoundingClientRect();
    setPosition({
      left: Math.max(MENU_MARGIN, Math.min(anchor.x, window.innerWidth - width - MENU_MARGIN)),
      top: Math.max(MENU_MARGIN, Math.min(anchor.y, window.innerHeight - height - MENU_MARGIN)),
    });
  }, [anchor.x, anchor.y, results.length, openFilter]);

  useEffect(() => {
    const closeWhenClickingOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) onClose();
    };
    document.addEventListener("pointerdown", closeWhenClickingOutside, true);
    return () => document.removeEventListener("pointerdown", closeWhenClickingOutside, true);
  }, [onClose]);

  const activeFilters = definitions.filter((definition) => filters[definition.key]);
  const setFilter = (key: FilterKey, value: string) => {
    setFilters((current) => ({ ...current, [key]: current[key] === value ? "" : value }));
    setOpenFilter(null);
  };
  // Filters are driven with the keyboard caret still inside the search field, so a click on
  // a chip must never move focus away from it.
  const keepSearchFocus = (event: { preventDefault: () => void }) => event.preventDefault();

  const emptyMessage = catalogQuery.isPending
    ? "Ricerca in corso…"
    : `Nessun oggetto compatibile con ${slot.label}.`;

  return createPortal(<div
    ref={menuRef}
    className="slot-item-picker"
    data-component-type="context-menu"
    data-theme="dark"
    data-retain-slot-selection=""
    role="dialog"
    aria-label={`Scegli un oggetto per ${slot.label}`}
    style={{ left: position.left, top: position.top }}
    onKeyDown={(event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        if (openFilter) { setOpenFilter(null); return; }
        onClose();
        return;
      }
      if (results.length === 0) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((current) => (current + 1) % results.length);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((current) => (current - 1 + results.length) % results.length);
      } else if (event.key === "Enter") {
        event.preventDefault();
        onPick(results[activeIndex] || results[0]);
      }
    }}
  >
    <header className="slot-item-picker-header">
      <strong>{slot.label}</strong>
      {slot.item && <button type="button" className="slot-item-picker-empty" disabled={pending} onClick={onEmpty}>Svuota</button>}
      <button type="button" className="icon-button" aria-label="Chiudi il menu" onClick={onClose}>×</button>
    </header>

    <input
      ref={searchRef}
      className="slot-item-picker-search"
      type="text"
      autoComplete="off"
      placeholder="Cerca un oggetto…"
      aria-label={`Cerca un oggetto per ${slot.label}`}
      value={text}
      onChange={(event) => setText(event.target.value)}
    />

    <div className="slot-item-picker-filters" role="group" aria-label="Filtri del catalogo">
      {definitions.map((definition) => {
        const selected = definition.options.find((option) => option.value === filters[definition.key]);
        return <div className="slot-item-picker-filter" key={definition.key}>
          <button
            type="button"
            className={selected ? "active" : ""}
            aria-expanded={openFilter === definition.key}
            title={`Filtra per ${definition.label}`}
            onMouseDown={keepSearchFocus}
            onClick={() => setOpenFilter((current) => current === definition.key ? null : definition.key)}
          >{selected ? selected.label : definition.label}<span aria-hidden="true">{selected ? "×" : "▾"}</span></button>
          {openFilter === definition.key && <div className="slot-item-picker-options" role="listbox" aria-label={definition.label}>
            {definition.options.map((option) => <button
              type="button"
              key={option.value}
              role="option"
              aria-selected={filters[definition.key] === option.value}
              className={filters[definition.key] === option.value ? "active" : ""}
              onMouseDown={keepSearchFocus}
              onClick={() => setFilter(definition.key, option.value)}
            >{option.label}</button>)}
          </div>}
        </div>;
      })}
      {activeFilters.length > 0 && <button
        type="button"
        className="slot-item-picker-reset"
        onMouseDown={keepSearchFocus}
        onClick={() => { setFilters(EMPTY_FILTERS); setOpenFilter(null); }}
      >Azzera filtri</button>}
    </div>

    <div className="slot-item-picker-results" role="listbox" aria-label="Oggetti compatibili">
      {results.length > 0
        ? results.map((item, index) => <button
            type="button"
            key={`${item.id}-${item.name}`}
            role="option"
            aria-selected={activeIndex === index}
            className={activeIndex === index ? "keyboard-active" : ""}
            disabled={pending}
            onMouseEnter={() => setActiveIndex(index)}
            onClick={() => onPick(item)}
          >
            {item.imageUrl ? <img src={item.imageUrl} alt="" loading="lazy" /> : <span className="slot-item-picker-glyph" aria-hidden="true">◆</span>}
            <span className="slot-item-picker-name">{item.name}</span>
            <span className="slot-item-picker-meta">{item.types.join(" · ") || "Oggetto"} · peso {item.weight ?? 0}</span>
          </button>)
        : <p className="slot-item-picker-vuoto">{emptyMessage}</p>}
    </div>
  </div>, document.body);
}
