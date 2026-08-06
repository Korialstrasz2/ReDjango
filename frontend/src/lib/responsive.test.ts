import { describe, expect, it } from "vitest";

import {
  PHONE_MAX_WIDTH,
  PHONE_NARROW_MAX_WIDTH,
  TABLET_MAX_WIDTH,
  responsiveCategoryFromWidth,
} from "./responsive";

describe("responsiveCategoryFromWidth", () => {
  it.each([
    [0, "phone-narrow"],
    [PHONE_NARROW_MAX_WIDTH, "phone-narrow"],
    [PHONE_NARROW_MAX_WIDTH + 1, "phone"],
    [PHONE_MAX_WIDTH, "phone"],
    [PHONE_MAX_WIDTH + 1, "tablet"],
    [TABLET_MAX_WIDTH, "tablet"],
    [TABLET_MAX_WIDTH + 1, "desktop"],
  ] as const)("classifies %dpx as %s", (width, expected) => {
    expect(responsiveCategoryFromWidth(width)).toBe(expected);
  });

  it("treats invalid widths as desktop", () => {
    expect(responsiveCategoryFromWidth(Number.NaN)).toBe("desktop");
    expect(responsiveCategoryFromWidth(Number.POSITIVE_INFINITY)).toBe("desktop");
  });
});
