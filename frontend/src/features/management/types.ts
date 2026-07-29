export type ManagementField = {
  key: string;
  label: string;
  type: "text" | "textarea" | "integer" | "boolean" | "select" | "json" | "item" | "effect" | "campaign" | "image";
  group: string;
  nullable?: boolean;
  readOnly?: boolean;
  minimum?: number;
  choices?: Array<{ value: string; label: string }>;
};

export type ManagedCharacterSummary = {
  id: number;
  name: string;
  internalName: string;
  type: string;
  level: number;
  campaignId: number | null;
  campaignName: string;
  missingRelations: string[];
  updatedAt: string | null;
};

export type OrphanRecord = {
  kind: string;
  label: string;
  id: number;
  name: string;
  reason: string;
  contents: string;
  attachable: boolean;
  updatedAt: string | null;
};

export type CharacterManagementOverview = {
  characters: ManagedCharacterSummary[];
  orphans: OrphanRecord[];
  relationKinds: Array<{ value: string; label: string; attachable: boolean }>;
  campaigns: Array<{ value: string; label: string }>;
};

export type ManagedRelation = {
  kind: string;
  label: string;
  present: boolean;
  id: number | null;
  name: string;
  fields: ManagementField[];
  values: Record<string, unknown>;
};

export type DeletionRecord = {
  kind: string;
  label: string;
  id: number | null;
  name: string;
  willDelete: boolean;
  status: "delete" | "shared" | "missing" | "empty";
  detail: string;
};

export type CharacterManagementDetail = {
  character: ManagedCharacterSummary;
  profileFields: ManagementField[];
  profile: Record<string, unknown>;
  relations: ManagedRelation[];
  options: {
    items: Array<{ id: number; name: string; archived: boolean }>;
    effects: Array<{ id: number; name: string }>;
    campaigns: Array<{ value: string; label: string }>;
    images: Array<{ id: number; name: string }>;
  };
  inventoryContainers: Array<{
    id: number;
    name: string;
    scope: string;
    capacity: number;
    weightless: boolean;
    entries: Array<{ slot: number; name: string; quantity: number; isReagent: boolean }>;
  }>;
  deletionPreview: {
    token: string;
    confirmation: string;
    records: DeletionRecord[];
  };
};

export type ManagedSkillGroup = {
  id: number;
  name: string;
  slug: string;
  order: number;
  notes: string;
  archived: boolean;
  familyCount: number;
  skillCount: number;
};

export type ManagedSkillFamily = {
  id: number;
  name: string;
  groupId: number;
  group: string;
  groupSlug: string;
  order: number;
  isClass: boolean;
  isReligion: boolean;
  isPerk: boolean;
  notes: string;
  additionalNotes: string;
  imageId: number | null;
  imageUrl: string;
  archived: boolean;
  activeSkillCount: number;
  archivedSkillCount: number;
  spellCount: number;
  skillCount: number;
  selected: boolean;
};

export type ManagedSkillRow = {
  id: number;
  number: number;
  name: string;
  slug: string;
  familyId: number;
  familyName: string;
  groupId: number;
  groupName: string;
  baseXpCost: number;
  xpType: string;
  xpTypeLabel: string;
  magic: boolean;
  spellTier: string | null;
  passiveCount: number;
  actionCount: number;
  prerequisiteCount: number;
  archived: boolean;
  sourceProject: string;
  sourceId: number | null;
  updatedAt: string | null;
};

export type SkillReviewSummary = {
  id: number;
  sourceProject: string;
  sourceId: number;
  name: string;
  severity: "blocked" | "warning";
  decision: string;
  status: "open" | "imported" | "ignored";
  blockers: string[];
  blockerLabels: string[];
  warnings: string[];
  warningLabels: string[];
  edited: boolean;
  liveSkillId: number | null;
  updatedAt: string | null;
};

export type SkillReviewDetail = SkillReviewSummary & {
  suggestedValues: Record<string, unknown>;
  workingValues: Record<string, unknown>;
  source: Record<string, unknown>;
  resolutionNotes: string;
};

export type SkillManagementOverview = {
  metrics: {
    activeSkills: number;
    archivedSkills: number;
    spells: number;
    families: number;
    groups: number;
    openReviews: number;
    blockedReviews: number;
  };
  groups: ManagedSkillGroup[];
  families: ManagedSkillFamily[];
  skills: ManagedSkillRow[];
  skillOptions: Array<{ id: number; number: number; name: string; familyName: string; familyGroup: string }>;
  reviews: SkillReviewSummary[];
  effectConfiguration: import("../../lib/types").EffectConfiguration;
};

export type ManagedUnitSummary = {
  id: number;
  name: string;
  category: string;
  description: string;
  generationKind: "creature" | "humanoid" | "";
  generationKindLabel: string;
  coreKey: string;
  coreLabel: string;
  hasEquipment: boolean;
  hasSkills: boolean;
  ready: boolean;
  archived: boolean;
  updatedAt: string | null;
  sourceProject: string;
  sourceIds: number[];
};

