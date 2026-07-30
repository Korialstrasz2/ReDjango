from __future__ import annotations

from typing import Annotated, Any, Literal

from ninja import Field, Schema


class ErrorSchema(Schema):
    code: str
    message: str
    field: str | None = None


class EventSchema(Schema):
    type: str
    message: str


class ItemSpecialReasonSchema(Schema):
    code: str
    label: str
    hint: str = ""


class ItemSchema(Schema):
    id: int
    name: str
    icon: str = ""
    types: list[str] = []
    typeValues: list[str] = []
    description: str = ""
    value: int | None = None
    weight: float | None = None
    rarity: int | None = None
    rarityLabel: str = ""
    lootLevel: str = ""
    region: str = ""
    effects: list[dict[str, Any]] = []
    elderEffects: list[str] = []
    specialRules: str = ""
    imageUrl: str = ""
    archived: bool = False
    special: bool = False
    systemManaged: bool = False
    isProjectile: bool = False
    compatibleEquipmentSlots: list[str] = []
    model: bool | None = None
    temporary: bool | None = None
    order: int | None = None
    regionWeight: float | None = None
    weaponTypeId: int | None = None
    weaponType: str = ""
    weaponLength: str = ""
    weaponPower: str = ""
    weaponRules: dict[str, Any] = {}
    actionPointCost: int | None = None
    weaponProfile: dict[str, Any] = {}
    alchemyProfile: dict[str, Any] = {}
    craftingProfile: dict[str, Any] = {}
    mediaId: int | None = None
    notes: str = ""
    metadata: dict[str, Any] = {}
    specialReasons: list[ItemSpecialReasonSchema] = []


class SlotSchema(Schema):
    id: str
    group: Literal["equipment", "backpack", "quiver", "utility", "campaign"]
    slot: str
    label: str
    slotType: str
    accepts: list[str]
    isExtraSlot: bool
    isLocked: bool
    isMagical: bool
    quantity: int = 1
    stackable: bool = False
    weightless: bool = False
    systemManaged: bool = False
    item: ItemSchema | None = None


class EquipmentSchema(Schema):
    kind: Literal["equipment"]
    label: str
    slots: list[SlotSchema]
    dualWield: bool = False
    primaryWeaponSlot: Literal["arma", "scudo"] = "arma"
    primaryWeaponId: int | None = None
    inactiveWeaponId: int | None = None
    weaponState: dict[str, Any] = {}


class ContainerSchema(Schema):
    kind: Literal["backpack", "quiver", "utility", "campaign"]
    label: str
    capacity: int
    occupied: int
    magicalSlots: int
    weightless: bool = False
    shared: bool = False
    available: bool = True
    slots: list[SlotSchema]


class CoinStorageSchema(Schema):
    coinsPerSlot: int
    requiredSlots: int
    placedSlots: int
    availableSlots: int
    maxCarryableCoins: int
    fits: bool
    coinItemId: int | None = None
    sharedCoins: int = 0
    canTransferToShared: bool = False


class CalculationContributionSchema(Schema):
    key: str
    label: str
    value: int | float


class ResourceSchema(Schema):
    key: Literal["pf", "mana", "energia", "potere"]
    label: str
    current: int
    maximum: int
    spent: int
    percent: float
    colorToken: str
    calculation: list[CalculationContributionSchema]


class StatSchema(Schema):
    key: str
    label: str
    value: int | float
    calculation: list[CalculationContributionSchema]


class CharacterValueGroupSchema(Schema):
    key: str
    label: str
    values: list[StatSchema]


class EncumbranceSchema(Schema):
    equipmentRaw: float
    equipment: float
    equipmentDiscountPercent: float
    backpack: float
    magicalWeightIgnored: float
    quiver: float
    total: float
    loadStep: float
    penalty: int


class EffectOperationSchema(Schema):
    target: str
    operation: str
    value: str
    condition: str = ""


class EffectSchema(Schema):
    scope: Literal["custom", "legacy", "automatic"] = "legacy"
    editable: bool = True
    slot: int | None = None
    id: int
    name: str
    type: str = ""
    description: str = ""
    payload: dict[str, Any] = {}
    durationTurns: int | None = None
    stackingRule: str = ""
    icon: str = ""
    originType: str = ""
    originName: str = ""
    temporary: bool = False
    operations: list[EffectOperationSchema] = []
    order: int = 0


class EffectConfigurationOptionSchema(Schema):
    value: str
    label: str


class EffectIconOptionSchema(EffectConfigurationOptionSchema):
    category: str
    keywords: str
    imageUrl: str = ""


class EffectOperationOptionSchema(EffectConfigurationOptionSchema):
    description: str
    example: str
    timing: str


class EffectFormulaGuideSchema(Schema):
    title: str
    text: str
    example: str
    values: list[str] = []


class EffectPresetSchema(Schema):
    id: int
    name: str
    description: str = ""
    origin: str = ""
    icon: str = "effetto"
    iconUrl: str = ""
    temporary: bool = True
    category: str = ""
    operations: list[EffectOperationSchema] = []


class EffectConfigurationSchema(Schema):
    targets: list[EffectConfigurationOptionSchema]
    presets: list[EffectPresetSchema] = []
    operations: list[EffectOperationOptionSchema]
    operationOrderNote: str
    icons: list[EffectIconOptionSchema]
    formulaGuide: list[EffectFormulaGuideSchema]


class CharacterSummarySchema(Schema):
    id: int
    name: str
    internalName: str
    type: str
    campaignId: int | None = None
    races: list[str]
    race1: str = ""
    race2: str = ""
    race3: str = ""
    level: int
    coins: int
    details: str
    isActive: bool
    primaryTotals: list[StatSchema]


class CharacterAppearanceSchema(Schema):
    characterKey: str
    armorKey: str
    imageUrl: str
    portraitUrl: str = ""
    fallbackUrl: str
    fallbackIsPlaceholder: bool = True
    preferredFilename: str
    isPlaceholder: bool


class NoteSectionsSchema(Schema):
    zaino: str = ""
    furto: str = ""
    combat: str = ""
    competenze: str = ""
    crafting: str = ""
    viaggio: str = ""
    appunti: str = ""
    missioni: str = ""
    background: str = ""


class ReagentValueSchema(Schema):
    key: str
    label: str
    value: float


class ReagentBagSchema(Schema):
    slotMax: int
    occupied: float
    remaining: float
    ingredients: dict[str, Any]
    multipliers: dict[str, Any]
    ingredientRows: list[ReagentValueSchema]
    multiplierRows: list[ReagentValueSchema]


class CharacterSheetSchema(CharacterSummarySchema):
    age: int | None = None
    sex: str = ""
    criticalThresholds: dict[str, str]
    resources: list[ResourceSchema]
    xp: dict[str, int]
    characteristics: list[StatSchema]
    diceModifiers: list[StatSchema]
    combat: list[StatSchema]
    resistances: list[StatSchema]
    valueGroups: list[CharacterValueGroupSchema]
    appearance: CharacterAppearanceSchema
    equipment: EquipmentSchema
    inventory: ContainerSchema
    quiver: ContainerSchema
    utilityContainer: ContainerSchema
    campaignContainer: ContainerSchema
    coinStorage: CoinStorageSchema
    effects: list[EffectSchema]
    skills: list[dict[str, Any]]
    abilities: list[dict[str, Any]]
    competencies: dict[str, Any]
    notes: NoteSectionsSchema
    reagents: ReagentBagSchema
    modifiedStats: dict[str, Any]
    encumbrance: EncumbranceSchema
    permissions: dict[str, bool]


