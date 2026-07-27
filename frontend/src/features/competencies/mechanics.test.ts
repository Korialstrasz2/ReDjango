import { describe, expect, it } from "vitest";

import type { CompetenceEntry, CompetenceRoll } from "../../lib/types";
import { latestDieValue, rollEquation, techniqueEnergyCost, techniqueUnlocked } from "./mechanics";

describe("competence mastery mechanics", () => {
  it("unlocks the two techniques at ranks one and three", () => {
    expect(techniqueUnlocked(0, "focus")).toBe(false);
    expect(techniqueUnlocked(1, "focus")).toBe(true);
    expect(techniqueUnlocked(2, "amplify")).toBe(false);
    expect(techniqueUnlocked(3, "amplify")).toBe(true);
  });

  it("applies the rank-five energy discount", () => {
    expect(techniqueEnergyCost(4, "focus")).toBe(3);
    expect(techniqueEnergyCost(5, "focus")).toBe(2);
    expect(techniqueEnergyCost(4, "amplify")).toBe(6);
    expect(techniqueEnergyCost(5, "amplify")).toBe(5);
  });

  it("shows the exact selected roll equation", () => {
    const entry = { dieSides: 10, rollModifier: -2 } as CompetenceEntry;
    expect(rollEquation(entry, "standard")).toBe("(d10 − 2)");
    expect(rollEquation(entry, "focus")).toBe("(d10 − 2 + 1)");
    expect(rollEquation(entry, "amplify")).toBe("(d10 − 2 + 2)");
  });

  it("reads the latest value after a reroll", () => {
    const roll = { rolls: [{ value: 2 }, { value: 9 }] } as unknown as CompetenceRoll;
    expect(latestDieValue(roll)).toBe(9);
  });
});
