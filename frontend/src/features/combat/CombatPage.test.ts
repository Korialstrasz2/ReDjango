import { describe, expect, it } from "vitest";

import {
  actionMatchesTagFilters,
  actionTagsFor,
  combatEventNeedsRefresh,
  healthBand,
  manaForEffect,
  publicEquipmentValue,
  persistentCombatButtonIds,
  spellCastCosts,
  spellManaBreakdown,
  toggledActionTags,
} from "./CombatPage";
import {
  adjustedAttackDamage,
  attackButtonModifierSummary,
  combatButtonTotalsSummary,
  selectedCombatButtonTotals,
} from "./AttackPanel";

const EMPTY = { pf: 0, mana: 0, energia: 0, potere: 0, pa: 0, stanchezza: 0 };
const MIXED_SPELL = {
  baseMana: 15,
  effectPerMana: 1 / 3,
  minimumMana: 0,
  effectUnit: "turni",
  formula: "Turni = max(0, (Mana - 15) × 0.333)",
  costSummary: "15 Mana fissi più 3 Mana per turni",
  fixedCosts: { ...EMPTY, energia: 2, pa: 1 },
};

describe("combat quick-action effect conversion", () => {
  it("uses one Mana for each effect point on ordinary actions", () => {
    expect(manaForEffect(37)).toBe(37);
  });

  it("uses the selected spell definition and rounds required Mana up", () => {
    expect(manaForEffect(9, {
      baseMana: 5,
      effectPerMana: 2,
      minimumMana: 8,
      effectUnit: "danni",
      formula: "Danni = max(0, (Mana - 5) × 2)",
      costSummary: "",
      fixedCosts: { ...EMPTY },
    })).toBe(10);
  });

  it("keeps the fixed Mana separate from the Mana bought with the effect", () => {
    expect(spellManaBreakdown(4, MIXED_SPELL)).toEqual({
      fixedMana: 15,
      variableMana: 12, // 4 turni × 3 Mana
      requiredMana: 27,
    });
  });

  it("charges only the fixed Mana when the effect is zero", () => {
    expect(spellManaBreakdown(0, MIXED_SPELL)).toMatchObject({ fixedMana: 15, requiredMana: 15 });
  });

  it("adds Mana declared by hand on the action to the fixed part", () => {
    expect(spellManaBreakdown(0, MIXED_SPELL, 5)).toMatchObject({ fixedMana: 20, requiredMana: 20 });
  });
});

describe("quick-action tags", () => {
  it("treats an action without stored labels as “no tag”", () => {
    expect(actionTagsFor(undefined, "skill:1:a")).toEqual(["no tag"]);
    expect(actionTagsFor({ "skill:1:a": [] }, "skill:1:a")).toEqual(["no tag"]);
  });

  it("drops “no tag” as soon as a real label is added and restores it when the last one goes", () => {
    expect(toggledActionTags(["no tag"], "melee")).toEqual(["melee"]);
    expect(toggledActionTags(["melee"], "combat")).toEqual(["combat", "melee"]);
    expect(toggledActionTags(["melee"], "melee")).toEqual([]);
    expect(actionTagsFor({ "skill:1:a": toggledActionTags(["melee"], "melee") }, "skill:1:a")).toEqual(["no tag"]);
  });

  it("keeps an action visible when at least one of its labels is filtered in", () => {
    expect(actionMatchesTagFilters(["combat", "melee"], ["preferito", "combat", "no tag"])).toBe(true);
    expect(actionMatchesTagFilters(["utility"], ["preferito", "combat", "no tag"])).toBe(false);
    expect(actionMatchesTagFilters(["no tag"], ["preferito", "combat", "no tag"])).toBe(true);
  });
});

describe("spell costs of the original rules", () => {
  const economy = { manaDiscountPerPower: 2, actionPointDiscountPerPower: 1, manaPerEnergy: 4, manaPerActionPoint: 5 };

  it("charges Mana, Energia and PA together and converts them from the undiscounted Mana", () => {
    expect(spellCastCosts({ ...EMPTY, mana: 0 }, 20, 0, 0, economy)).toMatchObject({ mana: 20, energia: 5, pa: 4, potere: 0 });
  });

  it("lets Potere discount Mana and PA while only the spent Potere leaves the pool", () => {
    expect(spellCastCosts({ ...EMPTY, mana: 0 }, 20, 3, 2, economy)).toMatchObject({
      mana: 10, // 20 − (3 + 2) × 2
      energia: 5, // 20 / 4, senza sconto
      pa: 0, // ceil(20 / 5) − 5 × 1, mai sotto zero
      potere: 3, // il Potere gratis non viene speso
    });
  });

  it("skips a conversion the character cannot perform", () => {
    expect(spellCastCosts({ ...EMPTY }, 12, 0, 0, { ...economy, manaPerEnergy: 0, manaPerActionPoint: 0 }))
      .toMatchObject({ mana: 12, energia: 0, pa: 0 });
  });

  it("adds the fixed costs of the spell on top of the converted ones", () => {
    expect(spellCastCosts({ ...EMPTY, pf: 3, energia: 2, pa: 1, stanchezza: 4 }, 20, 0, 0, economy)).toEqual({
      pf: 3, // solo fisso, nessuna conversione
      mana: 20,
      energia: 7, // 20 / 4 convertiti più 2 fissi
      potere: 0,
      pa: 5, // ceil(20 / 5) più 1 fisso
      stanchezza: 4,
    });
  });

  it("never converts the fixed costs a second time when Potere discounts the cast", () => {
    expect(spellCastCosts({ ...EMPTY, energia: 2, pa: 1 }, 20, 3, 2, economy)).toMatchObject({
      mana: 10,
      energia: 7,
      pa: 1, // la conversione si azzera con lo sconto, il costo fisso resta
      potere: 3,
    });
  });
});