class CharacterSheetDataSchema(Schema):
    character: CharacterSheetSchema
    effectCatalog: list[EffectSchema]
    effectConfiguration: EffectConfigurationSchema
    raceConfiguration: dict[str, Any]
    storageCatalog: list[ItemSchema]


class CharacterSheetEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: CharacterSheetDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class WeaponTypeSchema(Schema):
    id: int
    name: str
    length: str = ""
    power: str = ""
    bonus1: str = ""
    bonus2: str = ""
    rules: dict[str, Any] = {}


class ItemTypeOptionSchema(Schema):
    position: Literal[1, 2, 3, 4]
    value: str
    label: str


class ItemRarityChoiceSchema(Schema):
    value: int
    label: str


class ItemCatalogDataSchema(Schema):
    items: list[ItemSchema]
    typeOptions: list[ItemTypeOptionSchema]
    rarityChoices: list[ItemRarityChoiceSchema]
    effectConfiguration: EffectConfigurationSchema
    weaponTypes: list[WeaponTypeSchema]
    weaponConfiguration: dict[str, Any]
    total: int = 0
    offset: int = 0
    limit: int = 0
    hasMore: bool = False
    regions: list[str] = []
    specialCount: int = 0


class ItemCatalogEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: ItemCatalogDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class CompendiumTypeGroupSchema(Schema):
    position: Literal[1, 2, 3, 4]
    label: str
    note: str = ""
    options: list[ItemTypeOptionSchema] = []


class CompendiumRaritySchema(Schema):
    value: int
    label: str
    note: str = ""
    shopShare: float | None = None


class CompendiumWeaponCategorySchema(Schema):
    id: int | None = None
    key: str
    label: str
    combatMode: str = ""
    combatModeLabel: str = ""
    length: str = ""
    lengthLabel: str = ""
    lengthNote: str = ""
    lengthNotes: list[str] = []
    actionPointCost: int | None = None
    heaviness: str = ""
    heavinessLabel: str = ""
    heavinessNotes: list[str] = []
    power: str = ""
    powerLabel: str = ""
    powerSkill: str = ""
    damageType: str = ""
    damageTypeLabel: str = ""
    damageNotes: list[str] = []
    handling: str = ""
    handlingLabel: str = ""
    costBand: str = ""
    costBandLabel: str = ""
    baseRangeMeters: int | None = None
    ammunitionType: str = ""
    ammunitionLabel: str = ""
    magazineSize: int | None = None
    reloadBaseCost: int | None = None
    reloadPerProjectileCost: int | None = None
    uniquePowers: list[str] = []
    specialRules: list[str] = []
    incomplete: bool = False


class CompendiumAxisOptionSchema(Schema):
    value: str
    label: str
    note: str = ""
    notes: list[str] = []


class CompendiumAxisSchema(Schema):
    label: str
    note: str = ""
    options: list[CompendiumAxisOptionSchema] = []


class CompendiumLabelSchema(Schema):
    value: str
    label: str


class CompendiumOperationSchema(Schema):
    value: str
    label: str
    description: str = ""


class CompendiumGlossaryEntrySchema(Schema):
    key: str
    title: str
    text: str


class ItemCompendiumReferenceDataSchema(Schema):
    typeGroups: list[CompendiumTypeGroupSchema]
    subtypesByCategory: dict[str, list[str]] = {}
    rarityChoices: list[CompendiumRaritySchema]
    regions: list[str] = []
    lootLevels: list[int] = []
    sortOptions: list[CompendiumLabelSchema] = []
    weaponCategories: list[CompendiumWeaponCategorySchema] = []
    weaponAxes: dict[str, CompendiumAxisSchema] = {}
    effectTargets: list[CompendiumLabelSchema] = []
    effectOperations: list[CompendiumOperationSchema] = []
    equipmentSlots: list[CompendiumLabelSchema] = []
    glossary: list[CompendiumGlossaryEntrySchema] = []


class ItemCompendiumReferenceEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: ItemCompendiumReferenceDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class CompendiumOperationEntrySchema(Schema):
    target: str
    operation: str
    value: str = ""
    condition: str = ""


class CompendiumItemSchema(Schema):
    id: int
    name: str
    imageUrl: str = ""
    typeValues: list[str] = []
    description: str = ""
    value: int | None = None
    weight: float | None = None
    rarity: int | None = None
    rarityLabel: str = ""
    lootLevel: str = ""
    lootLevels: list[int] = []
    region: str = ""
    regionWeight: float | None = None
    operations: list[CompendiumOperationEntrySchema] = []
    elderEffects: list[str] = []
    specialRules: str = ""
    weaponCategory: str = ""
    weaponProfile: dict[str, Any] = {}
    actionPointCost: int | None = None
    alchemyProfile: dict[str, Any] = {}
    craftingProfile: dict[str, Any] = {}
    equipmentSlots: list[str] = []


class ItemCompendiumPageDataSchema(Schema):
    items: list[CompendiumItemSchema]
    total: int = 0
    offset: int = 0
    limit: int = 0
    hasMore: bool = False


class ItemCompendiumPageEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: ItemCompendiumPageDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class ManagementEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: dict[str, Any]
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class SlotReferenceSchema(Schema):
    group: Literal["equipment", "backpack", "quiver", "utility", "campaign"]
    slot: str


class SwapPayloadSchema(Schema):
    characterId: int
    source: SlotReferenceSchema
    target: SlotReferenceSchema


class ResourcePayloadSchema(Schema):
    characterId: int
    resource: Literal["pf", "mana", "energia", "potere"]
    current: int


class QuickStatPayloadSchema(Schema):
    characterId: int
    stat: Literal["stanchezza", "modificatore_generale"]
    delta: int = Field(ge=-1, le=1)


class AssignItemPayloadSchema(Schema):
    characterId: int
    target: SlotReferenceSchema
    itemId: int | None = None
    stockKey: str = ""
    quantity: int = Field(default=1, ge=1, le=9999)


class SetQuantityPayloadSchema(Schema):
    characterId: int
    target: SlotReferenceSchema
    quantity: int = Field(ge=0, le=9999)


class SwitchPrimaryWeaponPayloadSchema(Schema):
    characterId: int


class RestPayloadSchema(Schema):
    characterId: int
    fatigueRecovery: int = Field(ge=0, le=5)


class OverviewPayloadSchema(Schema):
    characterId: int
    values: dict[str, Any]


class CharacterCreatePayloadSchema(Schema):
    nome: str = Field(min_length=1, max_length=180)
    razza: str = Field(min_length=1, max_length=120)
    sottorazza: str = Field(default="", max_length=120)
    caratteristicaPreferita: str = Field(min_length=1, max_length=32)
    eta: int | None = Field(default=None, ge=1, le=999)
    sesso: str = Field(default="", max_length=80)
    dettagliPersonaggio: str = Field(default="", max_length=4000)
    background: str = Field(default="", max_length=8000)


class CoinsPayloadSchema(Schema):
    characterId: int
    coins: int = Field(ge=0, le=2_147_483_647)
    expectedCoins: int | None = Field(default=None, ge=0, le=2_147_483_647)
    transferOverflow: bool = False
    expectedSharedCoins: int | None = Field(default=None, ge=0, le=2_147_483_647)