export type UnitGenerationDraft = {
  kind: "creature" | "humanoid" | "";
  coreKey: string;
  coreShare: number;
  startingXp: number;
  xpBase: number;
  xpGrowth: number;
  competenceStartingXp: number;
  competenceXpBase: number;
  competenceXpGrowth: number;
  finalSpendingPasses: number;
  magicPolicy: "none" | "any";
  allowedClassFamilies: string[];
  allowedReligionFamilies: string[];
  allowedRaces: string[];
  allowedSubraces: string[];
  allowHumanoidStatGrowth: boolean;
};

export type UnitSkillPoolEntry = {
  skillId: number;
  skillName: string;
  family: string;
  group: string;
  pool: "core" | "archetype";
  perkTier?: "minor" | "major";
  weight: number;
  minLevel: number;
  maxLevel: number;
  requiredAtLevel?: number;
};

export type UnitItemPoolEntry = {
  itemId: number;
  itemName: string;
  minLevel: number;
  maxLevel: number;
  weight: number;
  chance: number;
};

export type UnitEquipmentSlotEntry = UnitItemPoolEntry & {
  slot: string;
};

export type UnitEquipmentGroup = {
  name: string;
  slots: string[];
  minCount: number;
  maxCount: number;
  emptyChance: number;
  items: UnitItemPoolEntry[];
};

export type UnitAccessoryCountBand = {
  minLevel: number;
  maxLevel: number;
  minCount: number;
  maxCount: number;
};

export type UnitInnateAction = {
  key: string;
  name: string;
  description: string;
  minLevel: number;
  maxLevel: number;
  costs: Record<string, number>;
  trigger: string;
  duration: string;
  icon: string;
};

export type UnitStatCurve = {
  key: string;
  profile: "very_low" | "low" | "medium" | "high" | "very_high" | "custom";
  level1: number;
  level20: number;
};

export type ManagedUnitDetail = {
  id: number | null;
  name: string;
  category: string;
  archetypeDescription: string;
  competenceProfile: Record<string, number>;
  archetypeTags: Record<string, number>;
  statProfile: {
    baseModifiers: Record<string, number>;
    perLevelModifiers: Record<string, number>;
    milestones: Array<Record<string, unknown>>;
    curves: UnitStatCurve[];
  };
  skillUnlocks: UnitSkillPoolEntry[];
  equipmentSlots: UnitEquipmentSlotEntry[];
  equipmentGroups: UnitEquipmentGroup[];
  accessoryCountByLevel: UnitAccessoryCountBand[];
  innateActions: UnitInnateAction[];
  levels: Array<Record<string, unknown>>;
  loreDescription: string;
  notes: string;
  archived: boolean;
  generation: UnitGenerationDraft;
  metadata: Record<string, unknown>;
  catalog?: ManagedUnitSummary;
};

export type UnitManagementOverview = {
  units: ManagedUnitSummary[];
  configuration: {
    kinds: Array<{ value: "creature" | "humanoid"; label: string }>;
    cores: Array<{ value: string; label: string; profile: Record<string, number> }>;
    tags: Array<{ key: string; label: string; minimum: number; maximum: number }>;
    equipmentSlots: Array<{ value: string; label: string }>;
    competences: Array<{ key: string; label: string }>;
    magicPolicies: Array<{ value: "none" | "any"; label: string }>;
    classFamilies: Array<{ value: string; label: string }>;
    religionFamilies: Array<{ value: string; label: string }>;
    races: Array<{
      value: string;
      label: string;
      subraces: Array<{ value: string; label: string }>;
    }>;
    statCurveProfiles: Array<{ value: UnitStatCurve["profile"]; label: string }>;
    statCurveVariables: Array<{
      key: string;
      label: string;
      presets: Record<Exclude<UnitStatCurve["profile"], "custom">, { level1: number; level20: number }>;
    }>;
  };
};

export type UnitSkillOption = {
  id: number;
  name: string;
  family: string;
  group: string;
  isClass: boolean;
  isReligion: boolean;
  isPerk: boolean;
  baseXpCost: number;
};

export type UnitItemOption = {
  id: number;
  name: string;
  types: string[];
  rarity: number | null;
};

export type UnitGenerationPreview = {
  name: string;
  level: number;
  totals: Record<string, number>;
  skills: Array<{ id: number; name: string; family: string; xpSpent: number }>;
  equipment: Array<{ slot: string; itemId: number; name: string }>;
  competences: Record<string, { barra1: number; barra2: number; extra: number }>;
  innateActions: UnitInnateAction[];
  trace: {
    kind: string;
    warnings: string[];
    perks: Array<{ skillId: number; name: string; tier: string; level: number }>;
    xp: Record<string, number>;
    competences: Record<string, number | string>;
  };
};
