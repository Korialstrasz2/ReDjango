import type { CombatMap } from "./types";

export function combatFocusedCharacterId(
  map: CombatMap | null | undefined,
  viewerCharacterId: number | null | undefined,
  canManage: boolean,
  masterForegroundCharacterId: number | null | undefined,
) {
  if (!map) return null;
  const participantIds = new Set(map.participants.map((entry) => entry.character.id));
  if (canManage && masterForegroundCharacterId && participantIds.has(masterForegroundCharacterId)) {
    return masterForegroundCharacterId;
  }
  if (viewerCharacterId && participantIds.has(viewerCharacterId)) return viewerCharacterId;
  return map.participants[0]?.character.id ?? null;
}
