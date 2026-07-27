import type { CompetenceEntry, CompetenceRoll } from "../../lib/types";

export type CompetenceTechnique = "standard" | "focus" | "amplify";

export function techniqueEnergyCost(masteryRank: number, technique: CompetenceTechnique): number {
  const discount = masteryRank >= 5 ? 1 : 0;
  if (technique === "focus") return Math.max(0, 3 - discount);
  if (technique === "amplify") return Math.max(0, 6 - discount);
  return 0;
}

export function techniqueUnlocked(masteryRank: number, technique: CompetenceTechnique): boolean {
  if (technique === "focus") return masteryRank >= 1;
  if (technique === "amplify") return masteryRank >= 3;
  return true;
}

export function latestDieValue(roll?: CompetenceRoll | null): number | null {
  const latest = roll?.rolls.at(-1);
  return latest && typeof latest.value === "number" ? latest.value : null;
}

export function rollEquation(entry: CompetenceEntry, technique: CompetenceTechnique): string {
  const techniqueBonus = technique === "focus" ? 1 : technique === "amplify" ? 2 : 0;
  const pieces = [`d${entry.dieSides}`, `${entry.rollModifier >= 0 ? "+" : "−"} ${Math.abs(entry.rollModifier)}`];
  if (techniqueBonus) pieces.push(`+ ${techniqueBonus}`);
  return `(${pieces.join(" ")})`;
}
