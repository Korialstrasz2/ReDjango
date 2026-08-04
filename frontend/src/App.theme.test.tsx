import { beforeEach, describe, expect, it } from "vitest";

import { applyTheme } from "./App";
import type { ThemeData } from "./lib/types";

const THEME: ThemeData = {
  slug: "test",
  name: "Test",
  description: "",
  colors: {
    background: "#101714",
    panel: "#1c2723",
    panelStrong: "#26342f",
    text: "#f1eadc",
    mutedText: "#aca999",
    line: "#46534b",
    accent: "#96a85b",
    accentStrong: "#c6d576",
    gold: "#d0a95b",
    sidebar: "#0d1412",
  },
  overlayOpacity: 0.37,
  panelOpacity: 0.81,
  backgroundPosition: "center",
  backgroundBlur: 4,
  backgrounds: {},
};

describe("applyTheme surface opacity targets", () => {
  beforeEach(() => {
    const root = document.documentElement;
    root.removeAttribute("style");
    root.removeAttribute("data-theme");
    root.removeAttribute("data-color-mode");
  });

  it("writes the configured opacities as target variables", () => {
    applyTheme(THEME);
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--theme-overlay-opacity-target")).toBe("0.37");
    expect(root.style.getPropertyValue("--theme-panel-opacity-target")).toBe("0.81");
  });

  it("no longer writes the effective variables directly", () => {
    applyTheme(THEME);
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--overlay-opacity")).toBe("");
    expect(root.style.getPropertyValue("--panel-opacity")).toBe("");
  });

  it("keeps the global derived surfaces at the configured values outside reveal scopes", () => {
    applyTheme(THEME);
    const root = document.documentElement;
    // I valori effettivi restano derivati dai bersagli per chi non partecipa alla rivelazione.
    expect(root.style.getPropertyValue("--overlay-opacity")).toBe("");
    expect(root.style.getPropertyValue("--theme-overlay-opacity-target")).toBe("0.37");
  });
});
