import { describe, expect, it } from "vitest";

import { colorLuminance, contrastingTextOutline } from "./appearance";

describe("appearance contrast helpers", () => {
  it("chooses black around light primary text and white around dark primary text", () => {
    expect(contrastingTextOutline("#f5efff")).toBe("#000000");
    expect(contrastingTextOutline("#291d15")).toBe("#ffffff");
  });

  it("uses the safe light outline fallback for invalid colors", () => {
    expect(colorLuminance("not-a-color")).toBe(0);
    expect(contrastingTextOutline("not-a-color")).toBe("#ffffff");
  });
});
