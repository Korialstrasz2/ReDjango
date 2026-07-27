import { describe, expect, it } from "vitest";

import { costsLabel } from "./types";

describe("skill reminder costs", () => {
  it("keeps reminder costs readable without pretending to execute them", () => {
    expect(costsLabel({ energia: 4, pa: 1 })).toBe("4 Energia · 1 PA");
    expect(costsLabel({})).toBe("Nessun costo");
  });
});
