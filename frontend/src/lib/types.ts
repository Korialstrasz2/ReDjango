import type { components } from "./generated/api";

export type DiceModifier = { key: string; label: string; value: number };
export type CharacterSheet = components["schemas"]["CharacterSheetSchema"] & { diceModifiers: DiceModifier[] };
export type CharacterSummary = Pick<CharacterSheet, "id" | "name" | "type" | "races" | "level" | "details" | "primaryTotals">;
export type CharacterSlot = components["schemas"]["SlotSchema"];
export type Item = components["schemas"]["ItemSchema"];
export type ItemSpecialReason = components["schemas"]["ItemSpecialReasonSchema"];
export type Effect = components["schemas"]["EffectSchema"];
export type EffectConfiguration = components["schemas"]["EffectConfigurationSchema"];
export type EffectOperation = components["schemas"]["EffectOperationSchema"];
export type EffectPreset = components["schemas"]["EffectPresetSchema"];
export type ItemCatalog = components["schemas"]["ItemCatalogDataSchema"];
export type SkillFamily = components["schemas"]["SkillFamilySchema"];
export type Skill = components["schemas"]["SkillSchema"];
export type SkillCatalog = components["schemas"]["SkillCatalogDataSchema"];
export type SkillUnlockPreview = components["schemas"]["SkillUnlockPreviewSchema"];
export type CompetenceCatalog = components["schemas"]["CompetenceCatalogDataSchema"];
export type CompetenceEntry = components["schemas"]["CompetenceEntrySchema"];
export type CompetenceRoll = components["schemas"]["CompetenceRollSchema"];
export type AlchemyCreationData = components["schemas"]["AlchemyCreationDataSchema"];
export type AlchemyBrewResult = components["schemas"]["AlchemyBrewResultSchema"];
export type AlchemyCatalogReagent = components["schemas"]["AlchemyCatalogReagentSchema"];

export type CompendiumReference = components["schemas"]["ItemCompendiumReferenceDataSchema"];
export type CompendiumPage = components["schemas"]["ItemCompendiumPageDataSchema"];
export type CompendiumItem = components["schemas"]["CompendiumItemSchema"];
export type CompendiumWeaponCategory = components["schemas"]["CompendiumWeaponCategorySchema"];
export type CompendiumAxis = components["schemas"]["CompendiumAxisSchema"];
export type CompendiumGlossaryEntry = components["schemas"]["CompendiumGlossaryEntrySchema"];

export type GuideEntry = { title: string; meta?: string; note?: string };

export type GuideVariable = { key: string; label: string; description: string; facts: string[] };
export type GuideVariableGroup = { label: string; variables: GuideVariable[]; note?: { title: string; text: string } };

export type GuideBlock = {
  type: "heading" | "paragraph" | "list" | "code" | "callout" | "warning" | "legacy_html" | "entries" | "variable_reference" | "item_compendium";
  text?: string;
  html?: string;
  level?: number;
  items?: string[] | GuideEntry[];
  title?: string;
  language?: string;
  groups?: GuideVariableGroup[];
};

export type Guide = {
  id: number | null;
  name: string;
  category: string;
  order: number;
  content: GuideBlock[];
};

export type BootstrapData = {
  user: { id: number; username: string; isAuthenticated: boolean; role: string };
  security: SecurityData;
  guides: Guide[];
  activeCampaignId: number | null;
  campaigns: CampaignData[];
};

export type CampaignData = {
  id: number;
  name: string;
  isActive: boolean;
  isSelected: boolean;
  weather: string;
  weatherLabel: string;
  weatherEffects: string;
  currentTime: string;
  currentHour: number;
  daysSinceStart: number;
  sharedNotes: string;
};

export type SecurityData = {
  role: "user" | "master" | "admin";
  roleRank: number;
  hierarchy: Array<{ id: string; label: string; rank: number; description: string }>;
  showRoleLabels: boolean;
  showAdminLink: boolean;
  canUseDjangoAdmin: boolean;
  canManageMasterSettings: boolean;
  canManageGameData: boolean;
  canManageAdminSettings: boolean;
  adminUrl: string;
};

