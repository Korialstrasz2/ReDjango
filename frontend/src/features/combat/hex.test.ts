import { describe, expect, it } from "vitest";

import { cellKey, gridToPixel, pixelToGrid, polygonPoints } from "./hex";

describe("combat hex geometry", () => {
  it.each(["pointy", "flat"] as const)("round-trips axial coordinates for %s orientation", (orientation) => {
    for (const cell of [{ q: 0, r: 0 }, { q: 3, r: 4 }, { q: 7, r: 2 }]) {
      const point = gridToPixel(cell, 34, orientation, 41, 23);
      expect(pixelToGrid(point.x, point.y, 34, orientation, 41, 23)).toEqual(cell);
    }
  });

  it("alternates pointy rows instead of drifting diagonally", () => {
    const row0 = gridToPixel({ q: 0, r: 0 }, 30, "pointy");
    const row1 = gridToPixel({ q: 0, r: 1 }, 30, "pointy");
    const row2 = gridToPixel({ q: 0, r: 2 }, 30, "pointy");
    expect(row1.x).toBeCloseTo(Math.sqrt(3) * 15);
    expect(row2.x).toBeCloseTo(row0.x);
  });

  it("produces stable keys and six polygon vertices", () => {
    expect(cellKey({ q: 3, r: -2 })).toBe("3:-2");
    expect(polygonPoints({ x: 50, y: 50 }, 20, "pointy").split(" ")).toHaveLength(6);
  });
});
