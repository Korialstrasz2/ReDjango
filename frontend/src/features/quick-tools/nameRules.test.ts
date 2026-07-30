import { describe, expect, it } from "vitest";

import type { GeneratedName, NameCultureEntry, NameRaceEntry } from "../../lib/types";
import { HISTORY_LIMIT, defaultCultureFor, nameSubtitle, poolSize, pushHistory } from "./nameRules";

const culture = (overrides: Partial<NameCultureEntry> = {}): NameCultureEntry => ({
  id: 1,
  name: "Dunmer",
  slug: "dunmer",
  race: "Dunmer",
  description: "",
  maleCount: 20,
  femaleCount: 18,
  surnameCount: 12,
  usable: true,
  ...overrides,
});

const generated = (overrides: Partial<GeneratedName> = {}): GeneratedName => ({
  name: "Rathas Dren",
  firstName: "Rathas",
  surname: "Dren",
  gender: "maschile",
  requestedGender: "casuale",
  race: "Dunmer",
  culture: "Dunmer",
  cultureId: 1,
  cultureDescription: "",
  alreadyUsed: false,
  ...overrides,
});

describe("scelta della cultura", () => {
  it("preferisce la cultura omonima della razza", () => {
    const race: NameRaceEntry = {
      race: "Dunmer",
      slug: "dunmer",
      playable: true,
      defaultCulture: "Dunmer",
      cultures: [culture({ id: 2, name: "Ashlander" }), culture({ id: 1, name: "Dunmer" })],
    };
    expect(defaultCultureFor(race)?.name).toBe("Dunmer");
  });

  it("ricade sulla prima cultura quando l'omonima non esiste", () => {
    const race: NameRaceEntry = {
      race: "Argoniano",
      slug: "argoniano",
      playable: true,
      defaultCulture: "Hist-Born",
      cultures: [culture({ id: 3, name: "Hist-Born", race: "Argoniano" })],
    };
    expect(defaultCultureFor(race)?.name).toBe("Hist-Born");
    expect(defaultCultureFor(null)).toBeNull();
  });
});

describe("consistenza dei bacini", () => {
  it("conta il bacino del genere richiesto", () => {
    expect(poolSize(culture(), "maschile")).toBe(20);
    expect(poolSize(culture(), "femminile")).toBe(18);
    expect(poolSize(culture(), "casuale")).toBe(20);
  });

  it("ricade sull'altro genere quando un bacino è unisex", () => {
    const unisex = culture({ femaleCount: 0, maleCount: 54 });
    expect(poolSize(unisex, "femminile")).toBe(54);
  });
});

describe("cronologia", () => {
  it("mette il nome nuovo in testa", () => {
    const history = pushHistory([generated({ name: "Sigrid" })], generated({ name: "Bjorn" }));
    expect(history.map((entry) => entry.name)).toEqual(["Bjorn", "Sigrid"]);
  });

  it("non tiene doppioni dello stesso nome", () => {
    const history = pushHistory([generated({ name: "Bjorn" }), generated({ name: "Sigrid" })], generated({ name: "Sigrid" }));
    expect(history.map((entry) => entry.name)).toEqual(["Sigrid", "Bjorn"]);
  });

  it("si ferma al limite", () => {
    let history: GeneratedName[] = [];
    for (let index = 0; index < HISTORY_LIMIT + 5; index += 1) {
      history = pushHistory(history, generated({ name: `Nome ${index}` }));
    }
    expect(history).toHaveLength(HISTORY_LIMIT);
    expect(history[0].name).toBe(`Nome ${HISTORY_LIMIT + 4}`);
  });
});

describe("sottotitolo", () => {
  it("omette la razza quando la cultura ha lo stesso nome", () => {
    expect(nameSubtitle(generated())).toBe("Dunmer · maschile");
  });

  it("mostra razza e cultura quando differiscono", () => {
    expect(nameSubtitle(generated({ culture: "Telvanni" }))).toBe("Dunmer · Telvanni · maschile");
  });
});
