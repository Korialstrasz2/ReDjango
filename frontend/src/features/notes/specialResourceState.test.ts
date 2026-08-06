import { describe, expect, it } from "vitest";

import type { CampaignData, CampaignSpecialResource } from "../../lib/types";
import {
  pendingSpecialResourceCount,
  specialResourceLineChanged,
  specialResourceLineDraft,
  specialResourceText,
} from "./specialResourceState";

const resource: CampaignSpecialResource = {
  id: "resource-1",
  character: "Rhyss",
  name: "Dono di Sanguine",
  value: "2 disponibili",
  notes: "Si rinnova all'alba.",
  highlighted: true,
  order: 0,
  archivedAt: null,
  createdAt: "2026-08-01T10:00:00Z",
  updatedAt: "2026-08-01T10:00:00Z",
  updatedBy: { id: 1, name: "Master" },
};

function campaign(canManage: boolean, statuses: Array<"pending" | "approved" | "rejected">): CampaignData {
  return {
    id: 1,
    name: "Sanguine",
    isActive: true,
    isSelected: true,
    weather: "Soleggiato",
    weatherLabel: "Soleggiato",
    weatherEffects: "",
    currentTime: "12",
    currentHour: 12,
    daysSinceStart: 1,
    sharedNotes: "",
    specialResources: {
      resources: [resource],
      canManage,
      proposals: statuses.map((status, index) => ({
        id: `proposal-${index}`,
        resourceId: resource.id,
        resourceName: resource.name,
        action: "save",
        before: { value: resource.value },
        values: { value: `${index + 1} disponibili` },
        baseUpdatedAt: resource.updatedAt,
        status,
        proposedBy: { id: 2, name: "Giocatore" },
        createdAt: "2026-08-02T10:00:00Z",
        reviewedAt: null,
        reviewedBy: null,
      })),
    },
  };
}

describe("special-resource line state", () => {
  it("combines the old value and rule into the new free-text line", () => {
    expect(specialResourceText(resource)).toBe("2 disponibili\nSi rinnova all'alba.");
  });

  it("keeps an untouched row disabled and detects visible edits", () => {
    const draft = specialResourceLineDraft(resource);
    expect(specialResourceLineChanged(resource, draft)).toBe(false);
    expect(specialResourceLineChanged(resource, { ...draft, text: ` ${draft.text} ` })).toBe(false);
    expect(specialResourceLineChanged(resource, { ...draft, text: `${draft.text}\nUsato una volta.` })).toBe(true);
  });

  it("counts pending approvals only for master/admin payloads", () => {
    expect(pendingSpecialResourceCount(campaign(true, ["pending", "approved", "pending"]))).toBe(2);
    expect(pendingSpecialResourceCount(campaign(false, ["pending"]))).toBe(0);
  });
});
