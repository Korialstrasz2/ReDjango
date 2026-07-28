import { describe, expect, it } from "vitest";

import { matchesShortcut, shortcutConflictKeys, shortcutFromKeyboardEvent, shortcutValue } from "./shortcuts";

const keyboardEvent = (overrides: Partial<KeyboardEvent> = {}) => ({
  altKey: true,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  key: "j",
  ...overrides,
}) as KeyboardEvent;

describe("keyboard shortcuts", () => {
  it("normalizes Alt keys used by the available profiles", () => {
    expect(shortcutFromKeyboardEvent(keyboardEvent())).toBe("Alt+J");
    expect(matchesShortcut(keyboardEvent({ key: "R" }), "Alt+R")).toBe(true);
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "<" }))).toBe("Alt+<");
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "," }))).toBe("Alt+,");
  });

  it("ignores combinations outside the configurable Alt-letter contract", () => {
    expect(shortcutFromKeyboardEvent(keyboardEvent({ altKey: false }))).toBeNull();
    expect(shortcutFromKeyboardEvent(keyboardEvent({ ctrlKey: true }))).toBeNull();
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "F4" }))).toBeNull();
  });

  it("uses the selected profile and falls back to Standard", () => {
    expect(shortcutValue({}, "journal")).toBe("Alt+J");
    expect(shortcutValue({ "shortcuts.profile": "fast" }, "dashboard")).toBe("Alt+<");
    expect(shortcutValue({ "shortcuts.profile": "custom", "shortcuts.journal": "Alt+K" }, "journal")).toBe("Alt+K");
  });

  it("reports every shortcut involved in an inline conflict", () => {
    expect([...shortcutConflictKeys({
      "shortcuts.dashboard": "Alt+S",
      "shortcuts.skills": "Alt+A",
      "shortcuts.lore": "Alt+A",
      unrelated: "Alt+A",
    })]).toEqual(["shortcuts.skills", "shortcuts.lore"]);
  });
});
