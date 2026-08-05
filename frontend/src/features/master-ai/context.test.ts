import { describe, expect, it } from "vitest";

import { buildMasterAIUrl, parseMasterAILaunch } from "./context";

describe("Master AI contextual launcher contract", () => {
  it("builds a target launcher without auto-submit state", () => {
    const url = buildMasterAIUrl({
      entityType: "item",
      targetId: 42,
      recordLabel: "Spada lunga",
      sourceSurface: "item-management",
      defaultPrompt: "Rivedi la Spada lunga.",
    });
    const parsed = parseMasterAILaunch(url.slice(url.indexOf("?")));
    expect(parsed.context).toEqual({ entityType: "item", targetId: 42, sourceSurface: "item-management" });
    expect(parsed.recordLabel).toBe("Spada lunga");
    expect(parsed.prompt).toBe("Rivedi la Spada lunga.");
  });

  it("builds a Spell clone launcher through the Skill surface", () => {
    const url = buildMasterAIUrl({
      entityType: "spell",
      sourceId: 17,
      recordLabel: "Tocco della Distruzione",
      sourceSurface: "skill-management",
    });
    expect(parseMasterAILaunch(url.slice(url.indexOf("?"))).context).toEqual({
      entityType: "spell",
      sourceId: 17,
      sourceSurface: "skill-management",
    });
  });

  it("builds a Unit launcher through the Unit management surface", () => {
    const url = buildMasterAIUrl({
      entityType: "unit",
      targetId: 9,
      recordLabel: "Lupo",
      sourceSurface: "unit-management",
    });
    expect(parseMasterAILaunch(url.slice(url.indexOf("?"))).context).toEqual({
      entityType: "unit",
      targetId: 9,
      sourceSurface: "unit-management",
    });
  });

  it("rejects target and source in the same launcher", () => {
    expect(() => buildMasterAIUrl({ entityType: "item", targetId: 1, sourceId: 2, sourceSurface: "item-management" })).toThrow();
    expect(parseMasterAILaunch("?entity=item&target=1&source=2&surface=item-management").context).toBeNull();
  });

  it("fails closed for unsupported entities and surfaces", () => {
    expect(parseMasterAILaunch("?entity=shop&target=1&surface=shop-management").context).toBeNull();
    expect(parseMasterAILaunch("?entity=theme&target=1&surface=player-management").context).toBeNull();
  });

  it("keeps the display label outside the backend context", () => {
    const parsed = parseMasterAILaunch("?entity=theme&target=8&surface=theme-management&label=Notte");
    expect(parsed.recordLabel).toBe("Notte");
    expect(parsed.context).toEqual({ entityType: "theme", targetId: 8, sourceSurface: "theme-management" });
    expect(parsed.context).not.toHaveProperty("label");
  });
});
