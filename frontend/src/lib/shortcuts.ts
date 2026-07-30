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
export type QuickToolShortcutTarget = "journal" | "dice" | "theft" | "audio" | "ai" | "names";

export const pageShortcutTargets: PageShortcutTarget[] = [
  "dashboard", "character", "skills", "competencies", "creation", "combat", "travel", "market",
  "lore", "media", "guides", "settings", "tools",
];
export const quickToolShortcutTargets: QuickToolShortcutTarget[] = ["journal", "dice", "theft", "audio", "ai", "names"];

export type ShortcutProfile = "standard" | "fast" | "custom";
type ShortcutTarget = PageShortcutTarget | QuickToolShortcutTarget;

export const STANDARD_SHORTCUTS: Record<ShortcutTarget, string> = {
  dashboard: "Alt+S", character: "Alt+C", skills: "Alt+A", competencies: "Alt+N", creation: "Alt+K",
  combat: "Alt+B", travel: "Alt+V", market: "Alt+Q", lore: "Alt+L", media: "Alt+M", guides: "Alt+G",
  settings: "Alt+I", tools: "Alt+T", journal: "Alt+J", dice: "Alt+R", theft: "Alt+F", audio: "Alt+U", ai: "Alt+H",
  names: "Alt+P",
};

// La riga centrale di una tastiera italiana (A…Ù) segue l'ordine del menu principale,
// la riga inferiore (Z…V) copre gli strumenti rapidi.
export const FAST_SHORTCUTS: Record<ShortcutTarget, string> = {
  dashboard: "Alt+A", character: "Alt+S", skills: "Alt+D", competencies: "Alt+F", creation: "Alt+G",
  combat: "Alt+H", travel: "Alt+J", market: "Alt+K", lore: "Alt+L", media: "Alt+Ò", guides: "Alt+À",
  settings: "Alt+Ù", tools: "Alt+T", journal: "Alt+Z", dice: "Alt+X", theft: "Alt+B", audio: "Alt+C", ai: "Alt+V",
  names: "Alt+N",
};

export const PROFILE_SHORTCUTS: Record<Exclude<ShortcutProfile, "custom">, Record<ShortcutTarget, string>> = {
  standard: STANDARD_SHORTCUTS,
  fast: FAST_SHORTCUTS,
};

export const SHORTCUT_CATEGORY = "scorciatoie da tastiera";

// Combinazioni gestite direttamente dalla schermata che le usa: restano visibili
// in Impostazioni ma non hanno una riga salvata, quindi non sono modificabili né rimuovibili.
export const FIXED_SHORTCUTS: Array<{ id: string; label: string; description: string; chord: string }> = [
  {
    id: "combat.quickActions",
    label: "Azioni rapide (Combattimento)",
    description: "Apre e chiude la finestra Azioni rapide dalla pagina Combattimento. Combinazione fissa, non modificabile.",
    chord: "Ctrl + Alt",
  },
];

/** Valore mostrato in Impostazioni: i profili fissi vincono sui valori personalizzati salvati. */
export function shortcutSettingValue(profile: ShortcutProfile, key: string, customValue: unknown): unknown {
  if (profile === "custom" || !key.startsWith("shortcuts.") || key === "shortcuts.profile") return customValue;
  const target = key.slice("shortcuts.".length) as ShortcutTarget;
  return PROFILE_SHORTCUTS[profile][target] ?? customValue;
}

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

const SHORTCUT_KEY_PATTERN = /^[a-z<,.\-òàù]$/i;
// Con Alt premuto alcune tastiere non producono il carattere: ricadiamo sulla posizione fisica del tasto.
const SHORTCUT_KEY_BY_CODE: Record<string, string> = {
  Semicolon: "ò", Quote: "à", Backslash: "ù", IntlBackslash: "<", Comma: ",", Period: ".", Minus: "-",
};

type ShortcutKeyboardEvent = Pick<KeyboardEvent, "altKey" | "ctrlKey" | "metaKey" | "shiftKey" | "key"> & { code?: string };

export function shortcutFromKeyboardEvent(event: ShortcutKeyboardEvent): string | null {
  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return null;
  const code = event.code || "";
  const key = SHORTCUT_KEY_PATTERN.test(event.key)
    ? event.key
    : /^Key[A-Z]$/.test(code) ? code.slice(3) : SHORTCUT_KEY_BY_CODE[code] || "";
  if (!key) return null;
  return `Alt+${key.toLocaleUpperCase("it")}`;
}

export function matchesShortcut(event: ShortcutKeyboardEvent, shortcut: string): boolean {
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
