import { describe, expect, it } from "vitest";

import { potionLevelForPotency, projectedBrew, selectedQuantity } from "./mechanics";

const multipliers = {
  colors: [
    { color: "rosso" as const, value: 0.2 },
    { color: "verde" as const, value: 0 },
    { color: "blu" as const, value: 0.4 },
  ],
  levels: [
    { level: 1, value: 1.2 },
    { level: 2, value: 1.7 },
    { level: 3, value: 2.2 },
    { level: 4, value: 2.7 },
  ],
};

describe("alchemy mechanics", () => {
  it("keeps the elder three-point potion thresholds", () => {
    expect(potionLevelForPotency(2.99)).toBe(0);
    expect(potionLevelForPotency(3)).toBe(1);
    expect(potionLevelForPotency(29.99)).toBe(9);
    expect(potionLevelForPotency(30)).toBe(10);
    expect(potionLevelForPotency(99)).toBe(10);
  });

  it("uses level values and the selected color ability bonus", () => {
    const result = projectedBrew(
      multipliers,
      [{ color: "rosso", level: 1 }, { color: "blu", level: 4 }],
      "rosso",
      1,
    );
    expect(result.levelTotal).toBeCloseTo(3.9);
    expect(result.abilityBonus).toBe(0.2);
    expect(result.potency).toBe(4.68);
    expect(result.potionLevel).toBe(1);
  });

  it("counts selected stock by color and level", () => {
    const ingredients = [
      { color: "verde" as const, level: 2 },
      { color: "verde" as const, level: 2 },
      { color: "rosso" as const, level: 2 },
    ];
    expect(selectedQuantity(ingredients, "verde", 2)).toBe(2);
    expect(selectedQuantity(ingredients, "rosso", 2)).toBe(1);
  });
});
