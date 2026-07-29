export type Axial = { q: number; r: number };
export type CombatResource = {
  key: string; label: string; current: number; maximum: number; spent: number; percent: number; colorToken: string;
};
export type CombatItem = {
  id: number; name: string; icon: string; types: string[]; description: string; imageUrl: string;
  effects: Array<Record<string, unknown>>; isProjectile: boolean; weaponType: string; weaponLength: string;
  weaponPower: string; weaponRules: Record<string, unknown>; actionPointCost: number | null;
  weaponProfile: Record<string, unknown>; weaponTypeBonuses: string[];
};
export type CombatSlot = { id: string; slot: string; label: string; item: CombatItem | null; isLocked: boolean };
export type CombatEffect = {
  scope: string; slot: number | null; id: number; name: string; type: string; description: string;
  icon: string; temporary: boolean; durationTurns: number | null; originName: string;
};
export type CombatAttackButton = {
  id: number; characterId: number | null; characterName: string; name: string; helpText: string;
  modifiers: { attackBonus: number; damageBonus: number; damageTierBonus: number; penetrationFlat: number; penetrationPercent: number };
  public: boolean; active: boolean; keepActiveInCombat: boolean; order: number; canEdit: boolean;
};
/** Conversioni Elder del personaggio usate per il costo degli incantesimi. */
export type SpellEconomy = {
  manaDiscountPerPower: number; actionPointDiscountPerPower: number;
  manaPerEnergy: number; manaPerActionPoint: number;
};
export type CombatActionSettings = { tags: Record<string, string[]>; tagFilters: string[] };
export type CombatCharacter = {
  id: number; name: string; internalName: string; type: string; level: number; races: string[]; portrait: string;
  resources: CombatResource[]; combat: Record<string, number>; resistances: Record<string, number>;
  characteristics: Record<string, number>; criticalThresholds: Record<string, string>;
  equipment: { slots: CombatSlot[]; dualWield: boolean; primaryWeaponSlot: "arma" | "scudo"; primaryWeaponId: number | null; inactiveWeaponId: number | null; weaponState: Record<string, { loaded?: number }> }; quiver: { capacity: number; occupied: number; slots: CombatSlot[] };
  effects: CombatEffect[];
  skills: Array<Record<string, unknown>>; abilities: Array<Record<string, unknown>>; combatButtons: CombatAttackButton[];
  spellEconomy: SpellEconomy; actionSettings: CombatActionSettings;
};
export type MapParticipant = {
  id: number; character: CombatCharacter; anchor: Axial; footprint: Axial[]; tokenColor: string; order: number;
};
export type EditedHex = {
  id: number; q: number; r: number; overlayColor: string; overlayOpacity: number; blocked: boolean; revealed: boolean; fogEffect: boolean; terrainTypeIds: number[];
};
export type CombatModifier = {
  id: number; name: string; scope: string; attackBonus: number; damageBonus: number; penetrationFlat: number;
  penetrationPercent: number; description: string; color: string; enabled: boolean;
};
export type PlannedAction = {
  id: number; characterId: number; actionType: string; name: string; description: string; order: number;
  costs: Record<string, number>; committedAt: string | null; sourceSkillId: number | null; path: Axial[];
};
export type CombatMap = {
  id: number; name: string; mapType: string; mapTypeId: number; imageId: number | null; imageUrl: string;
  orientation: "pointy" | "flat"; rows: number; columns: number; hexSize: number;
  gridOffsetX: number; gridOffsetY: number; imageScale: number; imageOffsetX: number; imageOffsetY: number;
  viewportScale: number; viewportOffsetX: number; viewportOffsetY: number; activeCharacterId: number | null;
  fogEnabled: boolean; fogOpacity: number; viewerCanSeeAll: boolean;
  activeCharacterIds: number[]; participants: MapParticipant[]; hexes: EditedHex[]; modifiers: CombatModifier[];
  plannedActions: PlannedAction[]; events: Array<{ id: number; type: string; message: string; payload: Record<string, unknown>; createdAt: string }>;
  revision?: number; updatedAt: string; isDefault: boolean;
  snapshots: Array<{ id: number; revision: number; label: string; createdAt: string; createdBy: string }>;
};
export type CombatWorkspace = {
  maps: Array<{ id: number; name: string; mapType: string; imageUrl: string; updatedAt: string; revision?: number; isDefault: boolean }>;
  map: CombatMap | null;
  focusCharacter: CombatCharacter | null;
  viewerCharacterId: number | null;
  mapTypes: Array<{ id: number; name: string; slug: string; description: string; orientation: "pointy" | "flat"; rows: number; columns: number }>;
  hexTypes: Array<{ id: number; name: string; slug: string; description: string; movementMultiplier: number; color: string; impassable: boolean }>;
  characterCatalog: Array<{ id: number; name: string; type: string; level: number; races: string[] }>;
  templates: Array<{ id: number; name: string; description: string; imageUrl: string; version: number }>;
  unitCatalog: Array<{
    id: number;
    name: string;
    category: string;
    description: string;
    imageUrl: string;
    generationKind: "animal" | "creature" | "humanoid" | "";
    generationKindLabel: string;
    coreKey: string;
    coreLabel: string;
    hasEquipment: boolean;
    hasSkills: boolean;
    ready: boolean;
  }>;
  effectCatalog: Array<{ id: number; name: string; type: string; description: string; icon: string; durationTurns: number | null }>;
  baseMovementAp: number;
  permissions: { canManageMaps: boolean; canImportCharacters: boolean; canControlCharacters: boolean; canApplyEnemyEffects: boolean };
  paths?: PathResult;
  attackResult?: AttackResult;
  directDamageResult?: DirectDamageResult;
  reloadResult?: { characterId: number; actionPointCost: number; loaded: number };
};
export type PathResult = {
  direct: { path: Axial[]; distance: number; cost: number };
  fastest: { path: Axial[]; distance: number | null; cost: number | null; actionPoints: number | null };
};
export type AttackResult = {
  damageType: string; attackRoll: number; attackTotal: number; defense: number; hit: boolean; margin: number;
  critical: string; criticalMultiplier: number; damageRoll: number; damageBonus: number; rawDamage: number;
  flatReduction: number; effectiveFlatReduction: number; resistanceLevel: number; resistancePercent: number;
  finalDamage: number; applied: boolean; attackerId: number; defenderId: number;
  attackDifference: number; damageMultiplier: number; appliedMultiplier: number; damageTier: number;
  damageFormula: string; attributeBonus: number; damagePercentBonus: number;
  powerName?: string; resourceCosts?: Record<string, number>;
  weaponId?: number | null; weaponName?: string; weaponActionPointCost?: number; dualWieldDiscount?: number;
  attackDistance?: number; rangeAttackPenalty?: number;
  ammunitionType?: string; ammunitionName?: string; loadedBefore?: number | null; loadedAfter?: number | null; magazineSize?: number | null; reloadRequired?: boolean;
  combatButtonIds?: number[]; combatButtonNames?: string[];
};
export type DirectDamageResult = {
  damageType: string; rawDamage: number; flatReduction: number; effectiveFlatReduction: number;
  resistanceLevel: number; resistancePercent: number; penetrationFlat: number; penetrationPercent: number;
  finalDamage: number; attackerId: number; defenderId: number; applied: boolean;
};
