import { describe, expect, it } from "vitest";

import { resolveSelectedShopId } from "./MarketPage";

describe("market shop selection", () => {
  const shops = [{ id: 11 }, { id: 22 }, { id: 33 }];

  it("keeps the clicked shop while its query is loading", () => {
    expect(resolveSelectedShopId(22, [], false)).toBe(22);
  });

  it("keeps an available non-first shop selected", () => {
    expect(resolveSelectedShopId(22, shops, true)).toBe(22);
  });

  it("falls back to the first shop only when the current selection is unavailable", () => {
    expect(resolveSelectedShopId(99, shops, true)).toBe(11);
    expect(resolveSelectedShopId(null, shops, true)).toBe(11);
  });
});
