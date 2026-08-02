import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildTerrainBadges, HexInspector } from "./CombatPage";
import type { Axial, CombatMap, CombatWorkspace } from "./types";

const HEX_TYPES = [
  { id: 1, name: "Bosco", slug: "bosco", description: "", movementMultiplier: 1.5, color: "#3d6a42", impassable: false },
];

const MAP = {
  id: 1, name: "Test", mapType: "", mapTypeId: 1, imageId: null, imageUrl: "",
  orientation: "pointy", rows: 2, columns: 2, hexSize: 30,
  gridOffsetX: 0, gridOffsetY: 0, imageScale: 1, imageOffsetX: 0, imageOffsetY: 0,
  viewportScale: 1, viewportOffsetX: 0, viewportOffsetY: 0, activeCharacterId: null,
  fogEnabled: false, fogOpacity: 0, viewerCanSeeAll: false,
  activeCharacterIds: [], participants: [], modifiers: [], plannedActions: [], events: [], hexes: [],
  updatedAt: "", isDefault: false, snapshots: [],
} as CombatMap;

const WORKSPACE = {
  map: MAP,
  hexTypes: HEX_TYPES,
  permissions: { canManageMaps: false, canImportCharacters: false, canControlCharacters: false, canApplyEnemyEffects: false },
} as unknown as CombatWorkspace;

describe("strumenti esagono per giocatori", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("offre colore e selezione, senza tipologia o controlli della nebbia", () => {
    const selectedCells: Axial[] = [{ q: 1, r: 0 }];
    const onApply = vi.fn();
    const onSelectionChange = vi.fn();

    act(() => root.render(<HexInspector
      workspace={WORKSPACE}
      selectedCells={selectedCells}
      canManage={false}
      tab="types"
      terrainBadges={buildTerrainBadges(HEX_TYPES)}
      onTabChange={vi.fn()}
      onSelectionChange={onSelectionChange}
      onApply={onApply}
      onFog={vi.fn()}
    />));

    expect(container.textContent).toContain("1 esagoni selezionati");
    expect(container.textContent).toContain("Applica colore");
    expect(container.textContent).not.toContain("Tipologia");
    expect(container.textContent).not.toContain("Nebbia di guerra");
    expect(container.textContent).not.toContain("Visibilità per i giocatori");

    const applyButton = [...container.querySelectorAll("button")]
      .find((button) => button.textContent === "Applica colore");
    expect(applyButton).toBeDefined();
    act(() => applyButton!.dispatchEvent(new MouseEvent("click", { bubbles: true })));

    expect(onApply).toHaveBeenCalledWith({
      cells: selectedCells,
      overlayColor: "#c96e3f",
      overlayOpacity: .42,
    });
    expect(onSelectionChange).toHaveBeenCalledWith([]);
  });
});
