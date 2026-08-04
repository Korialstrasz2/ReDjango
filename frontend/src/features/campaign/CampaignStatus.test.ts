import { describe, expect, it } from "vitest";

import { clockLabel, dayLabel, weatherSummary } from "./CampaignStatus";
import type { CampaignData } from "../../lib/types";

const campaign = (overrides: Partial<CampaignData> = {}): CampaignData => ({
  id: 1,
  name: "Sanguine",
  isActive: true,
  isSelected: true,
  weather: "Pioggia - Costo movimento in combat +25%, Attacco -3",
  weatherLabel: "Pioggia",
  weatherEffects: "Costo movimento in combat +25%, Attacco -3",
  currentTime: "9",
  currentHour: 9,
  daysSinceStart: 33,
  sharedNotes: "",
  specialResources: { resources: [], proposals: [], canManage: false },
  ...overrides,
});

describe("campaign weather summary", () => {
  it("shows the weather name and keeps its rules for the tooltip", () => {
    expect(weatherSummary(campaign())).toEqual({
      label: "Pioggia",
      detail: "Costo movimento in combat +25%, Attacco -3",
    });
  });

  it("explains a campaign that never rolled its weather", () => {
    expect(weatherSummary(campaign({ weather: "", weatherLabel: "", weatherEffects: "" })).label).toBe("Sconosciuto");
  });

  it("keeps a readable tooltip for a weather without rule effects", () => {
    expect(weatherSummary(campaign({ weatherEffects: "" })).detail).toBe("Nessun effetto sulle regole.");
  });

  it("stays quiet when no campaign is selected", () => {
    expect(weatherSummary(null)).toEqual({ label: "—", detail: "Nessuna campagna selezionata." });
  });
});

describe("campaign clock labels", () => {
  it("shows the stored hour and day", () => {
    expect(clockLabel(campaign())).toBe("9");
    expect(dayLabel(campaign())).toBe("33");
  });

  it("marks an empty clock instead of pretending it is midnight", () => {
    expect(clockLabel(campaign({ currentTime: "  ", currentHour: 0 }))).toBe("—");
  });

  it("keeps day zero visible", () => {
    expect(dayLabel(campaign({ daysSinceStart: 0 }))).toBe("0");
  });

  it("falls back when no campaign is selected", () => {
    expect(clockLabel(null)).toBe("—");
    expect(dayLabel(null)).toBe("—");
  });
});