class SharedCoinsPayloadSchema(Schema):
    characterId: int
    coins: int = Field(ge=0, le=2_147_483_647)
    expectedCoins: int | None = Field(default=None, ge=0, le=2_147_483_647)


class ApplyEffectPayloadSchema(Schema):
    characterId: int
    effectId: int


class RemoveEffectPayloadSchema(Schema):
    characterId: int
    effectId: int | None = None
    slot: int | None = Field(default=None, ge=1, le=50)


class CreateEffectPayloadSchema(Schema):
    characterId: int
    values: dict[str, Any]


class UpdateEffectPayloadSchema(Schema):
    characterId: int
    effectId: int | None = None
    legacySlot: int | None = Field(default=None, ge=1, le=50)
    values: dict[str, Any]


class MoveEffectPayloadSchema(Schema):
    characterId: int
    effectId: int
    direction: Literal["up", "down"]


class ItemWritePayloadSchema(Schema):
    itemId: int | None = None
    values: dict[str, Any]


class ArchiveItemPayloadSchema(Schema):
    itemId: int


class CompareItemPayloadSchema(Schema):
    itemId: int | None = None
    identityName: str = ""
    values: dict[str, Any]


class ManagedCharacterUpdatePayloadSchema(Schema):
    characterId: int
    profile: dict[str, Any] = {}
    relations: dict[str, dict[str, Any]] = {}


class ManagedCharacterDeletePayloadSchema(Schema):
    characterId: int
    previewToken: str


class ManagedCharacterAttachPayloadSchema(Schema):
    characterId: int
    kind: str
    recordId: int


class ManagedPlayerCreatePayloadSchema(Schema):
    values: dict[str, Any]


class ManagedPlayerUpdatePayloadSchema(Schema):
    playerId: int
    values: dict[str, Any]


class ManagedPlayerPasswordPayloadSchema(Schema):
    playerId: int
    password: str


class ManagedPlayerCharactersPayloadSchema(Schema):
    playerId: int
    characterIds: list[int] = []


class ManagedSkillStructureWritePayloadSchema(Schema):
    groupId: int | None = None
    familyId: int | None = None
    values: dict[str, Any]


class ManagedSkillStructureStatePayloadSchema(Schema):
    groupId: int | None = None
    familyId: int | None = None
    archived: bool


class DiceHistoryPurgePayloadSchema(Schema):
    olderThanDays: int = 30


class ItemSetSpecialPayloadSchema(Schema):
    itemIds: list[int]
    special: bool


class ItemRecheckSpecialPayloadSchema(Schema):
    itemIds: list[int]


class ManagedSkillStructureReorderPayloadSchema(Schema):
    groups: list[int] = []
    families: list[int] = []


class ManagedSkillStatePayloadSchema(Schema):
    skillId: int
    archived: bool


class ManagedUnitWritePayloadSchema(Schema):
    unitId: int | None = None
    values: dict[str, Any]


class ManagedUnitStatePayloadSchema(Schema):
    unitId: int
    archived: bool


class ManagedUnitPreviewPayloadSchema(Schema):
    unitId: int
    level: int = 1
    variant: str = "standard"


class ManagedVariablesValidatePayloadSchema(Schema):
    values: dict[str, Any]


class ManagedVariablesSavePayloadSchema(ManagedVariablesValidatePayloadSchema):
    previewToken: str


class ManagedThemeSavePayloadSchema(Schema):
    themeId: int
    theme: dict[str, Any]


class ManagedThemeCreatePayloadSchema(Schema):
    theme: dict[str, Any]


class ManagedThemeIdPayloadSchema(Schema):
    themeId: int


class ManagedDamageRulesValidatePayloadSchema(Schema):
    rules: dict[str, Any]


class ManagedDamageRulesSavePayloadSchema(ManagedDamageRulesValidatePayloadSchema):
    previewToken: str


class DiceTextureSchema(Schema):
    sides: int
    imageId: int
    imageUrl: str
    imageName: str = ""
    offsetX: int = 0
    offsetY: int = 0
    scale: int = 100
    rotation: int = 0


class DiceSetSchema(Schema):
    id: int
    slug: str
    name: str
    description: str = ""
    dice: list[int]
    surfaceColor: str
    accentColor: str
    textColor: str
    textures: list[DiceTextureSchema] = []
    untexturedDice: list[int] = []
    isActive: bool
    isDefault: bool
    order: int
    createdAt: str | None = None
    updatedAt: str | None = None


class DiceSetsDataSchema(Schema):
    diceSets: list[DiceSetSchema]
    defaultDiceSetId: int | None = None


class DiceSetsEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: DiceSetsDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class DiceRollSchema(Schema):
    diceSetId: int | None = None
    diceSetName: str = ""
    notation: str
    sides: int
    count: int
    rolls: list[int]
    modifier: int
    subtotal: int
    total: int
    rolledAt: str


class DiceHistoryRollSchema(Schema):
    id: int
    source: Literal["quick", "competence"]
    sourceLabel: str
    playerName: str
    characterId: int | None = None
    characterName: str = ""
    label: str = ""
    notation: str
    rolls: list[int]
    modifier: int
    total: int
    diceSetName: str = ""
    rolledAt: str


class DiceStatisticsRowSchema(Schema):
    name: str
    rolls: int
    dice: int
    averageTotal: float
    averageDie: float


class DiceFaceCountSchema(Schema):
    face: int
    count: int


class DiceStatisticsSchema(Schema):
    byPlayer: list[DiceStatisticsRowSchema] = []
    byDiceSet: list[DiceStatisticsRowSchema] = []
    faceDistribution: list[DiceFaceCountSchema] = []


class DiceHistoryDataSchema(Schema):
    rolls: list[DiceHistoryRollSchema]
    limit: int = 100
    total: int = 0
    offset: int = 0
    hasMore: bool = False
    sources: list[EffectConfigurationOptionSchema] = []
    players: list[str] = []
    statistics: DiceStatisticsSchema | None = None


class DiceHistoryEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: DiceHistoryDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class CharacterNotesDataSchema(Schema):
    characterId: int
    characterName: str
    noteId: int | None = None
    sections: NoteSectionsSchema
    updatedAt: str | None = None


class CharacterNotesEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: CharacterNotesDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class AlchemyStockSchema(Schema):
    key: str
    color: Literal["rosso", "verde", "blu"]
    colorLabel: str
    level: int
    quantity: int


class AlchemyUnclassifiedStockSchema(Schema):
    key: str
    label: str
    quantity: int


class AlchemyBagSchema(Schema):
    id: int | None = None
    capacity: int
    occupied: int
    remaining: int
    stock: list[AlchemyStockSchema]
    unclassified: list[AlchemyUnclassifiedStockSchema] = []


class AlchemyColorMultiplierSchema(Schema):
    key: str
    color: Literal["rosso", "verde", "blu"]
    label: str
    value: float


class AlchemyLevelMultiplierSchema(Schema):
    key: str
    level: int
    label: str
    value: float


class AlchemyMultipliersSchema(Schema):
    colors: list[AlchemyColorMultiplierSchema]
    levels: list[AlchemyLevelMultiplierSchema]


class AlchemyCatalogReagentSchema(Schema):
    id: int
    name: str
    color: Literal["rosso", "verde", "blu"]
    colorLabel: str
    level: int
    stockKey: str


