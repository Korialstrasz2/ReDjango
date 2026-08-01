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

export type ManagedPlayerCharacter = {
  id: number;
  name: string;
  campaignName: string;
  inActiveCampaign: boolean;
};

export type ManagedPlayer = {
  id: number;
  name: string;
  displayName: string;
  role: string;
  roleLabel: string;
  username: string;
  hasAccount: boolean;
  accountActive: boolean;
  canUseDjangoAdmin: boolean;
  lastLogin: string;
  activeCampaignId: number | null;
  activeCampaignName: string;
  activeCharacterId: number | null;
  activeCharacterName: string;
  characters: ManagedPlayerCharacter[];
  missingCharacterIds: number[];
  pendingRequests: Array<{ characterId: number; characterName: string; message: string }>;
};

export type PlayerManagementOverview = {
  players: ManagedPlayer[];
  roles: Array<{ value: string; label: string }>;
  campaigns: Array<{ value: string; label: string }>;
  characters: Array<{
    id: number;
    name: string;
    type: string;
    level: number;
    campaignId: number | null;
    campaignName: string;
    assignedTo: string[];
  }>;
  currentPlayerId: number | null;
  passwordHelp: string[];
  /** Set only on the payload returned by a write action: the player just saved. */
  savedPlayerId: number | null;
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
  ownerCount: number;
  updatedAt: string | null;
};

export type SkillManagementOverview = {
  metrics: {
    activeSkills: number;
    archivedSkills: number;
    spells: number;
    families: number;
    groups: number;
  };
  groups: ManagedSkillGroup[];
  families: ManagedSkillFamily[];
  skills: ManagedSkillRow[];
  total: number;
  offset: number;
  limit: number;
  hasMore: boolean;
  skillOptions: Array<{ id: number; number: number; name: string; familyName: string; familyGroup: string }>;
  effectConfiguration: import("../../lib/types").EffectConfiguration;
};

export type ManagedUnitSummary = {
  id: number;
  name: string;
  category: string;
  description: string;
  imageUrl: string;
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
  loreImageId: number | null;
  loreImageUrl: string;
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
  accessoryProfileKey: string;
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
    accessoryProfiles: Array<{ value: string; label: string; description: string }>;
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

export type BackupConfiguration = {
  enabled: boolean;
  onStartup: boolean;
  intervalMinutes: number;
  retentionCount: number;
};

export type ManagedBackup = {
  id: string;
  kind: "automatic" | "manual";
  label: string;
  createdAt: string;
  createdBy: string;
  sizeBytes: number;
};

export type BackupCharacterValue = {
  key: string;
  label: string;
  value: number | string;
};

export type BackupCharacterSummary = {
  id: number;
  name: string;
  type: string;
  level: number;
  coins: number;
  damage: number;
  coreValues: BackupCharacterValue[];
};

export type BackupContainerEntry = {
  slot: number;
  name: string;
  quantity: number;
};

export type BackupCharacterDetail = BackupCharacterSummary & {
  backpack: BackupContainerEntry[];
  containers: Array<{
    name: string;
    capacity: number;
    entries: BackupContainerEntry[];
  }>;
};

export type BackupInspection = {
  backupId: string;
  characterCount: number;
  characters: BackupCharacterSummary[];
  selectedCharacter: BackupCharacterDetail | null;
};

export type BackupManagementData = {
  configuration: BackupConfiguration;
  backups: ManagedBackup[];
  createdBackupId: string | null;
  storage: {
    count: number;
    usedBytes: number;
    content: string;
  };
  inspection?: BackupInspection;
};

/* Modifica di massa del catalogo oggetti. Le liste di campi, operatori e scelte
   arrivano da /api/v1/management/items/bulk-fields: il client non conosce lo
   schema, lo riceve, così un tipo oggetto aggiunto in Amministrazione compare
   qui senza toccare il frontend. */

export type BulkFieldKind = "text" | "longText" | "integer" | "number" | "boolean" | "rarity" | "itemType" | "weaponType";

export type BulkOperatorOption = { value: string; label: string };

export type BulkField = {
  name: string;
  label: string;
  kind: BulkFieldKind;
  group: string;
  hint: string;
  nullable: boolean;
  choices: Array<{ value: string; label: string }>;
  filterOperators: BulkOperatorOption[];
  actionOperators: BulkOperatorOption[];
};

export type BulkFieldCatalog = {
  fields: BulkField[];
  valuelessFilterOperators: string[];
  valuelessActionOperators: string[];
  replacementActionOperators: string[];
  roundingModes: BulkOperatorOption[];
  previewScanCap: number;
};

export type BulkFilterRow = { field: string; operator: string; value: string };

export type BulkActionRow = {
  field: string;
  operator: string;
  value: string;
  replacement: string;
  rounding: string;
  decimals: number;
};

export type BulkChange = { field: string; label: string; before: string; after: string };

export type BulkPreview = {
  total: number;
  scanned: number;
  truncated: boolean;
  changed: number;
  sample: Array<{ id: number; name: string; changes: BulkChange[] }>;
  issues: Array<{ id: number | null; name: string; field: string; message: string }>;
  filters: BulkFilterRow[];
  actions: BulkActionRow[];
  token: string;
};

export type BulkApplyResult = {
  matched: number;
  updated: number;
  unchanged: number;
  refreshedCharacters: number;
};
