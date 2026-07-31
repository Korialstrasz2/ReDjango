import { describe, expect, it } from "vitest";

import type { GeneratedName, NameCultureEntry, NameRaceEntry } from "../../lib/types";
import {
  HISTORY_LIMIT,
  cultureRoll,
  defaultCultureFor,
  genderRoll,
  nameSubtitle,
  poolHint,
  poolSize,
  pushHistory,
  raceRoll,
  resolvePreview,
  rolledParts,
} from "./nameRules";

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
  images: { maschile: "/media/dunmer-m.webp", femminile: "/media/dunmer-f.webp" },
  clips: { maschile: "/media/dunmer-m.mp4", femminile: "/media/dunmer-f.mp4" },
  ...overrides,
});

const raceEntry = (overrides: Partial<NameRaceEntry> = {}): NameRaceEntry => ({
  race: "Dunmer",
  slug: "dunmer",
  playable: true,
  defaultCulture: "Dunmer",
  image: "/media/razze/dunmer.webp",
  cultures: [culture()],
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
  cultureWasRolled: false,
  alreadyUsed: false,
  ...overrides,
});

describe("scelta della cultura", () => {
  it("preferisce la cultura omonima della razza", () => {
    const race = raceEntry({ cultures: [culture({ id: 2, name: "Ashlander" }), culture({ id: 1, name: "Dunmer" })] });
    expect(defaultCultureFor(race)?.name).toBe("Dunmer");
  });

  it("ricade sulla prima cultura quando l'omonima non esiste", () => {
    const race = raceEntry({
      race: "Argoniano",
      slug: "argoniano",
      defaultCulture: "Hist-Born",
      cultures: [culture({ id: 3, name: "Hist-Born", race: "Argoniano" })],
    });
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

describe("cascata: che cosa chiede ogni livello", () => {
  const race = raceEntry();

  it("il clic sulla razza fa tirare cultura e genere", () => {
    expect(raceRoll(race)).toEqual({ race: "Dunmer", gender: "casuale", randomCulture: true });
  });

  it("il clic sulla cultura lascia al dado solo il genere", () => {
    expect(cultureRoll(culture())).toEqual({ cultureId: 1, gender: "casuale" });
  });

  it("il clic sul genere non lascia nulla al dado", () => {
    expect(genderRoll(culture(), "femminile")).toEqual({ cultureId: 1, gender: "femminile" });
  });

  it("dichiara che cosa ha deciso il dado", () => {
    expect(rolledParts(raceRoll(race))).toBe("Sorteggiati: cultura e genere");
    expect(rolledParts(cultureRoll(culture()))).toBe("Sorteggiati: genere");
    expect(rolledParts(genderRoll(culture(), "maschile"))).toBe("");
    expect(rolledParts(null)).toBe("");
  });
});

describe("anteprima laterale", () => {
  it("mostra il ritratto della razza quando è aperto solo quel livello", () => {
    const preview = resolvePreview(raceEntry(), null, null);
    expect(preview).toEqual({
      title: "Dunmer",
      subtitle: "1 culture",
      image: "/media/razze/dunmer.webp",
      clip: "",
    });
  });

  it("segnala una razza solo narrativa nel sottotitolo", () => {
    expect(resolvePreview(raceEntry({ playable: false }), null, null)?.subtitle).toBe("Solo narrativa");
  });

  it("il livello più profondo vince sulla razza", () => {
    const preview = resolvePreview(raceEntry(), culture({ name: "Telvanni" }), null);
    expect(preview?.title).toBe("Telvanni");
  });

  it("senza sesso scelto la cultura mostra il ritratto maschile", () => {
    const preview = resolvePreview(null, culture(), null);
    expect(preview?.image).toBe("/media/dunmer-m.webp");
    expect(preview?.clip).toBe("/media/dunmer-m.mp4");
    expect(preview?.subtitle).toBe("Dunmer");
  });

  it("il sesso sotto il puntatore scambia immagine e clip", () => {
    const preview = resolvePreview(null, culture(), "femminile");
    expect(preview?.image).toBe("/media/dunmer-f.webp");
    expect(preview?.clip).toBe("/media/dunmer-f.mp4");
    expect(preview?.subtitle).toBe("Femminile");
  });

  it("un asset mancante resta stringa vuota invece di un'immagine rotta", () => {
    const bare = culture({ images: { maschile: "", femminile: "" }, clips: { maschile: "", femminile: "" } });
    expect(resolvePreview(null, bare, "maschile")).toMatchObject({ image: "", clip: "" });
    expect(resolvePreview(null, null, null)).toBeNull();
  });
});

describe("suggerimento sul bacino", () => {
  it("dice quando una cultura non ha cognomi", () => {
    expect(poolHint(culture({ surnameCount: 0 }))).toBe("20 nomi · nessun cognome in questa cultura");
  });

  it("conta nomi e cognomi", () => {
    expect(poolHint(culture(), "femminile")).toBe("18 nomi · 12 cognomi");
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
