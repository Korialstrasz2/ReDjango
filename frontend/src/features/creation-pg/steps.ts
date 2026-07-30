export type CreationStep = "identity" | "race" | "preferred" | "summary";

export const CREATION_STEPS: CreationStep[] = ["identity", "race", "preferred", "summary"];

export type CreationDraft = {
  nome: string;
  eta: string;
  sesso: string;
  dettagliPersonaggio: string;
  background: string;
  razza: string;
  sottorazza: string;
  caratteristicaPreferita: string;
};

export type RaceOption = { value: string; label: string; subraces: Array<{ value: string; label: string }> };

export const emptyDraft: CreationDraft = {
  nome: "",
  eta: "",
  sesso: "",
  dettagliPersonaggio: "",
  background: "",
  razza: "",
  sottorazza: "",
  caratteristicaPreferita: "",
};

/** Motivi per cui uno step non è ancora completo. Vuoto significa che si può proseguire. */
export function stepIssues(step: CreationStep, draft: CreationDraft, races: RaceOption[]): string[] {
  const issues: string[] = [];
  if (step === "identity") {
    if (!draft.nome.trim()) issues.push("Serve un nome.");
    if (draft.eta.trim()) {
      const eta = Number(draft.eta);
      if (!Number.isInteger(eta) || eta < 1 || eta > 999) issues.push("L'età deve essere un numero fra 1 e 999.");
    }
  }
  if (step === "race") {
    const race = races.find((entry) => entry.value === draft.razza);
    if (!race) issues.push("Scegli una razza.");
    // Le razze senza sottorazze in catalogo (Xivilai) non devono bloccare il passaggio.
    else if (race.subraces.length && !draft.sottorazza) issues.push("Scegli una sottorazza.");
    else if (draft.sottorazza && !race.subraces.some((entry) => entry.value === draft.sottorazza)) {
      issues.push(`«${draft.sottorazza}» non è una sottorazza di ${race.label}.`);
    }
  }
  if (step === "preferred" && !draft.caratteristicaPreferita) issues.push("Scegli una caratteristica preferita.");
  return issues;
}

export function canSubmit(draft: CreationDraft, races: RaceOption[]): boolean {
  return CREATION_STEPS.every((step) => stepIssues(step, draft, races).length === 0);
}

/** Cambiare razza invalida la sottorazza scelta prima. */
export function withRace(draft: CreationDraft, razza: string): CreationDraft {
  return { ...draft, razza, sottorazza: "" };
}

export function creationPayload(draft: CreationDraft): Record<string, unknown> {
  return {
    nome: draft.nome.trim(),
    razza: draft.razza,
    sottorazza: draft.sottorazza,
    caratteristicaPreferita: draft.caratteristicaPreferita,
    eta: draft.eta.trim() ? Number(draft.eta) : null,
    sesso: draft.sesso,
    dettagliPersonaggio: draft.dettagliPersonaggio.trim(),
    background: draft.background.trim(),
  };
}
