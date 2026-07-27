import { describe, expect, it } from "vitest";

import type { DamageRules } from "../../lib/types";
import { cloneDamageRules, damageCellBand } from "./DamageRulesPage";


describe("damage rule tool helpers", () => {
  it("classifies multiplier cells for the complete grid legend", () => {
    expect(damageCellBand(0)).toBe("zero");
    expect(damageCellBand(20)).toBe("low");
    expect(damageCellBand(80)).toBe("reduced");
    expect(damageCellBand(100)).toBe("full");
    expect(damageCellBand(140)).toBe("high");
    expect(damageCellBand(180)).toBe("extreme");
  });

  it("clones nested rule rows before editing", () => {
    const source = {
      version: 1,
      bounds: {
        attackDifferenceMinimum: -25,
        attackDifferenceMaximum: 45,
        d20Minimum: 1,
        d20Maximum: 20,
        resistanceLevelMinimum: -4,
        resistanceLevelMaximum: 9,
        tierMinimum: -5,
        tierMaximum: 30,
      },
      resistancePercentages: { "0": 0 },
      tierDamageFormulas: { "0": "1d8" },
      damageMultipliers: { "1": [0, 20] },
    } satisfies DamageRules;

    const clone = cloneDamageRules(source);
    clone.damageMultipliers["1"][0] = 100;

    expect(source.damageMultipliers["1"][0]).toBe(0);
  });
});
