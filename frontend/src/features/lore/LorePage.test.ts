import { describe, expect, it } from "vitest";

import { describeCoefficient, reputationOffset } from "./LorePage";

describe("reputation track placement", () => {
  it("puts a neutral score in the middle", () => {
    expect(reputationOffset(0, -100, 100)).toBe(50);
  });

  it("puts the extremes at both ends", () => {
    expect(reputationOffset(-100, -100, 100)).toBe(0);
    expect(reputationOffset(100, -100, 100)).toBe(100);
  });

  it("clamps scores outside the configured range", () => {
    expect(reputationOffset(-500, -100, 100)).toBe(0);
    expect(reputationOffset(500, -100, 100)).toBe(100);
  });

  it("stays centred when the range is degenerate", () => {
    expect(reputationOffset(10, 50, 50)).toBe(50);
  });
});

describe("reaction coefficient wording", () => {
  it("names an absent reaction", () => {
    expect(describeCoefficient(0)).toBe("Nessuna reazione");
  });

  it("explains a fractional coefficient as points per step", () => {
    expect(describeCoefficient(0.2)).toBe("guadagna 1 punto ogni 5");
    expect(describeCoefficient(-0.5)).toBe("perde 1 punto ogni 2");
  });

  it("explains a coefficient of one or more directly", () => {
    expect(describeCoefficient(2)).toBe("guadagna 2 punti per ogni punto");
  });

  it("keeps the singular for a one-to-one reaction", () => {
    expect(describeCoefficient(-1)).toBe("perde 1 punto per ogni punto");
  });
});
