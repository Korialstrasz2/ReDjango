import { describe, expect, it } from "vitest";

import type { Effect, EffectConfiguration } from "../../lib/types";
import { effectIconAssetUrl, filterEffects } from "./CharacterEffectsWorkspace";

const configuration = {
  targets: [],
  presets: [],
  operations: [],
  operationOrderNote: "",
  formulaGuide: [],
  icons: [
    {
      value: "runa",
      label: "Runa arcana",
      category: "Arcano",
      keywords: "magia simbolo incantesimo",
      imageUrl: "/static/frontend/images/effects/icons/Runa%20arcana.webp",
    },
    {
      value: "gelo",
      label: "Cristallo di gelo",
      category: "Elementi",
      keywords: "freddo ghiaccio neve",
      imageUrl: "",
    },
  ],
} satisfies EffectConfiguration;

describe("risoluzione dell'asset delle icone effetto", () => {
  it("lascia usare il glifo SVG quando l'icona selezionata non ha un asset WebP", () => {
    expect(effectIconAssetUrl("gelo", configuration)).toBe("");
  });

  it("usa l'asset predefinito soltanto per un valore non presente nel catalogo", () => {
    expect(effectIconAssetUrl("sconosciuta", configuration)).toBe(configuration.icons[0].imageUrl);
  });
});

describe("ricerca degli effetti", () => {
  const effect = {
    scope: "custom",
    editable: true,
    id: 1,
    name: "Passo instancabile",
    description: "Continui a correre.",
    originName: "Stivali",
    temporary: false,
    operations: [{ target: "energia", operation: "add", value: "3", condition: "" }],
  } as Effect;
  const searchableConfiguration = {
    ...configuration,
    targets: [{ value: "energia", label: "Energia" }],
  } satisfies EffectConfiguration;

  it("separa la ricerca testuale da quella per variabile modificata", () => {
    expect(filterEffects([effect], searchableConfiguration, "stiv", "text")).toEqual([effect]);
    expect(filterEffects([effect], searchableConfiguration, "ener", "text")).toEqual([]);
    expect(filterEffects([effect], searchableConfiguration, "ener", "variable")).toEqual([effect]);
  });
});
