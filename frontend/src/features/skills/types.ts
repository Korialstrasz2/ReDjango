import type { EffectOperation, Skill, SkillCatalog } from "../../lib/types";

export type PassiveFeature = {
  id: string;
  name: string;
  description: string;
  icon: string;
  operations: EffectOperation[];
};

export type ActiveReminder = {
  id: string;
  name: string;
  description: string;
  trigger: string;
  duration: string;
  usageNotes: string;
  costs: Partial<Record<"pf" | "mana" | "energia" | "potere" | "pa" | "stanchezza", number>>;
  icon: string;
  skillId?: number;
  skillName?: string;
  familyName?: string;
  familyGroup?: string;
  enabled?: boolean;
  order?: number;
  characterNote?: string;
};

export type SkillOption = { id: number; number: number; name: string; familyName: string; familyGroup?: string };

export type SkillFamilyGroup = {
  key: string;
  name: string;
  order: number;
  familyCount: number;
  skillCount: number;
  selected: boolean;
};

export type CharacterSkillAnalysis = {
  ownedSkills: number;
  passiveEffects: number;
  activeActions: number;
  xpSpent: number;
  progression: {
    currentLevel: number;
    expectedLevel: number;
    xpIntoLevel: number;
    xpForNextLevel: number;
    xpUntilNextLevel: number;
    progressPercent: number;
  };
  byGroup: Array<{ group: string; skills: number; passives: number; actions: number }>;
  byFamily: Array<{ group: string; family: string; skills: number }>;
};

export type CombatButtonModifiers = {
  attackBonus: number;
  damageBonus: number;
  damageTierBonus: number;
  penetrationFlat: number;
  penetrationPercent: number;
};

export type CombatButton = {
  id: number;
  characterId: number | null;
  characterName: string;
  name: string;
  helpText: string;
  modifiers: CombatButtonModifiers;
  public: boolean;
  active: boolean;
  keepActiveInCombat: boolean;
  order: number;
  canEdit: boolean;
};

export type CombatButtonConfiguration = {
  limit: number;
  availableSlots: number;
  own: CombatButton[];
  public: CombatButton[];
};

export type UnifiedSkill = Omit<Skill, "passiveEffects" | "activeReminders" | "familyGroup"> & {
  passiveEffects: PassiveFeature[];
  activeReminders: ActiveReminder[];
  familyGroup: string;
};

export type UnifiedSkillCatalog = Omit<SkillCatalog, "skills" | "activeReminders" | "skillOptions" | "groups" | "characterAnalysis" | "combatButtons"> & {
  skills: UnifiedSkill[];
  activeReminders: ActiveReminder[];
  skillOptions: SkillOption[];
  groups: SkillFamilyGroup[];
  selectedGroup: string;
  characterAnalysis: CharacterSkillAnalysis;
  combatButtons: CombatButtonConfiguration;
};

export const XP_LABELS: Record<string, string> = {
  general: "Generali",
  red: "Rossi",
  green: "Verdi",
  blue: "Blu",
};

export const ACTIVE_COST_LABELS: Record<string, string> = {
  pf: "PF",
  mana: "Mana",
  energia: "Energia",
  potere: "Potere",
  pa: "PA",
  stanchezza: "Stanchezza",
};

export function costsLabel(costs: ActiveReminder["costs"]): string {
  const values = Object.entries(costs || {})
    .filter(([, value]) => Number(value) > 0)
    .map(([key, value]) => `${value} ${ACTIVE_COST_LABELS[key] || key}`);
  return values.length ? values.join(" · ") : "Nessun costo";
}
