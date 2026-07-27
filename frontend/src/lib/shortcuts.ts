export type PageShortcutTarget = "dashboard" | "characters" | "character" | "combat" | "media" | "guides" | "settings";
export type QuickToolShortcutTarget = "journal" | "dice";

export const pageShortcutTargets: PageShortcutTarget[] = ["dashboard", "characters", "character", "combat", "media", "guides", "settings"];
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
