import type { PageShortcutTarget } from "./shortcuts";

export type ShellNavigationItem = {
  href: string;
  label: string;
  icon: string;
  shortcutTarget?: PageShortcutTarget;
  management: boolean;
};

export function playerNavigation(characterPath: string): ShellNavigationItem[] {
  return [
    { href: "/", label: "Menu", icon: "⌂", shortcutTarget: "dashboard", management: false },
    { href: characterPath, label: "PG", icon: "⚔", shortcutTarget: "character", management: false },
    { href: "/skills", label: "Abilità", icon: "✦", shortcutTarget: "skills", management: false },
    { href: "/competencies", label: "Competenze", icon: "✧", shortcutTarget: "competencies", management: false },
    { href: "/creation", label: "Creazione", icon: "⚗", shortcutTarget: "creation", management: false },
    { href: "/combat", label: "Combattimento", icon: "✦", shortcutTarget: "combat", management: false },
    { href: "/travel", label: "Viaggio", icon: "⌖", shortcutTarget: "travel", management: false },
    { href: "/market", label: "Mercato", icon: "¤", shortcutTarget: "market", management: false },
    { href: "/lore", label: "Lore", icon: "◈", shortcutTarget: "lore", management: false },
    { href: "/media", label: "Immagini", icon: "▧", shortcutTarget: "media", management: false },
    { href: "/guides", label: "Guide", icon: "☷", shortcutTarget: "guides", management: false },
    { href: "/settings", label: "Impostazioni", icon: "⚙", shortcutTarget: "settings", management: false },
  ];
}

export function managementNavigation(canManageAdminSettings: boolean): ShellNavigationItem[] {
  const links: ShellNavigationItem[] = [
    { href: "/tools", label: "Strumenti", icon: "◆", shortcutTarget: "tools", management: true },
    { href: "/tools/characters", label: "Gestione Personaggi", icon: "♙", management: true },
    { href: "/tools/items", label: "Gestione Oggetti", icon: "◇", management: true },
    { href: "/tools/skills", label: "Gestione Skill", icon: "✦", management: true },
    { href: "/tools/units", label: "Gestione Unit", icon: "⚔", management: true },
    { href: "/tools/shops", label: "Gestione Negozi", icon: "¤", management: true },
    { href: "/tools/ai", label: "Gestione AI", icon: "✳", management: true },
  ];
  if (canManageAdminSettings) links.push(
    { href: "/tools/players", label: "Gestione Player", icon: "☺", management: true },
    { href: "/tools/backups", label: "Gestione Backup", icon: "▣", management: true },
    { href: "/tools/dice", label: "Gestisci Dadi", icon: "◆", management: true },
    { href: "/tools/themes", label: "Gestione Temi", icon: "◐", management: true },
    { href: "/tools/variables", label: "Gestione Variabili", icon: "ƒ", management: true },
  );
  return links;
}

export function isNavigationActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/characters" || href.startsWith("/character/")) return pathname.startsWith("/character/");
  return pathname === href || pathname.startsWith(`${href}/`);
}