export type AccessRuntimeData = {
  activeAccessMode: "locked" | "lan" | "online";
  configuredAccessMode: "locked" | "lan" | "online";
  restartRequired: boolean;
  restartAvailable: boolean;
  onlineReady: boolean;
};

export type AuthData = {
  authenticated: boolean;
  user: {
    id: number;
    username: string;
    displayName: string;
    role: "user" | "master" | "admin";
    canUseDjangoAdmin: boolean;
  } | null;
  runtime: AccessRuntimeData;
  adminUrl: string;
};

export type PersonaggiData = {
  giocatore: { id: number; name: string; displayName: string; role: string; activePersonaggioId: number | null };
  personaggi: CharacterSummary[];
  activePersonaggio: CharacterSheet | null;
};

export type ThemeData = {
  slug: string;
  name: string;
  description: string;
  colors: Record<string, string>;
  overlayOpacity: number;
  panelOpacity: number;
  backgroundPosition: string;
  backgroundBlur: number;
  backgrounds: Record<string, string>;
};

export type SettingData = {
  key: string;
  label: string;
  category: string;
  description: string;
  minimumRole: string;
  valueType: "boolean" | "integer" | "color" | "select" | "string" | "json";
  value: unknown;
  baseValue: unknown;
  isOverride: boolean;
  choices: Array<{ value: string; label: string } | string>;
  constraints: { minimum?: number; maximum?: number; step?: number };
  editable: boolean;
  uiToken: string;
  order: number;
};

export type SettingsData = {
  giocatore: { id: number; name: string; displayName: string };
  player: {
    alias: string;
    characters: Array<{
      id: number;
      name: string;
      assigned: boolean;
      requestStatus: "" | "pending" | "approved" | "rejected";
    }>;
  };
  security: SecurityData;
  runtime: AccessRuntimeData;
  settings: SettingData[];
  ui: Record<string, unknown>;
  themes: ThemeData[];
  theme: ThemeData | null;
};

export type GameVariableField = {
  id: string;
  key: string;
  label: string;
  section: "base" | "formulas" | "rules" | "notes";
  group: string;
  valueType: "integer" | "number" | "formula" | "multi_select" | "text";
  value: unknown;
  defaultValue: unknown;
  constraints: {
    minimum?: number;
    maximum?: number;
    step?: number;
    suffix?: string;
    maximumLength?: number;
  };
  choices: Array<{ value: string; label: string }>;
  guide: {
    summary: string;
    influence: string;
    currentRule: string;
    technicalKey: string;
  };
};

export type GameVariableGroup = {
  id: string;
  label: string;
  section: GameVariableField["section"];
  fields: GameVariableField[];
};

export type GameVariablesData = {
  profile: {
    name: string;
    revision: string;
    updatedAt: string | null;
  };
  sections: Array<{ id: "all" | GameVariableField["section"]; label: string }>;
  groups: GameVariableGroup[];
  summary: {
    fieldCount: number;
    baseCount: number;
    formulaCount: number;
    ruleCount: number;
  };
  calculationOrder: string[];
};

export type GameVariablesValidation = {
  valid: true;
  previewToken: string;
  changedCount: number;
  changes: Array<{
    fieldId: string;
    label: string;
    before: string;
    after: string;
    section: GameVariableField["section"];
  }>;
  warnings: string[];
  message: string;
};

export type ManagedThemeBackground = {
  id: number | null;
  title: string;
  url: string;
  thumbnailUrl: string;
};

export type ManagedTheme = {
  id: number;
  slug: string;
  name: string;
  description: string;
  isActive: boolean;
  isDefault: boolean;
  order: number;
  colors: Record<string, string>;
  overlayOpacity: number;
  panelOpacity: number;
  backgroundPosition: string;
  backgroundBlur: number;
  backgrounds: Record<string, ManagedThemeBackground>;
  isSeeded: boolean;
  preview: ThemeData;
};

export type ThemeSurface = { key: string; label: string; section: string; hint: string };

export type ThemeSurfaceSection = { key: string; label: string; description: string };

