export type AlchemyColor = "rosso" | "verde" | "blu";
export type AlchemySelection = { color: AlchemyColor; level: number };

export type AlchemyMultiplierSnapshot = {
  colors: Array<{ color: AlchemyColor; value: number }>;
  levels: Array<{ level: number; value: number }>;
};

export function potionLevelForPotency(potency: number): number {
  if (!Number.isFinite(potency) || potency < 3) return 0;
  return Math.min(10, Math.floor(potency / 3));
}

export function projectedBrew(
  multipliers: AlchemyMultiplierSnapshot,
  ingredients: AlchemySelection[],
  potionColor: AlchemyColor,
  setBonus: number,
) {
  const levelTotal = ingredients.reduce((total, ingredient) => {
    return total + (multipliers.levels.find((entry) => entry.level === ingredient.level)?.value || 0);
  }, 0);
  const abilityBonus = multipliers.colors.find((entry) => entry.color === potionColor)?.value || 0;
  const safeSetBonus = Number.isFinite(setBonus) ? Math.max(0, setBonus) : 0;
  const potency = Math.max(0, Math.round(levelTotal * (safeSetBonus + abilityBonus) * 100) / 100);
  return {
    levelTotal,
    abilityBonus,
    setBonus: safeSetBonus,
    potency,
    potionLevel: potionLevelForPotency(potency),
  };
}

export function selectedQuantity(ingredients: AlchemySelection[], color: AlchemyColor, level: number): number {
  return ingredients.filter((ingredient) => ingredient.color === color && ingredient.level === level).length;
}
