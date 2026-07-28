import { describe, expect, it } from "vitest";

import { matchesShortcut, shortcutConflictKeys, shortcutFromKeyboardEvent, shortcutValue } from "./shortcuts";

const keyboardEvent = (overrides: Partial<KeyboardEvent> = {}) => ({
  altKey: true,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  key: "j",
  code: "KeyJ",
  ...overrides,
}) as KeyboardEvent;

describe("keyboard shortcuts", () => {
  it("normalizes Alt keys used by the available profiles", () => {
    expect(shortcutFromKeyboardEvent(keyboardEvent())).toBe("Alt+J");
    expect(matchesShortcut(keyboardEvent({ key: "R" }), "Alt+R")).toBe(true);
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "<" }))).toBe("Alt+<");
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "," }))).toBe("Alt+,");
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "ò" }))).toBe("Alt+Ò");
  });

  it("falls back to the physical key when Alt swallows the character", () => {
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "Dead", code: "Quote" }))).toBe("Alt+À");
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "Unidentified", code: "KeyD" }))).toBe("Alt+D");
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "Unidentified", code: "F5" }))).toBeNull();
  });

  it("ignores combinations outside the configurable Alt-letter contract", () => {
    expect(shortcutFromKeyboardEvent(keyboardEvent({ altKey: false }))).toBeNull();
    expect(shortcutFromKeyboardEvent(keyboardEvent({ ctrlKey: true }))).toBeNull();
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "F4", code: "F4" }))).toBeNull();
  });

  it("uses the selected profile and falls back to Standard", () => {
    expect(shortcutValue({}, "journal")).toBe("Alt+J");
    expect(shortcutValue({ "shortcuts.profile": "fast" }, "dashboard")).toBe("Alt+A");
    expect(shortcutValue({ "shortcuts.profile": "fast" }, "settings")).toBe("Alt+Ù");
    expect(shortcutValue({ "shortcuts.profile": "fast" }, "ai")).toBe("Alt+V");
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