export type ManagedThemesData = {
  themes: ManagedTheme[];
  colorFields: Array<{ field: string; key: string; label: string; fallbackSetting: string }>;
  surfaces: ThemeSurface[];
  surfaceSections: ThemeSurfaceSection[];
  fallbacks: Record<string, string>;
  activeCount: number;
};

export type DamageRules = {
  version: number;
  bounds: {
    attackDifferenceMinimum: number;
    attackDifferenceMaximum: number;
    d20Minimum: number;
    d20Maximum: number;
    resistanceLevelMinimum: number;
    resistanceLevelMaximum: number;
    tierMinimum: number;
    tierMaximum: number;
  };
  resistancePercentages: Record<string, number>;
  tierDamageFormulas: Record<string, string>;
  damageMultipliers: Record<string, number[]>;
};

export type DamageRulesData = {
  profile: {
    name: string;
    revision: string;
    updatedAt: string | null;
  };
  rules: DamageRules;
  defaults: DamageRules;
  counts: {
    resistanceLevels: number;
    damageTiers: number;
    d20Rows: number;
    attackDifferenceColumns: number;
  };
  behaviour: {
    resistanceOutsideRange: string;
    tierOutsideRange: string;
    gridLookup: string;
  };
};

export type DamageRulesValidation = {
  valid: true;
  previewToken: string;
  changedCount: number;
  changeCounts: {
    resistances: number;
    tiers: number;
    multipliers: number;
    total: number;
  };
  warnings: string[];
  message: string;
};

export type DiceTexture = {
  sides: number;
  imageId: number;
  imageUrl: string;
  imageName: string;
  offsetX: number;
  offsetY: number;
  scale: number;
  rotation: number;
};

export type DiceSet = {
  id: number;
  slug: string;
  name: string;
  description: string;
  dice: number[];
  surfaceColor: string;
  accentColor: string;
  textColor: string;
  textures: DiceTexture[];
  untexturedDice: number[];
  isActive: boolean;
  isDefault: boolean;
  order: number;
  createdAt: string | null;
  updatedAt: string | null;
};

export type DiceSetsData = { diceSets: DiceSet[]; defaultDiceSetId: number | null };

export type DiceHistoryRoll = components["schemas"]["DiceHistoryRollSchema"];
export type DiceHistoryData = components["schemas"]["DiceHistoryDataSchema"];

export type DiceRoll = {
  diceSetId: number | null;
  diceSetName: string;
  notation: string;
  sides: number;
  count: number;
  rolls: number[];
  modifier: number;
  subtotal: number;
  total: number;
  rolledAt: string;
};

export type NoteSection = "zaino" | "furto" | "combat" | "competenze" | "crafting" | "viaggio" | "appunti" | "missioni" | "background";

export type NoteSections = Record<NoteSection, string>;

export type CharacterNotesData = {
  characterId: number;
  characterName: string;
  noteId: number | null;
  sections: NoteSections;
  updatedAt: string | null;
};

export type MediaAsset = {
  id: number;
  title: string;
  originalName: string;
  url: string;
  thumbnailUrl: string;
  mimeType: string;
  sizeBytes: number;
  notes: string;
  folder: string;
  usageType: string;
  categoryId: number | null;
  category: string;
  categorySlug: string;
  group: string;
  source: string;
  limitedVisibility: boolean;
  createdAt: string | null;
  canDelete: boolean;
  canMove: boolean;
  canSetLimitedVisibility: boolean;
};

export type MediaUsage = {
  model: string;
  type: string;
  id: number;
  name: string;
  label: string;
  field: string;
  deletionBehavior: "cascade" | "clear" | "protect" | "other";
};

export type MediaDetailData = {
  asset: MediaAsset;
  usages: MediaUsage[];
  usageCount: number;
};

export type ImageCategory = {
  id: number;
  name: string;
  slug: string;
  description: string;
  usageTypes: string[];
  order: number;
};

export type MediaLibraryData = {
  assets: MediaAsset[];
  categories: ImageCategory[];
};