class AlchemyPotionFamilySchema(Schema):
    color: Literal["rosso", "verde", "blu"]
    label: str
    effects: list[str]


class AlchemyThresholdSchema(Schema):
    level: int
    minimumPotency: int


class AlchemyCharacterSchema(Schema):
    id: int
    name: str
    level: int


class AlchemySetSchema(Schema):
    id: int
    name: str
    bonus: float
    bonusPercent: float
    source: Literal["backpack", "utility", "campaign"]
    sourceLabel: str
    shared: bool
    rarity: int | None = None
    rarityLabel: str = ""
    value: int = 0
    description: str = ""


class AlchemyRulesSchema(Schema):
    maxIngredients: int
    defaultSetBonus: float
    defaultSetId: int | None = None
    baseSetBonus: float = 1
    formula: str


class AlchemyCreationDataSchema(Schema):
    character: AlchemyCharacterSchema
    bag: AlchemyBagSchema
    multipliers: AlchemyMultipliersSchema
    sets: list[AlchemySetSchema] = []
    catalog: list[AlchemyCatalogReagentSchema]
    potionFamilies: list[AlchemyPotionFamilySchema]
    thresholds: list[AlchemyThresholdSchema]
    notes: str = ""
    rules: AlchemyRulesSchema


class AlchemyCreationEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: AlchemyCreationDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class AlchemyBrewIngredientSchema(Schema):
    color: Literal["rosso", "verde", "blu"]
    level: int
    stockKey: str
    value: float


class AlchemyBrewResultSchema(Schema):
    potionColor: Literal["rosso", "verde", "blu"]
    potionColorLabel: str
    effect: str
    ingredients: list[AlchemyBrewIngredientSchema]
    levelTotal: float
    setBonus: float
    setId: int | None = None
    setName: str = ""
    abilityBonus: float
    potency: float
    potionLevel: int
    potionLevelLabel: str
    formula: str
    consumed: dict[str, int] = {}


class CompetenceThresholdSchema(Schema):
    score: int
    text: str


class CompetenceSourceSchema(Schema):
    source: str
    sourceType: Literal["equipment", "effect", "skill"]
    operation: str
    value: Any
    delta: int


class CompetenceMasteryFeatureSchema(Schema):
    rank: int
    key: str
    title: str
    description: str
    unlocked: bool | None = None


class CompetenceEntrySchema(Schema):
    id: int
    key: str
    name: str
    description: str
    descriptionIntro: str = ""
    thresholds: list[CompetenceThresholdSchema] = []
    attribute: str = ""
    category: str = ""
    iconUrl: str
    baseRank: int
    masteryRank: int
    manualExtra: int
    linkedExtra: int
    effectiveExtra: int
    sourceBreakdown: list[CompetenceSourceSchema] = []
    rollModifier: int
    dieSides: int
    nextBaseCost: int | None = None
    nextMasteryCost: int | None = None
    masteryFeatures: list[CompetenceMasteryFeatureSchema] = []
    dailyRerollsRemaining: int = 0


class CompetenceCharacterContextSchema(Schema):
    id: int
    name: str
    level: int
    xpAvailable: int
    xpSpent: int
    energyCurrent: int
    energyMaximum: int


class CompetenceRollSchema(Schema):
    id: int
    competenceKey: str
    competenceName: str
    technique: Literal["standard", "focus", "amplify"]
    dieSides: int
    baseRank: int
    manualExtra: int
    linkedExtra: int
    modifier: int
    focusBonus: int
    multiplier: int
    energySpent: int
    rolls: list[dict[str, Any]]
    total: int
    rerollsUsed: int
    rerollsRemaining: int
    canReroll: bool
    rolledAt: str | None = None


class CompetenceCatalogDataSchema(Schema):
    character: CompetenceCharacterContextSchema
    competencies: list[CompetenceEntrySchema]
    masteryFeatures: list[CompetenceMasteryFeatureSchema]
    recentRolls: list[CompetenceRollSchema]
    backgrounds: list[str]
    effectTargetPrefix: str


class CompetenceCatalogEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: CompetenceCatalogDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class SkillFamilySchema(Schema):
    id: int
    name: str
    groupId: int | None = None
    group: str = ""
    groupSlug: str = ""
    order: int = 0
    isClass: bool = False
    isReligion: bool = False
    isPerk: bool = False
    notes: str = ""
    additionalNotes: str = ""
    imageUrl: str = ""
    skillCount: int = 0
    selected: bool = False


class SkillFamilyGroupSchema(Schema):
    key: str
    name: str
    order: int = 0
    familyCount: int = 0
    skillCount: int = 0
    selected: bool = False


class SkillUnlockStateSchema(Schema):
    owned: bool
    canUnlock: bool
    blockedReasons: list[str] = []
    prerequisiteIds: list[int] = []
    missingPrerequisiteIds: list[int] = []
    prerequisitesBypassed: bool = False
    allowedXpPools: list[str] = []
    acceptedPassiveIds: list[str] = []
    spentXp: dict[str, int] = {}
    note: str = ""
    unlockedAt: str | None = None


class SkillPricingSchema(Schema):
    baseCost: int = 0
    calculatedCost: int = 0
    calculatedBeforeOwnedSkillDiscount: int = 0
    levelSurcharge: int = 0
    spentXpInCategory: int = 0
    surchargeDiscountPercent: float = 0
    ownedSkillDiscount: int = 0
    ownedSkillDiscountSources: list[str] = []


class SpellDefinitionSchema(Schema):
    id: int
    tier: str
    tierLabel: str
    range: str = ""
    effectUnit: str
    baseMana: float = 0
    effectPerMana: float
    minimumMana: float = 0
    fixedCosts: dict[str, int] = {}
    rounding: str
    roundingLabel: str
    legacyFormula: str = ""
    costNotes: str = ""
    formula: str
    costSummary: str = ""
    combatConfiguration: dict[str, Any] = {}


class SkillSchema(Schema):
    id: int
    slug: str
    number: int
    name: str
    description: str = ""
    familyId: int
    familyName: str
    familyGroup: str
    familyOrder: int = 0
    magic: bool = False
    baseXpCost: int = 0
    xpCost: int = 0
    pricing: SkillPricingSchema
    xpType: str
    xpTypeLabel: str
    rulesCost: str = ""
    requirementsText: str = ""
    spell: SpellDefinitionSchema | None = None
    profileTags: dict[str, Any] = {}
    profileNotes: str = ""
    passiveEffects: list[dict[str, Any]] = []
    activeReminders: list[dict[str, Any]] = []
    icon: str = "runa"
    notes: str = ""
    metadata: dict[str, Any] = {}
    archived: bool = False
    unlock: SkillUnlockStateSchema


class SkillCharacterContextSchema(Schema):
    id: int
    name: str
    level: int
    xp: dict[str, int]
    competenceXp: int = 0


class CombatButtonModifiersSchema(Schema):
    attackBonus: int = 0
    damageBonus: int = 0
    damageTierBonus: int = 0
    penetrationFlat: int = 0
    penetrationPercent: int = 0


class CombatButtonSchema(Schema):
    id: int
    characterId: int | None = None
    characterName: str
    name: str
    helpText: str = ""
    modifiers: CombatButtonModifiersSchema
    public: bool = False
    active: bool = True
    keepActiveInCombat: bool = False
    order: int = 0
    canEdit: bool = False


