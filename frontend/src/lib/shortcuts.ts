export type PageShortcutTarget =
  | "dashboard"
  | "characters"
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
export type QuickToolShortcutTarget = "journal" | "dice";

export const pageShortcutTargets: PageShortcutTarget[] = [
  "dashboard",
  "characters",
  "character",
  "skills",
  "competencies",
  "creation",
  "combat",
  "travel",
  "market",
  "lore",
  "media",
  "guides",
  "settings",
  "tools",
];
export const quickToolShortcutTargets: QuickToolShortcutTarget[] = ["journal", "dice"];

export function shortcutValue(ui: Record<string, unknown>, target: PageShortcutTarget | QuickToolShortcutTarget): string {
  const value = ui[`shortcuts.${target}`];
  return typeof value === "string" ? value : "";
}

export function shortcutFromKeyboardEvent(event: Pick<KeyboardEvent, "altKey" | "ctrlKey" | "metaKey" | "shiftKey" | "key">): string | null {
  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || !/^[a-z]$/i.test(event.key)) return null;
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