export type AIProviderSummary = {
  id: number;
  slug: string;
  name: string;
  purpose: "chat" | "image";
  kind: string;
  model: string;
  isEnabled: boolean;
  isDefault: boolean;
  description: string;
  isConfigured: boolean;
  isReady: boolean;
  configurationIssues: string[];
  capabilities: {
    chat: boolean;
    tools: boolean;
    reasoning: boolean;
    verbosity: boolean;
    images: boolean;
    imageEditing: boolean;
  };
  imageGeneration?: {
    sizes: Array<{ value: string; label: string }>;
    qualities: Array<{ value: string; label: string }>;
    defaultSize: string;
    defaultQuality: string;
  };
};

export type AIManagedProvider = AIProviderSummary & {
  authStrategy: string;
  baseUrl: string;
  hasSecret: boolean;
  suggestedModels: string[];
  modelCatalog: Array<{
    id: string;
    label: string;
    contextWindow: number | null;
    capabilities: AIProviderSummary["capabilities"];
  }>;
  modelCatalogRefreshedAt: string;
  canFetchModels: boolean;
  configurationSchema: {
    maxTokens: { minimum: number; maximum: number };
    reasoningEfforts: string[];
    verbosityOptions: string[];
  };
  maxTokens: number | null;
  effort: string;
  verbosity: string;
  disableTools: boolean;
  order: number;
};

export type AIToolSummary = {
  name: string;
  description: string;
  scope: string;
  minimumRole: "user" | "master" | "admin";
  readOnly: boolean;
};

export type AIAgentSummary = {
  id: number;
  slug: string;
  name: string;
  description: string;
  minimumRole: "user" | "master" | "admin";
  providerId: number | null;
  providerName: string;
  model: string;
  effectiveProviderName: string;
  effectiveModel: string;
  isReady: boolean;
  availabilityIssues: string[];
  toolNames: string[];
  maxIterations: number;
  routingMode: "off" | "auto";
  isEnabled: boolean;
  isDefault: boolean;
};

export type AIManagedAgent = AIAgentSummary & {
  instructions: string;
  configuredToolNames: string[];
  order: number;
};

export type AIWorkspaceData = {
  agents: AIAgentSummary[];
  chatProviders: AIProviderSummary[];
  imageProviders: AIProviderSummary[];
  tools: AIToolSummary[];
  conversations: AIConversationSummary[];
  canManage: boolean;
  ready: boolean;
  readiness: { chat: boolean; images: boolean };
  runPolicy: { maximumSeconds: number; maximumTokens: number; maximumToolCalls: number };
  activeRun: AIExecutionRun | null;
  npcGeneration: NpcGenerationConfig;
};

export type NpcGenerationConfig = {
  portraitSize: string;
  portraitQuality: string;
  portraitStyle: string;
  allowCampaignContext: boolean;
};

export type AIManagementData = {
  providers: AIManagedProvider[];
  agents: AIManagedAgent[];
  kinds: Array<{ value: string; label: string }>;
  purposes: Array<{ value: string; label: string }>;
  authStrategies: Array<{ value: string; label: string }>;
  roles: Array<{ value: "user" | "master" | "admin"; label: string }>;
  routingModes: Array<{ value: "off" | "auto"; label: string }>;
  tools: AIToolSummary[];
  canManage: boolean;
  canManageCredentials: boolean;
  test?: { ok: boolean; message: string };
  npcGeneration: NpcGenerationConfig;
  portraitQualities: Array<{ value: string; label: string }>;
  imageSizes: Array<{ value: string; label: string }>;
};

/** Il catalogo dei bacini di nomi: si legge senza alcun provider AI configurato. */
export type NameCatalogData = {
  races: NameRaceEntry[];
  genders: Array<{ value: NameGender; label: string }>;
  cultureCount: number;
};

export type NameGender = "maschile" | "femminile" | "casuale";

export type NameRaceEntry = {
  race: string;
  slug: string;
  playable: boolean;
  defaultCulture: string;
  /** Ritratto della razza; stringa vuota quando l'asset non è stato importato. */
  image: string;
  cultures: NameCultureEntry[];
};

