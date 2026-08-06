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
  resource: Pick<CampaignSpecialResource, "value" | "notes">,
): string {
  return [resource.value, resource.notes]
    .map((value) => value.trim())
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

export function specialResourceLineChanged(
  resource: Pick<CampaignSpecialResource, "character" | "name" | "value" | "notes">,
  draft: SpecialResourceLineDraft,
): boolean {
  const current = specialResourceLineDraft(resource);
  return current.character !== draft.character
    || current.name !== draft.name
    || current.text !== draft.text;
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
