// I payload dei due banchi viaggiano come dict aperto lato Ninja, quindi la
// forma vive qui invece che nello schema generato.

export type ForgeMaterial = {
  key: string;
  label: string;
  tier: number;
  branch: "leggero" | "pesante";
  quantity: number;
  unlocked: boolean;
  unlockedBy: string;
  requiresSkill: string;
  toolsReady: boolean;
};

export type ForgeBlueprint = {
  itemId: number;
  name: string;
  icon: string;
  type: string;
  category: string;
  categoryLabel: string;
  material: string;
  materialLabel: string;
  tier: number;
  ingots: number;
  hours: number;
  quantity: number;
  value: number;
  canForge: boolean;
  blockedReason: string;
};

export type ForgeImprovementOption = {
  key: string;
  label: string;
  baseCost: number;
  nextCost: number;
  mode: "effect" | "column" | "rule";
  stack: number;
};

export type ForgeInstance = {
  instanceId: number;
  name: string;
  icon: string;
  type: string;
  material: string;
  materialLabel: string;
  tier: number;
  kind: string;
  weight: number;
  pointsSpent: number;
  pointsMax: number;
  budgetFormula: string;
  fatigueBonus: number;
  improvable: boolean;
  blockedReason: string;
  improvements: Array<{ key: string; stack: number; pointsPaid: number }>;
  tableRules: string[];
  options: ForgeImprovementOption[];
};

export type ForgeData = {
  character: { id: number; name: string; level: number; fatigue: number };
  capability: {
    canMelt: boolean;
    canReshape: boolean;
    canForgeAnywhere: boolean;
    arrowBonus: number;
    practicalLevel: number;
    fatigueForExtraPoint: number;
    specialistMaterial: string;
    maxTier: number;
    unlockedCount: number;
  };
  tools: { level: number; name: string };
  materials: ForgeMaterial[];
  blueprints: ForgeBlueprint[];
  practical: Array<{ itemId: number; name: string; icon: string; type: string; leather: number; canForge: boolean; blockedReason: string }>;
  improvable: ForgeInstance[];
  tableRules: Array<{ skill: string; text: string }>;
  notes: string;
  rules: Record<string, string>;
};

export type EnchantGem = { slot: number; itemId: number; name: string; level: number; filled: boolean };
export type EnchantAltar = { itemId: number; name: string; bonus: number; bonusPercent: number; portable: boolean };
export type EnchantTarget = { slot: number; itemId: number; name: string; type: string; isInstance: boolean; existingEffects: number };
export type EnchantKind = { kind: string; label: string; resultItemId: number; resultName: string; value: number; hasEffects: boolean };

export type EnchantedItem = {
  instanceId: number;
  name: string;
  icon: string;
  type: string;
  kind: string;
  effects: Array<{ kind: string; label: string; level: number; charges: number; chargesMax: number; mana: number }>;
  spell: string;
  scrollLevel: number;
  castEffect: number;
  tableRules: string[];
};

export type EnchantData = {
  character: { id: number; name: string; level: number; fatigue: number };
  capability: {
    maxItemLevel: number;
    maxScrollLevel: number;
    manaPerLevel: number;
    chargeBonusPercent: number;
    maxEffects: number;
    canReenchant: boolean;
    canCombineGems: boolean;
    canDisenchant: boolean;
    fatigueLevelBonus: number;
  };
  gems: EnchantGem[];
  altars: EnchantAltar[];
  targets: EnchantTarget[];
  preview: { slotType: string; level: number; kinds: EnchantKind[] };
  manaLadder: Array<{ level: number; mana: number }>;
  spells: Array<{ spellId: number; name: string; school: string; tier: string; minimumMana: number; formula: string; effectUnit: string }>;
  scrollLadder: number[];
  enchanted: EnchantedItem[];
  tableRules: Array<{ skill: string; text: string }>;
  notes: string;
  rules: Record<string, string>;
};

export const TIER_LABELS = ["", "I", "II", "III", "IV", "V", "VI", "VII"];

export function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}
