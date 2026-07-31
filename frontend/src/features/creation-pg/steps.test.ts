import { describe, expect, it } from "vitest";

import { canSubmit, creationPayload, emptyDraft, stepIssues, withRace, type RaceOption } from "./steps";

const noBonus = { note: "", bonuses: [] };
const races: RaceOption[] = [
  {
    value: "Dunmer",
    label: "Dunmer",
    subraces: [
      { value: "Retaggio Mago", label: "Retaggio Mago", note: "", bonuses: [] },
      { value: "Nobile di Vvardenfell", label: "Nobile di Vvardenfell", note: "", bonuses: [] },
    ],
    modifiers: [{ label: "Intelligenza", value: "+2", kind: "bonus" }],
    trait: noBonus,
  },
  {
    value: "Nord",
    label: "Nord",
    subraces: [{ value: "Berserker", label: "Berserker", note: "", bonuses: [] }],
    modifiers: [],
    trait: noBonus,
  },
  { value: "Xivilai", label: "Xivilai", subraces: [], modifiers: [], trait: noBonus },
];

const complete = {
  ...emptyDraft,
  nome: "Sera Telvanni",
  eta: "31",
  sesso: "femmina",
  razza: "Dunmer",
  sottorazza: "Retaggio Mago",
  caratteristicaPreferita: "intelligenza",
};

describe("nuovo PG steps", () => {
  it("requires name, age and sex in the identity step", () => {
    expect(stepIssues("identity", emptyDraft, races)).toEqual(["Serve un nome.", "Serve un'età.", "Scegli il sesso."]);
    expect(stepIssues("identity", complete, races)).toEqual([]);
  });

  it("rejects a missing age and one out of range", () => {
    expect(stepIssues("identity", { ...complete, eta: "" }, races)).toEqual(["Serve un'età."]);
    expect(stepIssues("identity", { ...complete, eta: "0" }, races)).toHaveLength(1);
    expect(stepIssues("identity", { ...complete, eta: "1000" }, races)).toHaveLength(1);
    expect(stepIssues("identity", { ...complete, eta: "abc" }, races)).toHaveLength(1);
  });

  it("rejects a missing sex", () => {
    expect(stepIssues("identity", { ...complete, sesso: "" }, races)).toEqual(["Scegli il sesso."]);
  });

  it("rejects a subrace belonging to another race", () => {
    const issues = stepIssues("race", { ...complete, razza: "Nord", sottorazza: "Retaggio Mago" }, races);
    expect(issues).toEqual(["«Retaggio Mago» non è una sottorazza di Nord."]);
  });

  it("requires a subrace only when the race has any", () => {
    expect(stepIssues("race", { ...complete, sottorazza: "" }, races)).toEqual(["Scegli una sottorazza."]);
    expect(stepIssues("race", { ...complete, razza: "Xivilai", sottorazza: "" }, races)).toEqual([]);
  });

  it("drops the subrace when the race changes", () => {
    expect(withRace(complete, "Nord")).toMatchObject({ razza: "Nord", sottorazza: "" });
  });

  it("requires every mandatory field before submitting", () => {
    expect(canSubmit({ ...complete, caratteristicaPreferita: "" }, races)).toBe(false);
    expect(canSubmit({ ...complete, eta: "" }, races)).toBe(false);
    expect(canSubmit({ ...complete, sesso: "" }, races)).toBe(false);
    expect(canSubmit(complete, races)).toBe(true);
  });

  it("sends the age as a number", () => {
    expect(creationPayload({ ...complete, eta: " 31 " }).eta).toBe(31);
  });

  it("trims the free text fields", () => {
    expect(creationPayload({ ...complete, nome: "  Sera  " }).nome).toBe("Sera");
  });
});