describe("character combat-button reset", () => {
  it("keeps only buttons configured to remain active after an applied attack", () => {
    expect(persistentCombatButtonIds([
      { id: 1, keepActiveInCombat: false },
      { id: 2, keepActiveInCombat: true },
      { id: 3, keepActiveInCombat: true },
    ], [1, 2])).toEqual([2]);
  });
});

describe("combat event refresh deduplication", () => {
  it("does not refetch a workspace that already contains the SSE event", () => {
    expect(combatEventNeedsRefresh(42, [{ id: 41 }, { id: 42 }])).toBe(false);
    expect(combatEventNeedsRefresh(43, [{ id: 41 }, { id: 42 }])).toBe(true);
  });
});

describe("compact attack helpers", () => {
  it("stacks repeated percentage modifiers against the same base damage", () => {
    expect(adjustedAttackDamage(10, 66)).toBe(16);
    expect(adjustedAttackDamage(10, 0)).toBe(10);
    expect(adjustedAttackDamage(10, -100)).toBe(0);
  });

  it("summarizes every numerical bonus and malus on a combat button", () => {
    expect(attackButtonModifierSummary({
      modifiers: {
        attackBonus: 2,
        damageBonus: -1,
        damageTierBonus: 1,
        penetrationFlat: 0,
        penetrationPercent: 25,
      },
    })).toBe("ATK +2 · Danno -1 · Tier +1 · Perforazione % +25");
  });

  it("shows the accumulated effect of every selected combat button", () => {
    const buttons = [
      { id: 1, modifiers: { attackBonus: 2, damageBonus: -1, damageTierBonus: 0, penetrationFlat: 0, penetrationPercent: 10 } },
      { id: 2, modifiers: { attackBonus: 1, damageBonus: 3, damageTierBonus: 1, penetrationFlat: 2, penetrationPercent: 0 } },
    ];
    const totals = selectedCombatButtonTotals(buttons, [1, 2]);
    expect(totals).toEqual({ attackBonus: 3, damageBonus: 2, damageTierBonus: 1, penetrationFlat: 2, penetrationPercent: 10 });
    expect(combatButtonTotalsSummary(totals)).toBe("ATK +3 · Danno +2 · Tier +1 · Perforazione +2 · Perforazione % +10");
  });
});

describe("visibilità dei combattenti per i giocatori", () => {
  it("arrotonda i PF al limite superiore della fascia", () => {
    expect(healthBand(0)).toMatchObject({ key: "empty", width: 0 });
    expect(healthBand(-30)).toMatchObject({ key: "empty", width: 0 });
    expect(healthBand(1)).toMatchObject({ key: "very-low", width: 15 });
    expect(healthBand(14.9)).toMatchObject({ key: "very-low", width: 15 });
    expect(healthBand(15)).toMatchObject({ key: "low", width: 40 });
    expect(healthBand(39.9)).toMatchObject({ key: "low", width: 40 });
    expect(healthBand(40)).toMatchObject({ key: "ok", width: 70 });
    expect(healthBand(69.9)).toMatchObject({ key: "ok", width: 70 });
    expect(healthBand(70)).toMatchObject({ key: "high", width: 95 });
    expect(healthBand(94.9)).toMatchObject({ key: "high", width: 95 });
    expect(healthBand(95)).toMatchObject({ key: "full", width: 100 });
    expect(healthBand(140)).toMatchObject({ key: "full", width: 100 });
  });

  it("mostra solo armi, scudo e protezioni finché il personaggio ha PF", () => {
    const weapon = { slot: "arma", item: { name: "Lama corta" } };
    const shield = { slot: "scudo", item: null };
    const ring = { slot: "anello_1", item: { name: "Anello del silenzio" } };
    expect(publicEquipmentValue(weapon, false)).toBe("Lama corta");
    expect(publicEquipmentValue(shield, false)).toBe("VUOTO");
    expect(publicEquipmentValue(ring, false)).toBe("Vedi a 0 PF");
    expect(publicEquipmentValue(ring, true)).toBe("Anello del silenzio");
    expect(publicEquipmentValue({ slot: "mantello", item: null }, true)).toBe("VUOTO");
  });
});
