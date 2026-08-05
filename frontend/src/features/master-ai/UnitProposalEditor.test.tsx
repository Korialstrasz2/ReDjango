import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ProposalFieldRenderer } from "./FieldRenderer";
import type { AIChangeField } from "./types";

beforeAll(() => {
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
});

afterEach(() => {
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

const fields: AIChangeField[] = [
  {
    name: "name",
    label: "Nome",
    kind: "text",
    group: "Identità",
    required: true,
    nullable: false,
    readOnly: false,
    help: "Contratto Unit di prova",
    choices: [],
    ui: {
      widget: "unitDefinition",
      width: "full",
      configuration: {
        kinds: [{ value: "creature", label: "Creatura" }, { value: "humanoid", label: "Umanoide" }],
        cores: [{ value: "warrior", label: "Guerriero", profile: {} }],
        tags: [],
        equipmentSlots: [{ value: "arma", label: "Arma" }],
        accessoryProfiles: [],
        competences: [],
        magicPolicies: [{ value: "none", label: "Nessuna magia" }, { value: "any", label: "Magia consentita" }],
        classFamilies: [],
        religionFamilies: [],
        races: [],
        statCurveProfiles: [{ value: "custom", label: "Personalizzato" }],
        statCurveVariables: [{ key: "pf", label: "Punti ferita", presets: {} }],
      },
    },
  },
  {
    name: "loreImageId",
    label: "Ritratto",
    kind: "image",
    group: "Identità",
    required: false,
    nullable: true,
    readOnly: false,
    help: "",
    choices: [],
    ui: {},
  },
  {
    name: "auditPreview",
    label: "Audit",
    kind: "structured",
    group: "Verifica",
    required: false,
    nullable: false,
    readOnly: true,
    help: "",
    choices: [],
    ui: { widget: "unitAudit" },
  },
];

const values = {
  name: "Bestia di prova",
  category: "Creature",
  generation: {
    kind: "creature",
    coreShare: 0.5,
    startingXp: 0,
    xpBase: 20,
    xpGrowth: 1,
    competenceStartingXp: 5,
    competenceXpBase: 15,
    competenceXpGrowth: 0,
    finalSpendingPasses: 4,
    magicPolicy: "any",
    allowedClassFamilies: [],
    allowedReligionFamilies: [],
    allowedRaces: [],
    allowedSubraces: [],
    allowHumanoidStatGrowth: false,
  },
  archetypeTags: {},
  competenceProfile: {},
  skillUnlocks: [],
  equipmentSlots: [],
  equipmentGroups: [],
  accessoryCountByLevel: [],
  accessoryProfileKey: "",
  innateActions: [],
  statProfile: { baseModifiers: {}, perLevelModifiers: {}, milestones: [], curves: [] },
  levels: [],
  auditPreview: {
    passed: true,
    warningCount: 0,
    levels: [1, 10, 20],
    named: [
      { level: 1, skills: 0, perks: 0, equipment: 0, innateActions: 1, warnings: [] },
      { level: 20, skills: 0, perks: 0, equipment: 0, innateActions: 1, warnings: [] },
    ],
    repeatability: [{ level: 1, stable: true }, { level: 20, stable: true }],
    automatic: [{ level: 1, unique: 2, variants: 3 }, { level: 20, unique: 2, variants: 3 }],
  },
};

describe("Unit proposal editor", () => {
  it("uses the specialized Unit surface and displays rollback audit results", async () => {
    const host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    await act(async () => root.render(
      <ProposalFieldRenderer fields={fields} values={values} errors={[]} disabled={false} onChange={vi.fn()} />,
    ));

    expect(host.textContent).toContain("Contratto Unit di prova");
    expect(host.textContent).toContain("Audit Unit superato");
    expect(host.textContent).toContain("Livello 20");
    expect(host.textContent).toContain("Varianti nominate stabili");

    await act(async () => root.unmount());
  });

  it("reports identity edits through the normal operation patch callback", async () => {
    const onChange = vi.fn();
    const host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    await act(async () => root.render(
      <ProposalFieldRenderer fields={fields} values={values} errors={[]} disabled={false} onChange={onChange} />,
    ));
    const name = host.querySelector('input[value="Bestia di prova"]') as HTMLInputElement;
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(name, "Bestia corretta");
      name.dispatchEvent(new Event("input", { bubbles: true }));
      name.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(onChange).toHaveBeenCalledWith("name", "Bestia corretta");
    await act(async () => root.unmount());
  });
});