class CombatButtonConfigurationSchema(Schema):
    limit: int = 12
    availableSlots: int = 0
    own: list[CombatButtonSchema] = []
    public: list[CombatButtonSchema] = []


class SkillCatalogDataSchema(Schema):
    groups: list[SkillFamilyGroupSchema]
    families: list[SkillFamilySchema]
    skills: list[SkillSchema]
    skillOptions: list[dict[str, Any]] = []
    selectedFamilyId: int | None = None
    selectedGroup: str = ""
    query: str = ""
    character: SkillCharacterContextSchema | None = None
    activeReminders: list[dict[str, Any]] = []
    combatButtons: CombatButtonConfigurationSchema
    characterAnalysis: dict[str, Any] = {}
    effectConfiguration: EffectConfigurationSchema
    permissions: dict[str, bool]


class SkillCatalogEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: SkillCatalogDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class SkillUnlockPreviewSchema(Schema):
    skill: SkillSchema
    cost: int
    pricing: SkillPricingSchema
    xp: dict[str, int]
    allowedXpPools: list[str]
    missingPrerequisiteIds: list[int] = []
    passiveConfirmations: list[dict[str, Any]] = []
    canConfirm: bool
    prerequisitesBypassed: bool = False
    blockedReasons: list[str] = []


class SpellCastPreviewSchema(Schema):
    skillId: int
    skillName: str
    tier: str
    tierLabel: str
    requestedEffect: float
    projectedEffect: float
    effectUnit: str
    fixedMana: float = 0
    variableMana: float = 0
    requiredManaBeforeDiscounts: int
    powerConsidered: float
    fixedCosts: dict[str, int] = {}
    resourceOptions: dict[str, int | None]
    costs: dict[str, int] = {}
    costSummary: str = ""
    spendsResources: bool = False
    combatReady: bool = False
    note: str


class DiceRollPayloadSchema(Schema):
    sides: int
    count: int = 1
    modifier: int = 0
    diceSetId: int | None = None
    characterId: int | None = None


class DiceSetCreatePayloadSchema(Schema):
    values: dict[str, Any]


class DiceSetUpdatePayloadSchema(Schema):
    diceSetId: int
    values: dict[str, Any]


class DiceSetArchivePayloadSchema(Schema):
    diceSetId: int


class NoteUpdatePayloadSchema(Schema):
    characterId: int
    section: str
    content: str


class CampaignSelectPayloadSchema(Schema):
    campaignId: int


class CampaignNotesUpdatePayloadSchema(Schema):
    campaignId: int
    content: str


class CampaignClockUpdatePayloadSchema(Schema):
    campaignId: int
    field: Literal["ora", "giorno"]
    direction: Literal["increase", "decrease"]


class CampaignWeatherRerollPayloadSchema(Schema):
    campaignId: int


class AlchemyIngredientSelectionSchema(Schema):
    color: Literal["rosso", "verde", "blu"]
    level: int


class AlchemyBrewPayloadSchema(Schema):
    characterId: int
    ingredients: list[AlchemyIngredientSelectionSchema]
    potionColor: Literal["rosso", "verde", "blu"]
    effect: str
    setItemId: int | None = None


class AlchemyExtractPayloadSchema(Schema):
    characterId: int


class SkillPreviewPayloadSchema(Schema):
    characterId: int
    skillId: int


class SpellPreviewPayloadSchema(Schema):
    characterId: int
    skillId: int
    effect: float
    power: float = 0


class SkillUnlockPayloadSchema(Schema):
    characterId: int
    skillId: int
    spend: dict[str, int]
    acceptedPassiveIds: list[str] = []
    note: str = ""


class SkillXpUpdatePayloadSchema(Schema):
    characterId: int
    xp: dict[str, int]


class SkillCharacterActionsPayloadSchema(Schema):
    characterId: int
    actions: list[dict[str, Any]] = []


class CombatButtonWritePayloadSchema(Schema):
    characterId: int
    buttonId: int | None = None
    values: dict[str, Any]


class CombatButtonDeletePayloadSchema(Schema):
    characterId: int
    buttonId: int


class SkillWritePayloadSchema(Schema):
    skillId: int | None = None
    values: dict[str, Any]


class SkillArchivePayloadSchema(Schema):
    skillId: int


class SkillReorderPayloadSchema(Schema):
    familyId: int
    skillIds: list[int]


class SkillDeletePayloadSchema(Schema):
    skillId: int
    confirmation: str


class CompetenceUpgradePayloadSchema(Schema):
    characterId: int
    competenceKey: str
    track: Literal["base", "mastery"]
    targetRank: int


class CompetenceExtraPayloadSchema(Schema):
    characterId: int
    competenceKey: str
    extra: int


class CompetenceRollPayloadSchema(Schema):
    characterId: int
    competenceKey: str
    technique: Literal["standard", "focus", "amplify"] = "standard"
    diceSetId: int | None = None


class CompetenceRerollPayloadSchema(Schema):
    characterId: int
    rollId: int


class MarketShopSavePayloadSchema(Schema):
    values: dict[str, Any]


class MarketGenerationPayloadSchema(Schema):
    values: dict[str, Any] = {}
    shopId: int | None = None
    seed: str = ""


class MarketBatchPayloadSchema(Schema):
    values: dict[str, Any] = {}
    confirm: bool = False


class MarketStatePayloadSchema(Schema):
    shopId: int
    archived: bool


class MarketProfileAssignmentPayloadSchema(Schema):
    shopId: int
    profileKey: str = ""


class MarketSettingsPayloadSchema(Schema):
    values: dict[str, Any]


class MarketQuotePayloadSchema(Schema):
    shopId: int
    lines: list[dict[str, Any]]
    negotiationPercent: int = 0


class MarketPurchasePayloadSchema(MarketQuotePayloadSchema):
    characterId: int
    stockRevision: int


class BackupConfigurationSchema(Schema):
    enabled: bool
    onStartup: bool
    intervalMinutes: int = Field(ge=5, le=120)
    retentionCount: int = Field(ge=1, le=100)


class BackupConfigurationPayloadSchema(Schema):
    configuration: BackupConfigurationSchema


class BackupCreatePayloadSchema(Schema):
    label: str = Field(default="", max_length=120)


class BackupIdPayloadSchema(Schema):
    backupId: str = Field(min_length=1, max_length=120)


class BackupInspectPayloadSchema(BackupIdPayloadSchema):
    characterId: int | None = Field(default=None, ge=1)


class ActionBaseSchema(Schema):
    requestId: str
    context: dict[str, Any] = {}
    meta: dict[str, Any] = {}


class SwapActionSchema(ActionBaseSchema):
    action: Literal["inventory.swapItems"]
    payload: SwapPayloadSchema


class ResourceActionSchema(ActionBaseSchema):
    action: Literal["character.updateResource"]
    payload: ResourcePayloadSchema


class QuickStatActionSchema(ActionBaseSchema):
    action: Literal["character.adjustQuickStat"]
    payload: QuickStatPayloadSchema


class AssignItemActionSchema(ActionBaseSchema):
    action: Literal["inventory.assignItem"]
    payload: AssignItemPayloadSchema


class SetQuantityActionSchema(ActionBaseSchema):
    action: Literal["inventory.setQuantity"]
    payload: SetQuantityPayloadSchema


