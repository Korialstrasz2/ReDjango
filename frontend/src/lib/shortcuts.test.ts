import { describe, expect, it } from "vitest";

import { matchesShortcut, shortcutFromKeyboardEvent, shortcutValue } from "./shortcuts";

const keyboardEvent = (overrides: Partial<KeyboardEvent> = {}) => ({
  altKey: true,
  ctrlKey: false,
  metaKey: false,
  shiftKey: false,
  key: "j",
  ...overrides,
}) as KeyboardEvent;

describe("keyboard shortcuts", () => {
  it("normalizes Alt plus a letter", () => {
    expect(shortcutFromKeyboardEvent(keyboardEvent())).toBe("Alt+J");
    expect(matchesShortcut(keyboardEvent({ key: "R" }), "Alt+R")).toBe(true);
  });

  it("ignores combinations outside the configurable Alt-letter contract", () => {
    expect(shortcutFromKeyboardEvent(keyboardEvent({ altKey: false }))).toBeNull();
    expect(shortcutFromKeyboardEvent(keyboardEvent({ ctrlKey: true }))).toBeNull();
    expect(shortcutFromKeyboardEvent(keyboardEvent({ key: "F4" }))).toBeNull();
  });

  it("reads configured shortcut values safely", () => {
    expect(shortcutValue({ "shortcuts.journal": "Alt+K" }, "journal")).toBe("Alt+K");
    expect(shortcutValue({}, "journal")).toBe("");
  });
});
