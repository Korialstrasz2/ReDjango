import type { ShopType } from "./types";

const iconMap: Record<string, string> = {
  store: "⌂",
  hammer: "⚒",
  shield: "◈",
  swords: "⚔",
  "bow-arrow": "➶",
  flask: "⚗",
  sparkles: "✦",
  shirt: "♢",
  backpack: "▣",
  beer: "♨",
  tent: "△",
};

export const shopIcon = (type?: ShopType) => iconMap[type?.icon || ""] || "◇";

export const shopIconOptions = Object.keys(iconMap);

export const stableSlug = (value: string) => value.trim().toLocaleLowerCase("it").normalize("NFD")
  .replace(/[\u0300-\u036f]/g, "")
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/^-|-$/g, "");

export function uniqueSlug(label: string, existingKeys: string[]): string {
  const base = stableSlug(label) || "nuovo";
  let candidate = base;
  let suffix = 2;
  while (existingKeys.includes(candidate)) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  return candidate;
}

export const itemTypeLabel = (value: string) => value
  .replace(/[_-]+/g, " ")
  .replace(/\b\w/g, (letter) => letter.toLocaleUpperCase("it"));

export const rankOptions = [
  { rank: 0, label: "Principale", short: "0", help: "Molto frequente" },
  { rank: 1, label: "Comune", short: "1", help: "Frequente" },
  { rank: 2, label: "Secondaria", short: "2", help: "Occasionale" },
  { rank: 3, label: "Rara", short: "3", help: "Poco frequente" },
  { rank: 4, label: "Eccezionale", short: "4", help: "Molto rara" },
  { rank: 5, label: "Esclusa", short: "×", help: "Mai generata" },
] as const;
