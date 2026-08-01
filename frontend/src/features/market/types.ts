import type { Item } from "../../lib/types";

export type MarketPlace = {
  key: string;
  label: string;
  enabled: boolean;
  locationKey: string;
  shopCount: number;
};

export type MarketRegion = {
  key: string;
  label: string;
  enabled: boolean;
  places: MarketPlace[];
  shopCount: number;
};

export type MarketLocationConfiguration = {
  version: number;
  regions: Array<{
    key: string;
    label: string;
    enabled: boolean;
    places: Array<{ key: string; label: string; enabled: boolean; aliases?: string[] }>;
  }>;
};

export type ShopType = {
  key: string;
  label: string;
  icon: string;
  enabled: boolean;
  defaultBackground?: string;
  inventoryMultiplier: number;
  itemTypeRanks?: Record<string, number>;
};

export type ShopTypeConfiguration = {
  version: number;
  types: ShopType[];
};

export type ShopSummary = {
  id: number;
  name: string;
  owner: string;
  categoryKey: string;
  level: number;
  locationKey: string;
  regionName: string;
  placeName: string;
  description: string;
  backgroundUrl: string;
  featured: boolean;
  archived: boolean;
  stockRevision: number;
  stockCount: number;
  distinctStockCount: number;
  priceModifierPercent: number;
  lastRestockedAt: string | null;
};

export type StockLine = {
  item: Item;
  quantity: number;
  unitPrice: number;
  source: string;
};

export type ShopDetail = ShopSummary & {
  seed: string;
  stock: StockLine[];
  diagnostics: Record<string, unknown>;
};

export type StockExclusionSample = {
  id: number;
  name: string;
  itemType: string;
  lootLevel: string;
  reasons: string[];
};

export type StockEligibility = {
  eligibleCount: number;
  excludedCount: number;
  configuredTypes: string[];
  rollableRarities: number[];
  reasons: Array<{ key: string; label: string; count: number }>;
  samples: StockExclusionSample[];
  sampleLimit: number;
};

export type RarityChoice = { value: string; label: string };

export type MarketData = {
  stockEligibility?: StockEligibility;
  locations: MarketRegion[];
  shopTypes: ShopType[];
  shops: ShopSummary[];
  selectedShop: ShopDetail | null;
  character: { id: number; name: string; coins: number } | null;
  permissions: {
    canManage: boolean;
    canEditLocations: boolean;
    canEditShopTypes: boolean;
    canRegenerate: boolean;
    canTuneGenerator: boolean;
    canBatchCreate: boolean;
    canArchive: boolean;
    canPurchase: boolean;
  };
  configuration: {
    hash?: string;
    locations?: MarketLocationConfiguration | null;
    shopTypes?: ShopTypeConfiguration | null;
    generatorRules?: Record<string, unknown> | null;
    rarityChoices?: RarityChoice[];
    itemTypes?: string[];
    limits: Record<string, number>;
  };
};

export type MarketActionData = {
  market?: MarketData;
  marketQuote?: { total: number };
};

export type ShopDraft = {
  name: string;
  owner: string;
  locationKey: string;
  categoryKey: string;
  level: number;
  description: string;
  priceModifierPercent: number;
  featured: boolean;
  seed: string;
  generateStock: boolean;
};
