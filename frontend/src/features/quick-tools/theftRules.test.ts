import { describe, expect, it } from "vitest";

import { applyToggle, calculateCheck } from "./theftRules";

describe("scasso", () => {
  it("keeps the elder lock thresholds untouched when nothing is selected", () => {
    expect(calculateCheck("scasso", "elementare", [], 0, 0, "nessuno").threshold).toBe(8);
    expect(calculateCheck("scasso", "eccellente", [], 0, 0, "nessuno").threshold).toBe(16);
  });

  it("applies the maintenance bonus and malus to the threshold", () => {
    expect(calculateCheck("scasso", "buona", ["curata"], 0, 0, "nessuno").threshold).toBe(16);
    expect(calculateCheck("scasso", "buona", ["trascurata"], 0, 0, "nessuno").threshold).toBe(12);
  });

  it("cancels only the malus on dwarven metal, never the bonus", () => {
    const neglected = calculateCheck("scasso", "buona", ["trascurata", "nanico"], 0, 0, "nessuno");
    expect(neglected.threshold).toBe(14);
    expect(neglected.contributions[0]).toMatchObject({ value: 0, note: "annullato dal metallo nanico" });
    expect(calculateCheck("scasso", "buona", ["curata", "nanico"], 0, 0, "nessuno").threshold).toBe(16);
  });

  it("reports the set bonus separately from the threshold", () => {
    const check = calculateCheck("scasso", "eccellente", [], 0, 0, "maestro");
    expect(check.threshold).toBe(16);
    expect(check.rollBonus).toBe(8);
    expect(calculateCheck("scasso", "comune", [], 0, 0, "improvvisato").rollBonus).toBe(-3);
  });

  it("sums the manual modifier into the final modifier", () => {
    const check = calculateCheck("scasso", "comune", ["curata"], 0, -3, "nessuno");
    expect(check.modifier).toBe(-1);
    expect(check.threshold).toBe(11);
  });
});

describe("borseggio", () => {
  it("uses the apple as the reference target", () => {
    expect(calculateCheck("borseggio", "mela", [], 0, 0, "nessuno").threshold).toBe(2);
    expect(calculateCheck("borseggio", "arma2", [], 0, 0, "nessuno").threshold).toBe(6);
  });

  it("stacks company, coin purse and sleep modifiers", () => {
    const check = calculateCheck("borseggio", "arma1", ["neutrali", "borsello"], 0, 0, "nessuno");
    expect(check.modifier).toBe(6);
    expect(check.threshold).toBe(10);
    expect(calculateCheck("borseggio", "mela", ["dorme"], 0, 0, "nessuno").threshold).toBe(1);
  });

  it("subtracts the diversion and clamps it to the elder 1–4 range", () => {
    expect(calculateCheck("borseggio", "arma2", [], 4, 0, "nessuno").threshold).toBe(2);
    expect(calculateCheck("borseggio", "arma2", [], 9, 0, "nessuno").threshold).toBe(2);
  });

  it("never lets the threshold fall below 1", () => {
    expect(calculateCheck("borseggio", "mela", ["dorme"], 4, -10, "nessuno").threshold).toBe(1);
  });

  it("ignores the lockpick set, which only helps against locks", () => {
    expect(calculateCheck("borseggio", "mela", [], 0, 0, "maestro").rollBonus).toBe(0);
  });
});

describe("applyToggle", () => {
  it("keeps the company options mutually exclusive", () => {
    const first = applyToggle("borseggio", [], "amichevoli");
    expect(first).toEqual(["amichevoli"]);
    expect(applyToggle("borseggio", first, "diffidenti")).toEqual(["diffidenti"]);
  });

  it("leaves independent options alone", () => {
    const active = applyToggle("borseggio", ["neutrali"], "borsello");
    expect(active).toContain("neutrali");
    expect(active).toContain("borsello");
  });

  it("toggles an active option back off", () => {
    expect(applyToggle("scasso", ["curata"], "curata")).toEqual([]);
  });
});
