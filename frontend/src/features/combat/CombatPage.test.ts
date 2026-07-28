import { describe, expect, it } from "vitest";

import {
  actionMatchesTagFilters,
  actionTagsFor,
  combatEventNeedsRefresh,
  manaForEffect,
  persistentCombatButtonIds,
  spellCastCosts,
  toggledActionTags,
} from "./CombatPage";
import {
  adjustedAttackDamage,
  attackButtonModifierSummary,
  combatButtonTotalsSummary,
  selectedCombatButtonTotals,
} from "./AttackPanel";

const EMPTY = { pf: 0, mana: 0, energia: 0, potere: 0, pa: 0, stanchezza: 0 };

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
    })).toBe(10);
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
