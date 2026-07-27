import type { CSSProperties } from "react";
import { useDraggable, useDroppable } from "@dnd-kit/core";

import type { CharacterSlot as Slot, Item } from "../../lib/types";

type Props = {
  slot: Slot;
  variant?: "card" | "figure";
  selected: boolean;
  moveSource: boolean;
  compatibility: "valid" | "invalid" | "neutral";
  equipItem: Item | null;
  actionsVisible: boolean;
  actionPending: boolean;
  onSelect: (slot: Slot) => void;
  onMoveStart: (slot: Slot) => void;
  onEquip: (slot: Slot) => void;
  onEmpty: (slot: Slot) => void;
  onQuantityChange?: (slot: Slot, delta: -1 | 1) => void;
  onActionsEnter: () => void;
  onActionsLeave: () => void;
};

export function CharacterSlot({
  slot,
  variant = "card",
  selected,
  moveSource,
  compatibility,
  equipItem,
  actionsVisible,
  actionPending,
  onSelect,
  onMoveStart,
  onEquip,
  onEmpty,
  onQuantityChange,
  onActionsEnter,
  onActionsLeave,
}: Props) {
  const draggable = useDraggable({ id: `drag:${slot.id}`, data: { slot }, disabled: !slot.item || slot.isLocked });
  const droppable = useDroppable({ id: `drop:${slot.id}`, data: { slot }, disabled: slot.isLocked });
  const style: CSSProperties = draggable.transform ? { transform: `translate3d(${draggable.transform.x}px, ${draggable.transform.y}px, 0)` } : {};
  return <article
    ref={(node) => { draggable.setNodeRef(node); droppable.setNodeRef(node); }}
    className={`character-slot ${variant === "figure" ? "figure-slot" : ""} ${selected ? "selected" : ""} ${moveSource ? "move-source" : ""} ${compatibility} ${slot.isLocked ? "locked" : ""} ${droppable.isOver ? "over" : ""} ${draggable.isDragging ? "dragging" : ""}`}
    data-slot-id={slot.id}
    data-figure-slot={variant === "figure" ? slot.slot : undefined}
    data-component-type="card"
    data-theme={slot.isExtraSlot ? "arcane" : "default"}
    data-magical={slot.isMagical ? "true" : undefined}
    style={style}
    onClick={() => !slot.isLocked && onSelect(slot)}
    onPointerEnter={() => selected && onActionsEnter()}
    onPointerLeave={() => selected && onActionsLeave()}
    {...draggable.listeners}
    {...draggable.attributes}
    role="button"
    tabIndex={slot.isLocked ? -1 : 0}
    aria-disabled={slot.isLocked}
    aria-label={`${slot.label}: ${slot.isLocked ? `bloccato${slot.item ? `, contiene ${slot.item.name}` : ""}` : slot.item?.name || "vuoto"}`}
    onKeyDown={(event) => {
      if (!slot.isLocked && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        onSelect(slot);
      }
    }}
  >
    <header><span>{slot.label}</span>{variant !== "figure" && slot.isExtraSlot && <em>qualsiasi</em>}{variant !== "figure" && slot.isMagical && <em>magico</em>}</header>
    {slot.isLocked
      ? slot.item
        ? <div className="slot-item locked-slot-item"><strong>{slot.item.name}</strong><small>Spazio bloccato</small></div>
        : <div className="slot-empty">Bloccato</div>
      : slot.item
        ? <div className="slot-item"><strong>{slot.item.name}{slot.stackable && slot.quantity > 1 ? ` × ${slot.quantity}` : ""}</strong>{variant !== "figure" && <><small>{slot.item.types.join(" · ")}</small><span>{slot.weightless ? "peso non conteggiato" : `${slot.item.weight ?? 0} peso`}</span></>}</div>
        : <div className="slot-empty">Vuoto</div>}
    {actionsVisible && !slot.isLocked && <div className="slot-inline-actions" data-component-type="toolbar" data-theme="dark" onPointerDown={(event) => event.stopPropagation()}>
      <button
        type="button"
        disabled={actionPending || !equipItem}
        title={equipItem ? `Inserisci ${equipItem.name} in ${slot.label}` : "Seleziona prima un oggetto dalla ricerca"}
        aria-label={equipItem ? `Equipaggia ${equipItem.name} in ${slot.label}` : `Equipaggia un oggetto in ${slot.label}`}
        onClick={(event) => { event.stopPropagation(); onEquip(slot); }}
      >Equip</button>
      <button
        type="button"
        disabled={actionPending || !slot.item}
        aria-label={`Svuota ${slot.label}`}
        onClick={(event) => { event.stopPropagation(); onEmpty(slot); }}
      >Svuota</button>
      {slot.stackable && slot.item && onQuantityChange && <>
        <button
          type="button"
          disabled={actionPending}
          aria-label={`Riduci la quantità di ${slot.item.name}`}
          onClick={(event) => { event.stopPropagation(); onQuantityChange(slot, -1); }}
        >−</button>
        <button
          type="button"
          disabled={actionPending || slot.quantity >= 9999}
          aria-label={`Aumenta la quantità di ${slot.item.name}`}
          onClick={(event) => { event.stopPropagation(); onQuantityChange(slot, 1); }}
        >+</button>
      </>}
    </div>}
    {variant !== "figure" && slot.item && !slot.isLocked && <button className="slot-move-button" type="button" onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.stopPropagation(); onMoveStart(slot); }}>{moveSource ? "Annulla" : "Sposta"}</button>}
  </article>;
}