/** Le due varianti per sesso di un ritratto o di una clip. */
export type NameMediaPair = { maschile: string; femminile: string };

export type NameCultureEntry = {
  id: number;
  name: string;
  slug: string;
  race: string;
  description: string;
  maleCount: number;
  femaleCount: number;
  surnameCount: number;
  usable: boolean;
  images: NameMediaPair;
  clips: NameMediaPair;
};

export type GeneratedName = {
  name: string;
  firstName: string;
  surname: string;
  gender: Exclude<NameGender, "casuale">;
  requestedGender: NameGender;
  race: string;
  culture: string;
  cultureId: number;
  cultureDescription: string;
  cultureWasRolled: boolean;
  alreadyUsed: boolean;
};

export type NpcDossierDraft = {
  ruolo: string;
  aspetto: string;
  personalita: string;
  voce: string;
  gancio: string;
  ganci: string[];
};

export type NpcDossierResult = {
  name: string;
  draft: NpcDossierDraft;
  description: string;
  subject: Record<string, string>;
  contextUsed: boolean;
  contextTrace: Array<{ name: string; ok: boolean; characters: number }>;
  contextCharacters: number;
  provider: { id: number; name: string; model: string };
  portrait: { size: string; quality: string; style: string };
};

/** Una voce della conversazione nella forma neutra che il backend rimanda indietro. */
export type AIHistoryEntry = {
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: Array<{ id: string; name: string; arguments: Record<string, unknown> }>;
  toolCallId?: string;
  name?: string;
  isError?: boolean;
};

export type AIToolTraceEntry = { name: string; arguments: Record<string, unknown>; isError: boolean };

export type AIChatResult = {
  reply: string;
  history: AIHistoryEntry[];
  toolTrace: AIToolTraceEntry[];
  usage: { inputTokens: number; outputTokens: number };
  stopReason: string;
  runId: string;
  provider: { id: number; name: string; model: string };
  agent: { id: number; name: string };
};

export type AIConversationBubble = {
  id: string;
  role: "user" | "assistant";
  text: string;
  tools: AIToolTraceEntry[];
};

export type AIConversationSummary = {
  id: number;
  title: string;
  agentId: number | null;
  history: AIHistoryEntry[];
  bubbles: AIConversationBubble[];
  updatedAt: string;
};

export type AIExecutionRun = {
  id: string;
  kind: "chat" | "image";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: string;
  cancelRequested: boolean;
  request: { message: string; prompt: string };
  result: AIChatResult | { asset: MediaAsset } | Record<string, never>;
  error: { code?: string; message?: string; field?: string };
  conversation: AIConversationSummary | null;
  budgets: { maximumSeconds: number; maximumTokens: number; maximumToolCalls: number };
};

export type AudioTag = { value: string; label: string };

export type AudioTrack = {
  id: number;
  title: string;
  tags: string[];
  tagLabels: string[];
  url: string;
  originalName: string;
  mimeType: string;
  sizeBytes: number;
  durationSeconds: number | null;
  notes: string;
  createdAt: string | null;
};

export type AudioLibraryData = {
  tracks: AudioTrack[];
  tags: AudioTag[];
  canManage: boolean;
};

export type TravelGrid = {
  orientation: "pointy" | "flat";
  cols: number;
  rows: number;
  scale: number;
  offsetX: number;
  offsetY: number;
  hexSize: number;
  gridOffsetX: number;
  gridOffsetY: number;
};

export type TravelHexEffect = { black: boolean; bw: boolean; blur: number };

export type TravelMarker = {
  id: string;
  hex: string;
  markerType: string;
  tag: string;
  author: string;
  createdAt: string;
};

export type TravelMap = {
  id: number;
  name: string;
  imageUrl: string;
  grid: TravelGrid;
  hexEffects: Record<string, TravelHexEffect>;
  markers: TravelMarker[];
  isDefault: boolean;
  updatedAt: string | null;
};

export type TravelMapsData = {
  campaign: { id: number; name: string } | null;
  maps: TravelMap[];
  canManage: boolean;
  playerName: string;
};
