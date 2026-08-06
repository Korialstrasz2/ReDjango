import type {
  CampaignData,
  CampaignSpecialResource,
  CampaignSpecialResourceProposal,
} from "../../lib/types";

export type SpecialResourceLineDraft = {
  character: string;
  name: string;
  text: string;
};

export function specialResourceText(
  resource: { value?: string | null; notes?: string | null },
): string {
  return [resource.value, resource.notes]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .join("\n");
}

export function specialResourceLineDraft(
  resource: Pick<CampaignSpecialResource, "character" | "name" | "value" | "notes">,
): SpecialResourceLineDraft {
  return {
    character: resource.character,
    name: resource.name,
    text: specialResourceText(resource),
  };
}

function normalizedLine(draft: SpecialResourceLineDraft): SpecialResourceLineDraft {
  return {
    character: draft.character.trim(),
    name: draft.name.trim(),
    text: draft.text.trim(),
  };
}

export function specialResourceLineChanged(
  resource: Pick<CampaignSpecialResource, "character" | "name" | "value" | "notes">,
  draft: SpecialResourceLineDraft,
): boolean {
  const current = normalizedLine(specialResourceLineDraft(resource));
  const proposed = normalizedLine(draft);
  return current.character !== proposed.character
    || current.name !== proposed.name
    || current.text !== proposed.text;
}

export function pendingSpecialResourceProposals(
  campaign: CampaignData | null,
): CampaignSpecialResourceProposal[] {
  if (!campaign?.specialResources.canManage) return [];
  return campaign.specialResources.proposals.filter((proposal) => proposal.status === "pending");
}

export function pendingSpecialResourceCount(campaign: CampaignData | null): number {
  return pendingSpecialResourceProposals(campaign).length;
}
