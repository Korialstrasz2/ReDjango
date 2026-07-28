export type PageShortcutTarget =
  | "dashboard"
  | "character"
  | "skills"
  | "competencies"
  | "creation"
  | "combat"
  | "travel"
  | "market"
  | "lore"
  | "media"
  | "guides"
  | "settings"
  | "tools";
export type QuickToolShortcutTarget = "journal" | "dice" | "audio" | "ai";

export const pageShortcutTargets: PageShortcutTarget[] = [
  "dashboard", "character", "skills", "competencies", "creation", "combat", "travel", "market",
  "lore", "media", "guides", "settings", "tools",
];
export const quickToolShortcutTargets: QuickToolShortcutTarget[] = ["journal", "dice", "audio", "ai"];

export type ShortcutProfile = "standard" | "fast" | "custom";
type ShortcutTarget = PageShortcutTarget | QuickToolShortcutTarget;

export const STANDARD_SHORTCUTS: Record<ShortcutTarget, string> = {
  dashboard: "Alt+S", character: "Alt+C", skills: "Alt+A", competencies: "Alt+N", creation: "Alt+K",
  combat: "Alt+B", travel: "Alt+V", market: "Alt+Q", lore: "Alt+L", media: "Alt+M", guides: "Alt+G",
  settings: "Alt+I", tools: "Alt+T", journal: "Alt+J", dice: "Alt+R", audio: "Alt+U", ai: "Alt+H",
};

// The physical bottom row of an Italian keyboard mirrors the main sidebar order.
export const FAST_SHORTCUTS: Record<ShortcutTarget, string> = {
  dashboard: "Alt+<", character: "Alt+Z", skills: "Alt+X", competencies: "Alt+C", creation: "Alt+V",
  combat: "Alt+B", travel: "Alt+N", market: "Alt+M", lore: 'Alt+,', media: "Alt+.", guides: "Alt+-",
  settings: "Alt+W", tools: "Alt+Y", journal: "Alt+A", dice: "Alt+H", audio: "Alt+J", ai: "Alt+K",
};

export function shortcutProfile(ui: Record<string, unknown>): ShortcutProfile {
  const profile = ui["shortcuts.profile"];
  return profile === "fast" || profile === "custom" ? profile : "standard";
}

export function shortcutValue(ui: Record<string, unknown>, target: ShortcutTarget): string {
  const profile = shortcutProfile(ui);
  if (profile === "standard") return STANDARD_SHORTCUTS[target];
  if (profile === "fast") return FAST_SHORTCUTS[target];
  const value = ui[`shortcuts.${target}`];
  return typeof value === "string" ? value : STANDARD_SHORTCUTS[target];
}

export function shortcutFromKeyboardEvent(event: Pick<KeyboardEvent, "altKey" | "ctrlKey" | "metaKey" | "shiftKey" | "key">): string | null {
  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || !/^[a-z<,.-]$/i.test(event.key)) return null;
  return `Alt+${event.key.toLocaleUpperCase("it")}`;
}

export function matchesShortcut(event: Pick<KeyboardEvent, "altKey" | "ctrlKey" | "metaKey" | "shiftKey" | "key">, shortcut: string): boolean {
  return Boolean(shortcut) && shortcutFromKeyboardEvent(event) === shortcut;
}

export function shortcutConflictKeys(values: Record<string, unknown>): Set<string> {
  const owners = new Map<string, string>();
  const conflicts = new Set<string>();
  Object.entries(values).forEach(([key, rawValue]) => {
    if (!key.startsWith("shortcuts.") || typeof rawValue !== "string" || !rawValue) return;
    const owner = owners.get(rawValue);
    if (owner) {
      conflicts.add(owner);
      conflicts.add(key);
    } else {
      owners.set(rawValue, key);
    }
  });
  return conflicts;
}
