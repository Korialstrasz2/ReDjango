import type { CharacterSlot as Slot, Item } from "../../lib/types";

/** Slot actions stay reachable long enough to walk to the search column and back. */
export const SLOT_ACTIONS_HIDE_DELAY = 12000;

export function fits(item: Item | null | undefined, target: Slot): boolean {
  if (!item) return true;
  if (target.systemManaged) return false;
  if (target.isLocked) return false;
  const storageOnly = Boolean((item.metadata as Record<string, unknown> | undefined)?.storageOnly);
  if (target.group === "utility" || target.group === "campaign") return true;
  if (storageOnly) return false;
  if (target.group === "backpack") return true;
  if (target.group === "quiver") return Boolean(item.isProjectile);
  return Boolean(item.compatibleEquipmentSlots?.includes(target.slot));
}

export function canSwap(source: Slot, target: Slot): boolean {
  const sourceExtended = source.group === "utility" || source.group === "campaign";
  const targetExtended = target.group === "utility" || target.group === "campaign";
  if (sourceExtended !== targetExtended) return false;
  return source.id !== target.id && fits(source.item, target) && fits(target.item, source);
}

export function shouldCloseSlotActions(target: EventTarget | null, selectedSlotId: string): boolean {
  const element = target instanceof Element ? target : null;
  if (element?.closest("[data-retain-slot-selection]")) return false;
  return element?.closest<HTMLElement>("[data-slot-id]")?.dataset.slotId !== selectedSlotId;
}

/**
 * Named equipment slots an item may occupy. Extra slots accept anything, so they are
 * deliberately left out: they are scarce and choosing one is always the player's call.
 */
export function equipmentCandidates(item: Item, slots: Slot[]): Slot[] {
  return slots.filter((slot) => slot.group === "equipment" && !slot.isExtraSlot && fits(item, slot));
}

export type EquipResolution =
  | { kind: "assign"; slot: Slot }
  | { kind: "choose"; candidates: Slot[] }
  | { kind: "none" };

/**
 * Where "Equipaggia" should put an item. A free slot wins; when every compatible slot is
 * taken the player is asked which one to replace, unless there is only one to begin with.
 */
export function resolveEquipTarget(item: Item, slots: Slot[]): EquipResolution {
  const candidates = equipmentCandidates(item, slots);
  if (candidates.length === 0) return { kind: "none" };
  const free = candidates.find((slot) => !slot.item);
  if (free) return { kind: "assign", slot: free };
  if (candidates.length === 1) return { kind: "assign", slot: candidates[0] };
  return { kind: "choose", candidates };
}

export function firstFreeSlot(item: Item, slots: Slot[]): Slot | null {
  return slots.find((slot) => !slot.item && fits(item, slot)) || null;
}
