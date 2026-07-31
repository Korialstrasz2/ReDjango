import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { CombatMapCanvas } from "./CombatMapCanvas";
import { buildTerrainBadges } from "./CombatPage";
import type { CombatMap, EditedHex } from "./types";

const HEX_TYPES = [
  { id: 1, name: "Bosco", slug: "bosco", description: "", movementMultiplier: 1.5, color: "#3d6a42", impassable: false },
  { id: 2, name: "Acqua bassa", slug: "acqua-bassa", description: "", movementMultiplier: 1.5, color: "#4b91b0", impassable: false },
  { id: 3, name: "Neve", slug: "neve", description: "", movementMultiplier: 1.4, color: "#d8e2e3", impassable: false },
];

const hex = (q: number, r: number, terrainTypeIds: number[]): EditedHex => ({
  id: q * 10 + r, q, r, overlayColor: "", overlayOpacity: 0, blocked: false, revealed: true, fogEffect: false, terrainTypeIds,
});

const MAP = {
  id: 1, name: "Test", mapType: "", mapTypeId: 1, imageId: null, imageUrl: "",
  orientation: "pointy", rows: 2, columns: 2, hexSize: 30,
  gridOffsetX: 0, gridOffsetY: 0, imageScale: 1, imageOffsetX: 0, imageOffsetY: 0,
  viewportScale: 1, viewportOffsetX: 0, viewportOffsetY: 0, activeCharacterId: null,
  fogEnabled: false, fogOpacity: 0, viewerCanSeeAll: true,
  activeCharacterIds: [], participants: [], modifiers: [], plannedActions: [], events: [],
  hexes: [hex(0, 0, [1]), hex(1, 0, [2]), hex(0, 1, [3]), hex(1, 1, [])],
  updatedAt: "", isDefault: false, snapshots: [],
} as unknown as CombatMap;

const noop = () => {};

describe("etichette di tipologia sugli esagoni", () => {
  let container: HTMLDivElement;
  let root: Root;

  const render = (terrainBadges: ReturnType<typeof buildTerrainBadges> | null) => act(() => {
    root.render(<CombatMapCanvas
      map={MAP} selected={null} selectedCells={[]} selectionEnabled={false} terrainBadges={terrainBadges}
      paths={null} pathStart={null} controlledCharacterId={null} canControlAll={false}
      onHexClick={noop} onSelectionChange={noop} onMoveParticipant={noop} onContextParticipant={noop}
    />);
  });
  const badges = () => [...container.querySelectorAll(".combat-hex-terrain-badge")].map((node) => ({
    label: node.querySelector("text")?.textContent,
    fill: node.querySelector("rect")?.getAttribute("fill"),
    ink: (node.querySelector("text") as SVGTextElement | null)?.style.fill,
    title: node.querySelector("title")?.textContent,
  }));

  beforeEach(() => {
    (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });
  afterEach(() => { act(() => root.unmount()); container.remove(); });

  it("non stampa nulla finché la scheda Tipologia è chiusa", () => {
    render(null);
    expect(badges()).toEqual([]);
  });

  it("stampa una sigla per ogni esagono tipizzato, col colore del terreno", () => {
    render(buildTerrainBadges(HEX_TYPES));
    expect(badges()).toEqual([
      { label: "BO", fill: "#3d6a42", ink: "#fdf6e3", title: "Bosco · Costo ×1.5" },
      { label: "AB", fill: "#4b91b0", ink: "#fdf6e3", title: "Acqua bassa · Costo ×1.5" },
      { label: "NE", fill: "#d8e2e3", ink: "#12160f", title: "Neve · Costo ×1.4" },
    ]);
  });
});