class SwitchPrimaryWeaponActionSchema(ActionBaseSchema):
    action: Literal["equipment.switchPrimaryWeapon"]
    payload: SwitchPrimaryWeaponPayloadSchema


class RestActionSchema(ActionBaseSchema):
    action: Literal["character.rest"]
    payload: RestPayloadSchema


class OverviewActionSchema(ActionBaseSchema):
    action: Literal["character.updateOverview"]
    payload: OverviewPayloadSchema


class CharacterCreateActionSchema(ActionBaseSchema):
    action: Literal["characters.create"]
    payload: CharacterCreatePayloadSchema


class CoinsActionSchema(ActionBaseSchema):
    action: Literal["character.updateCoins"]
    payload: CoinsPayloadSchema


class SharedCoinsActionSchema(ActionBaseSchema):
    action: Literal["campaign.updateSharedCoins"]
    payload: SharedCoinsPayloadSchema


class ApplyEffectActionSchema(ActionBaseSchema):
    action: Literal["effects.apply"]
    payload: ApplyEffectPayloadSchema


class RemoveEffectActionSchema(ActionBaseSchema):
    action: Literal["effects.remove"]
    payload: RemoveEffectPayloadSchema


class CreateEffectActionSchema(ActionBaseSchema):
    action: Literal["effects.create"]
    payload: CreateEffectPayloadSchema


class UpdateEffectActionSchema(ActionBaseSchema):
    action: Literal["effects.update"]
    payload: UpdateEffectPayloadSchema


class MoveEffectActionSchema(ActionBaseSchema):
    action: Literal["effects.move"]
    payload: MoveEffectPayloadSchema


class CreateItemActionSchema(ActionBaseSchema):
    action: Literal["items.create"]
    payload: ItemWritePayloadSchema


class UpdateItemActionSchema(ActionBaseSchema):
    action: Literal["items.update"]
    payload: ItemWritePayloadSchema


class ArchiveItemActionSchema(ActionBaseSchema):
    action: Literal["items.archive"]
    payload: ArchiveItemPayloadSchema


class CompareItemActionSchema(ActionBaseSchema):
    action: Literal["items.compareSave"]
    payload: CompareItemPayloadSchema


class ManagedCharacterUpdateActionSchema(ActionBaseSchema):
    action: Literal["management.characters.update"]
    payload: ManagedCharacterUpdatePayloadSchema


class ManagedCharacterDeleteActionSchema(ActionBaseSchema):
    action: Literal["management.characters.delete"]
    payload: ManagedCharacterDeletePayloadSchema


class ManagedCharacterAttachActionSchema(ActionBaseSchema):
    action: Literal["management.characters.attach"]
    payload: ManagedCharacterAttachPayloadSchema


class ManagedPlayerCreateActionSchema(ActionBaseSchema):
    action: Literal["management.players.create"]
    payload: ManagedPlayerCreatePayloadSchema


class ManagedPlayerUpdateActionSchema(ActionBaseSchema):
    action: Literal["management.players.update"]
    payload: ManagedPlayerUpdatePayloadSchema


class ManagedPlayerPasswordActionSchema(ActionBaseSchema):
    action: Literal["management.players.setPassword"]
    payload: ManagedPlayerPasswordPayloadSchema


class ManagedPlayerCharactersActionSchema(ActionBaseSchema):
    action: Literal["management.players.assignCharacters"]
    payload: ManagedPlayerCharactersPayloadSchema


class ManagedSkillGroupSaveActionSchema(ActionBaseSchema):
    action: Literal["management.skills.group.save"]
    payload: ManagedSkillStructureWritePayloadSchema


class ManagedSkillGroupStateActionSchema(ActionBaseSchema):
    action: Literal["management.skills.group.state"]
    payload: ManagedSkillStructureStatePayloadSchema


class ManagedSkillFamilySaveActionSchema(ActionBaseSchema):
    action: Literal["management.skills.family.save"]
    payload: ManagedSkillStructureWritePayloadSchema


class ManagedSkillFamilyStateActionSchema(ActionBaseSchema):
    action: Literal["management.skills.family.state"]
    payload: ManagedSkillStructureStatePayloadSchema


class DiceSetDuplicateActionSchema(ActionBaseSchema):
    action: Literal["diceSets.duplicate"]
    payload: DiceSetArchivePayloadSchema


class DiceHistoryPurgeActionSchema(ActionBaseSchema):
    action: Literal["diceHistory.purge"]
    payload: DiceHistoryPurgePayloadSchema


class ItemSetSpecialActionSchema(ActionBaseSchema):
    action: Literal["items.setSpecial"]
    payload: ItemSetSpecialPayloadSchema


class ItemRecheckSpecialActionSchema(ActionBaseSchema):
    action: Literal["items.recheckSpecial"]
    payload: ItemRecheckSpecialPayloadSchema


class ManagedSkillStructureReorderActionSchema(ActionBaseSchema):
    action: Literal["management.skills.structure.reorder"]
    payload: ManagedSkillStructureReorderPayloadSchema


class ManagedSkillStateActionSchema(ActionBaseSchema):
    action: Literal["management.skills.skill.state"]
    payload: ManagedSkillStatePayloadSchema


class ManagedUnitSaveActionSchema(ActionBaseSchema):
    action: Literal["management.units.save"]
    payload: ManagedUnitWritePayloadSchema


class ManagedUnitStateActionSchema(ActionBaseSchema):
    action: Literal["management.units.state"]
    payload: ManagedUnitStatePayloadSchema


class ManagedUnitPreviewActionSchema(ActionBaseSchema):
    action: Literal["management.units.preview"]
    payload: ManagedUnitPreviewPayloadSchema


class ManagedVariablesValidateActionSchema(ActionBaseSchema):
    action: Literal["management.variables.validate"]
    payload: ManagedVariablesValidatePayloadSchema


class ManagedVariablesSaveActionSchema(ActionBaseSchema):
    action: Literal["management.variables.save"]
    payload: ManagedVariablesSavePayloadSchema


class ManagedBackupSettingsActionSchema(ActionBaseSchema):
    action: Literal["management.backups.saveSettings"]
    payload: BackupConfigurationPayloadSchema


class ManagedBackupCreateActionSchema(ActionBaseSchema):
    action: Literal["management.backups.create"]
    payload: BackupCreatePayloadSchema


class ManagedBackupDeleteActionSchema(ActionBaseSchema):
    action: Literal["management.backups.delete"]
    payload: BackupIdPayloadSchema


class ManagedBackupInspectActionSchema(ActionBaseSchema):
    action: Literal["management.backups.inspect"]
    payload: BackupInspectPayloadSchema


class ManagedThemeSaveActionSchema(ActionBaseSchema):
    action: Literal["management.themes.save"]
    payload: ManagedThemeSavePayloadSchema


class ManagedThemeCreateActionSchema(ActionBaseSchema):
    action: Literal["management.themes.create"]
    payload: ManagedThemeCreatePayloadSchema


class ManagedThemeSetDefaultActionSchema(ActionBaseSchema):
    action: Literal["management.themes.setDefault"]
    payload: ManagedThemeIdPayloadSchema


class ManagedThemeArchiveActionSchema(ActionBaseSchema):
    action: Literal["management.themes.archive"]
    payload: ManagedThemeIdPayloadSchema


