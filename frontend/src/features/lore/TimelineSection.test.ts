import { describe, expect, it } from "vitest";

import { formatTimelineYear } from "./TimelineSection";

describe("Timeline year labels", () => {
  it("anchors year zero to Dagoth Ur", () => {
    expect(formatTimelineYear(0)).toBe("Anno di Dagoth");
  });

  it("formats years on both sides of the anchor", () => {
    expect(formatTimelineYear(-10)).toBe("10 anni prima di Dagoth");
    expect(formatTimelineYear(23)).toBe("23 anni dopo Dagoth");
  });

  it("uses the singular around the anchor", () => {
    expect(formatTimelineYear(-1)).toBe("1 anno prima di Dagoth");
    expect(formatTimelineYear(1)).toBe("1 anno dopo Dagoth");
  });
});
