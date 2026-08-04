import { describe, expect, it } from "vitest";

import { combatFocusedCharacterId } from "./focus";
import type { CombatMap } from "./types";

const map = {
  participants: [
    { character: { id: 11 } },
    { character: { id: 22 } },
  ],
} as CombatMap;

describe("combatFocusedCharacterId", () => {
  it("always keeps a player focused on their active character", () => {
    expect(combatFocusedCharacterId(map, 11, false, 22)).toBe(11);
  });

  it("defaults a master to their active character", () => {
    expect(combatFocusedCharacterId(map, 11, true, null)).toBe(11);
  });

  it("uses only the master's explicit foreground override", () => {
    expect(combatFocusedCharacterId(map, 11, true, 22)).toBe(22);
  });

  it("falls back safely when the viewer character is not on the map", () => {
    expect(combatFocusedCharacterId(map, 99, false, null)).toBe(11);
  });
});
