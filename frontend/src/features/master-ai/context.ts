export type MasterAIEntityType = "item" | "skill" | "spell" | "theme";
export type MasterAISourceSurface = "item-management" | "skill-management" | "theme-management" | "management-hub" | "master-ai";

export type MasterAILaunchContext = {
  entityType: MasterAIEntityType;
  targetId?: number;
  sourceId?: number;
  sourceSurface: MasterAISourceSurface;
};

export type MasterAILaunchRequest = MasterAILaunchContext & {
  defaultPrompt?: string;
  recordLabel?: string;
};

const ENTITY_TYPES = new Set<MasterAIEntityType>(["item", "skill", "spell", "theme"]);
const SOURCE_SURFACES = new Set<MasterAISourceSurface>([
  "item-management",
  "skill-management",
  "theme-management",
  "management-hub",
  "master-ai",
]);

const positiveId = (value: string | null): number | undefined => {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
};

export function parseMasterAILaunch(search: string): { context: MasterAILaunchContext | null; prompt: string; recordLabel: string } {
  const params = new URLSearchParams(search);
  const entity = params.get("entity") as MasterAIEntityType | null;
  const surface = params.get("surface") as MasterAISourceSurface | null;
  const targetId = positiveId(params.get("target"));
  const sourceId = positiveId(params.get("source"));
  const prompt = (params.get("prompt") || "").slice(0, 8000);
  const recordLabel = (params.get("label") || "").trim().slice(0, 200);
  if (!entity || !ENTITY_TYPES.has(entity) || !surface || !SOURCE_SURFACES.has(surface)) return { context: null, prompt, recordLabel };
  if (targetId && sourceId) return { context: null, prompt, recordLabel };
  return {
    context: {
      entityType: entity,
      sourceSurface: surface,
      ...(targetId ? { targetId } : {}),
      ...(sourceId ? { sourceId } : {}),
    },
    prompt,
    recordLabel,
  };
}

export function buildMasterAIUrl(request: MasterAILaunchRequest): string {
  if (request.targetId && request.sourceId) throw new Error("A Master AI launcher cannot specify both targetId and sourceId.");
  const params = new URLSearchParams({ entity: request.entityType, surface: request.sourceSurface });
  if (request.targetId) params.set("target", String(request.targetId));
  if (request.sourceId) params.set("source", String(request.sourceId));
  if (request.recordLabel?.trim()) params.set("label", request.recordLabel.trim().slice(0, 200));
  if (request.defaultPrompt?.trim()) params.set("prompt", request.defaultPrompt.trim().slice(0, 8000));
  return `/tools/master-ai?${params.toString()}`;
}

export function contextRecordId(context: MasterAILaunchContext): number | undefined {
  return context.targetId || context.sourceId;
}
