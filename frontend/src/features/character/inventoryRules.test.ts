import { describe, expect, it } from "vitest";

import type { CharacterSlot, Item } from "../../lib/types";
import { canSwap, fits, shouldCloseSlotActions } from "./CharacterPage";

const item = (overrides: Partial<Item>): Item => ({
  id: 1,
  name: "Oggetto",
  icon: "",
  types: [],
  description: "",
  value: 0,
  weight: 0,
  rarity: 0,
  lootLevel: "",
  region: "",
  effects: [],
  imageUrl: "",
  archived: false,
  isProjectile: false,
  compatibleEquipmentSlots: [],
  ...overrides,
} as Item);

const slot = (overrides: Partial<CharacterSlot>): CharacterSlot => ({
  id: "backpack:1",
  group: "backpack",
  slot: "1",
  label: "Zaino 1",
  slotType: "backpack",
  accepts: ["any"],
  isExtraSlot: false,
  isLocked: false,
  isMagical: false,
  quantity: 1,
  stackable: false,
  weightless: false,
  item: null,
  ...overrides,
});

describe("regole visive dell'inventario", () => {
  it("accetta ogni oggetto nello zaino e negli slot extra", () => {
    const ring = item({ types: ["anello"], compatibleEquipmentSlots: ["anello_1", "extra_slot_1"] });
    expect(fits(ring, slot({}))).toBe(true);
    expect(fits(ring, slot({ id: "equipment:extra_slot_1", group: "equipment", slot: "extra_slot_1", isExtraSlot: true }))).toBe(true);
  });

  it("limita la faretra ai proiettili", () => {
    const quiver = slot({ id: "quiver:1", group: "quiver", slot: "1", slotType: "quiver" });
    expect(fits(item({ name: "Freccia", isProjectile: true }), quiver)).toBe(true);
    expect(fits(item({ name: "Pozione" }), quiver)).toBe(false);
  });

  it("mostra valido uno scambio solo quando entrambe le direzioni sono compatibili", () => {
    const ring = item({ name: "Anello", types: ["anello"], compatibleEquipmentSlots: ["anello_1", "extra_slot_1"] });
    const sword = item({ id: 2, name: "Spada", types: ["spadalunga"], compatibleEquipmentSlots: ["arma", "extra_slot_1"] });
    const ringSlot = slot({ id: "equipment:anello_1", group: "equipment", slot: "anello_1", item: ring });
    const weaponSlot = slot({ id: "equipment:arma", group: "equipment", slot: "arma", item: sword });
    const backpack = slot({ item: sword });
    const extra = slot({ id: "equipment:extra_slot_1", group: "equipment", slot: "extra_slot_1", isExtraSlot: true });

    expect(canSwap(ringSlot, weaponSlot)).toBe(false);
    expect(canSwap(backpack, extra)).toBe(true);
  });

  it("non propone spazi bloccati", () => {
    expect(fits(item({}), slot({ isLocked: true }))).toBe(false);
  });

  it("accetta oggetti e reagenti nei contenitori impilabili senza proporre scambi con lo zaino", () => {
    const potion = item({ name: "Pozione" });
    const reagent = item({ id: -11, name: "Reagente Rosso · livello 1", metadata: { storageOnly: true } });
    const utility = slot({ id: "utility:1", group: "utility", stackable: true, weightless: true });

    expect(fits(potion, utility)).toBe(true);
    expect(fits(reagent, utility)).toBe(true);
    expect(fits(reagent, slot({}))).toBe(false);
    expect(canSwap(slot({ item: potion }), utility)).toBe(false);
  });

  it("mantiene selezionato lo slot mentre si apre l'editor dell'oggetto", () => {
    const editButton = document.createElement("button");
    editButton.setAttribute("data-retain-slot-selection", "");
    const buttonLabel = document.createElement("span");
    editButton.append(buttonLabel);

    expect(shouldCloseSlotActions(buttonLabel, "backpack:1")).toBe(false);
    expect(shouldCloseSlotActions(document.body, "backpack:1")).toBe(true);
  });
});