class ManagedDamageRulesValidateActionSchema(ActionBaseSchema):
    action: Literal["management.damageRules.validate"]
    payload: ManagedDamageRulesValidatePayloadSchema


class ManagedDamageRulesSaveActionSchema(ActionBaseSchema):
    action: Literal["management.damageRules.save"]
    payload: ManagedDamageRulesSavePayloadSchema


class DiceRollActionSchema(ActionBaseSchema):
    action: Literal["dice.roll"]
    payload: DiceRollPayloadSchema


class DiceSetCreateActionSchema(ActionBaseSchema):
    action: Literal["diceSets.create"]
    payload: DiceSetCreatePayloadSchema


class DiceSetUpdateActionSchema(ActionBaseSchema):
    action: Literal["diceSets.update"]
    payload: DiceSetUpdatePayloadSchema


class DiceSetArchiveActionSchema(ActionBaseSchema):
    action: Literal["diceSets.archive"]
    payload: DiceSetArchivePayloadSchema


class NoteUpdateActionSchema(ActionBaseSchema):
    action: Literal["notes.updateSection"]
    payload: NoteUpdatePayloadSchema


class CampaignSelectActionSchema(ActionBaseSchema):
    action: Literal["campaign.select"]
    payload: CampaignSelectPayloadSchema


class CampaignNotesUpdateActionSchema(ActionBaseSchema):
    action: Literal["campaign.notes.update"]
    payload: CampaignNotesUpdatePayloadSchema


class CampaignClockUpdateActionSchema(ActionBaseSchema):
    action: Literal["campaign.clock.update"]
    payload: CampaignClockUpdatePayloadSchema


class CampaignWeatherRerollActionSchema(ActionBaseSchema):
    action: Literal["campaign.weather.reroll"]
    payload: CampaignWeatherRerollPayloadSchema


class AlchemyBrewActionSchema(ActionBaseSchema):
    action: Literal["alchemy.brew"]
    payload: AlchemyBrewPayloadSchema


class AlchemyExtractActionSchema(ActionBaseSchema):
    action: Literal["alchemy.extract"]
    payload: AlchemyExtractPayloadSchema


class SkillPreviewActionSchema(ActionBaseSchema):
    action: Literal["skills.previewUnlock"]
    payload: SkillPreviewPayloadSchema


class SkillUnlockActionSchema(ActionBaseSchema):
    action: Literal["skills.unlock"]
    payload: SkillUnlockPayloadSchema


class SkillXpUpdateActionSchema(ActionBaseSchema):
    action: Literal["skills.updateCharacterXp"]
    payload: SkillXpUpdatePayloadSchema


class SpellPreviewActionSchema(ActionBaseSchema):
    action: Literal["skills.previewSpell"]
    payload: SpellPreviewPayloadSchema


class SkillConfigureCharacterActionsActionSchema(ActionBaseSchema):
    action: Literal["skills.configureCharacterActions"]
    payload: SkillCharacterActionsPayloadSchema


class CombatButtonCreateActionSchema(ActionBaseSchema):
    action: Literal["combatButtons.create"]
    payload: CombatButtonWritePayloadSchema


class CombatButtonUpdateActionSchema(ActionBaseSchema):
    action: Literal["combatButtons.update"]
    payload: CombatButtonWritePayloadSchema


class CombatButtonDeleteActionSchema(ActionBaseSchema):
    action: Literal["combatButtons.delete"]
    payload: CombatButtonDeletePayloadSchema


class SkillCreateActionSchema(ActionBaseSchema):
    action: Literal["skills.create"]
    payload: SkillWritePayloadSchema


class SkillUpdateActionSchema(ActionBaseSchema):
    action: Literal["skills.update"]
    payload: SkillWritePayloadSchema


class SkillArchiveActionSchema(ActionBaseSchema):
    action: Literal["skills.archive"]
    payload: SkillArchivePayloadSchema


class SkillReorderActionSchema(ActionBaseSchema):
    action: Literal["skills.reorder"]
    payload: SkillReorderPayloadSchema


class SkillDeleteActionSchema(ActionBaseSchema):
    action: Literal["skills.delete"]
    payload: SkillDeletePayloadSchema


class CompetenceUpgradeActionSchema(ActionBaseSchema):
    action: Literal["competencies.upgrade"]
    payload: CompetenceUpgradePayloadSchema


class CompetenceExtraActionSchema(ActionBaseSchema):
    action: Literal["competencies.updateExtra"]
    payload: CompetenceExtraPayloadSchema


class CompetenceRollActionSchema(ActionBaseSchema):
    action: Literal["competencies.roll"]
    payload: CompetenceRollPayloadSchema


class CompetenceRerollActionSchema(ActionBaseSchema):
    action: Literal["competencies.reroll"]
    payload: CompetenceRerollPayloadSchema


class MarketShopSaveActionSchema(ActionBaseSchema):
    action: Literal["market.shop.save"]
    payload: MarketShopSavePayloadSchema


class MarketShopPreviewActionSchema(ActionBaseSchema):
    action: Literal["market.shop.preview"]
    payload: MarketGenerationPayloadSchema


class MarketShopRegenerateActionSchema(ActionBaseSchema):
    action: Literal["market.shop.regenerate"]
    payload: MarketGenerationPayloadSchema


class MarketShopBatchActionSchema(ActionBaseSchema):
    action: Literal["market.shop.batchCreate"]
    payload: MarketBatchPayloadSchema


class MarketShopStateActionSchema(ActionBaseSchema):
    action: Literal["market.shop.state"]
    payload: MarketStatePayloadSchema


class MarketProfileAssignmentActionSchema(ActionBaseSchema):
    action: Literal["market.shop.profileAssign"]
    payload: MarketProfileAssignmentPayloadSchema


class MarketSettingsSaveActionSchema(ActionBaseSchema):
    action: Literal["market.settings.save"]
    payload: MarketSettingsPayloadSchema


class MarketQuoteActionSchema(ActionBaseSchema):
    action: Literal["market.quote"]
    payload: MarketQuotePayloadSchema


class MarketPurchaseActionSchema(ActionBaseSchema):
    action: Literal["market.purchase"]
    payload: MarketPurchasePayloadSchema


class LoreValuesPayloadSchema(Schema):
    values: dict[str, Any]


class LoreIdPayloadSchema(Schema):
    id: int


class LoreRelationsPayloadSchema(Schema):
    relations: list[dict[str, Any]] = []


class LoreFactionSaveActionSchema(ActionBaseSchema):
    action: Literal["lore.faction.save"]
    payload: LoreValuesPayloadSchema


class LoreFactionDeleteActionSchema(ActionBaseSchema):
    action: Literal["lore.faction.delete"]
    payload: LoreIdPayloadSchema


class LoreRelationsSaveActionSchema(ActionBaseSchema):
    action: Literal["lore.relations.save"]
    payload: LoreRelationsPayloadSchema


class LoreEventRecordActionSchema(ActionBaseSchema):
    action: Literal["lore.event.record"]
    payload: LoreValuesPayloadSchema


class LoreEventUpdateActionSchema(ActionBaseSchema):
    action: Literal["lore.event.update"]
    payload: LoreValuesPayloadSchema


class LoreEventDeleteActionSchema(ActionBaseSchema):
    action: Literal["lore.event.delete"]
    payload: LoreIdPayloadSchema


