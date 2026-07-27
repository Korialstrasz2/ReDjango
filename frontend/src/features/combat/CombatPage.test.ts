import { describe, expect, it } from "vitest";

import {
  combatEventNeedsRefresh,
  manaForEffect,
  persistentCombatButtonIds,
} from "./CombatPage";
import {
  adjustedAttackDamage,
  attackButtonModifierSummary,
  combatButtonTotalsSummary,
  selectedCombatButtonTotals,
} from "./AttackPanel";

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