class LoreCharacterSaveActionSchema(ActionBaseSchema):
    action: Literal["lore.character.save"]
    payload: LoreValuesPayloadSchema


class LoreCharacterDeleteActionSchema(ActionBaseSchema):
    action: Literal["lore.character.delete"]
    payload: LoreIdPayloadSchema


class LoreTimelineValuesSchema(Schema):
    id: int | None = None
    title: str
    year: int
    description: str = ""
    imageId: int | None = None
    tags: list[str] = []


class LoreTimelineSavePayloadSchema(Schema):
    values: LoreTimelineValuesSchema


class LoreTimelineSaveActionSchema(ActionBaseSchema):
    action: Literal["lore.timeline.save"]
    payload: LoreTimelineSavePayloadSchema


class LoreTimelineArchiveActionSchema(ActionBaseSchema):
    action: Literal["lore.timeline.archive"]
    payload: LoreIdPayloadSchema


class NameGeneratePayloadSchema(Schema):
    """`race` basta alla modalità rapida; `cultureId` serve solo quando il Master
    sceglie una cultura diversa da quella omonima della razza."""

    race: str = ""
    cultureId: int | None = None
    gender: str = "casuale"


class NameGenerateActionSchema(ActionBaseSchema):
    action: Literal["names.generate"]
    payload: NameGeneratePayloadSchema


ActionEnvelopeSchema = Annotated[
    SwapActionSchema
    | AssignItemActionSchema
    | SetQuantityActionSchema
    | SwitchPrimaryWeaponActionSchema
    | ResourceActionSchema
    | QuickStatActionSchema
    | RestActionSchema
    | OverviewActionSchema
    | CharacterCreateActionSchema
    | CoinsActionSchema
    | SharedCoinsActionSchema
    | ApplyEffectActionSchema
    | RemoveEffectActionSchema
    | CreateEffectActionSchema
    | UpdateEffectActionSchema
    | MoveEffectActionSchema
    | CreateItemActionSchema
    | UpdateItemActionSchema
    | ArchiveItemActionSchema
    | CompareItemActionSchema
    | ManagedCharacterUpdateActionSchema
    | ManagedCharacterDeleteActionSchema
    | ManagedCharacterAttachActionSchema
    | ManagedPlayerCreateActionSchema
    | ManagedPlayerUpdateActionSchema
    | ManagedPlayerPasswordActionSchema
    | ManagedPlayerCharactersActionSchema
    | ManagedSkillGroupSaveActionSchema
    | ManagedSkillGroupStateActionSchema
    | ManagedSkillFamilySaveActionSchema
    | ManagedSkillFamilyStateActionSchema
    | ItemSetSpecialActionSchema
    | ItemRecheckSpecialActionSchema
    | DiceSetDuplicateActionSchema
    | DiceHistoryPurgeActionSchema
    | ManagedSkillStructureReorderActionSchema
    | ManagedSkillStateActionSchema
    | ManagedUnitSaveActionSchema
    | ManagedUnitStateActionSchema
    | ManagedUnitPreviewActionSchema
    | ManagedVariablesValidateActionSchema
    | ManagedVariablesSaveActionSchema
    | ManagedBackupSettingsActionSchema
    | ManagedBackupCreateActionSchema
    | ManagedBackupDeleteActionSchema
    | ManagedBackupInspectActionSchema
    | ManagedThemeSaveActionSchema
    | ManagedThemeCreateActionSchema
    | ManagedThemeSetDefaultActionSchema
    | ManagedThemeArchiveActionSchema
    | ManagedDamageRulesValidateActionSchema
    | ManagedDamageRulesSaveActionSchema
    | DiceRollActionSchema
    | DiceSetCreateActionSchema
    | DiceSetUpdateActionSchema
    | DiceSetArchiveActionSchema
    | NoteUpdateActionSchema
    | CampaignSelectActionSchema
    | CampaignNotesUpdateActionSchema
    | CampaignClockUpdateActionSchema
    | CampaignWeatherRerollActionSchema
    | AlchemyBrewActionSchema
    | AlchemyExtractActionSchema
    | SkillPreviewActionSchema
    | SkillUnlockActionSchema
    | SkillXpUpdateActionSchema
    | SpellPreviewActionSchema
    | SkillConfigureCharacterActionsActionSchema
    | CombatButtonCreateActionSchema
    | CombatButtonUpdateActionSchema
    | CombatButtonDeleteActionSchema
    | SkillCreateActionSchema
    | SkillUpdateActionSchema
    | SkillArchiveActionSchema
    | SkillReorderActionSchema
    | SkillDeleteActionSchema
    | CompetenceUpgradeActionSchema
    | CompetenceExtraActionSchema
    | CompetenceRollActionSchema
    | CompetenceRerollActionSchema
    | MarketShopSaveActionSchema
    | MarketShopPreviewActionSchema
    | MarketShopRegenerateActionSchema
    | MarketShopBatchActionSchema
    | MarketShopStateActionSchema
    | MarketProfileAssignmentActionSchema
    | MarketSettingsSaveActionSchema
    | MarketQuoteActionSchema
    | MarketPurchaseActionSchema
    | LoreFactionSaveActionSchema
    | LoreFactionDeleteActionSchema
    | LoreRelationsSaveActionSchema
    | LoreEventRecordActionSchema
    | LoreEventUpdateActionSchema
    | LoreEventDeleteActionSchema
    | LoreCharacterSaveActionSchema
    | LoreCharacterDeleteActionSchema
    | LoreTimelineSaveActionSchema
    | LoreTimelineArchiveActionSchema
    | NameGenerateActionSchema,
    Field(discriminator="action"),
]


class ActionDataSchema(Schema):
    character: CharacterSheetSchema | None = None
    item: ItemSchema | None = None
    catalog: ItemCatalogDataSchema | None = None
    diceSets: DiceSetsDataSchema | None = None
    diceRoll: DiceRollSchema | None = None
    notes: CharacterNotesDataSchema | None = None
    campaigns: dict[str, Any] | None = None
    weatherReminder: bool | None = None
    management: dict[str, Any] | None = None
    skills: SkillCatalogDataSchema | None = None
    skill: SkillSchema | None = None
    skillOrder: dict[int, int] | None = None
    skillPreview: SkillUnlockPreviewSchema | None = None
    spellPreview: SpellCastPreviewSchema | None = None
    competencies: CompetenceCatalogDataSchema | None = None
    competenceRoll: CompetenceRollSchema | None = None
    creation: AlchemyCreationDataSchema | None = None
    alchemyResult: AlchemyBrewResultSchema | None = None
    extractedReagent: AlchemyCatalogReagentSchema | None = None
    market: dict[str, Any] | None = None
    marketQuote: dict[str, Any] | None = None
    lore: dict[str, Any] | None = None
    generatedName: dict[str, Any] | None = None


class ActionEnvelopeResponseSchema(Schema):
    ok: bool
    requestId: str
    data: ActionDataSchema
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class ErrorEnvelopeSchema(Schema):
    ok: Literal[False]
    requestId: str
    data: dict[str, Any] = {}
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema]


class MarketEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: dict[str, Any]
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class LoreEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: dict[str, Any]
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []


class NameCatalogEnvelopeSchema(Schema):
    ok: bool
    requestId: str
    data: dict[str, Any]
    events: list[EventSchema] = []
    warnings: list[dict[str, Any]] = []
    errors: list[ErrorSchema] = []
