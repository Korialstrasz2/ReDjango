import { describe, expect, it } from "vitest";

import { canSubmit, creationPayload, emptyDraft, stepIssues, withRace, type RaceOption } from "./steps";

const races: RaceOption[] = [
  {
    value: "Dunmer",
    label: "Dunmer",
    subraces: [
      { value: "Retaggio Mago", label: "Retaggio Mago" },
      { value: "Nobile di Vvardenfell", label: "Nobile di Vvardenfell" },
    ],
  },
  { value: "Nord", label: "Nord", subraces: [{ value: "Berserker", label: "Berserker" }] },
  { value: "Xivilai", label: "Xivilai", subraces: [] },
];

const complete = {
  ...emptyDraft,
  nome: "Sera Telvanni",
  razza: "Dunmer",
  sottorazza: "Retaggio Mago",
  caratteristicaPreferita: "intelligenza",
};

describe("nuovo PG steps", () => {
  it("requires a name and nothing else in the identity step", () => {
    expect(stepIssues("identity", emptyDraft, races)).toEqual(["Serve un nome."]);
    expect(stepIssues("identity", { ...emptyDraft, nome: "Sera" }, races)).toEqual([]);
  });

  it("accepts a missing age but rejects one out of range", () => {
    expect(stepIssues("identity", { ...complete, eta: "" }, races)).toEqual([]);
    expect(stepIssues("identity", { ...complete, eta: "31" }, races)).toEqual([]);
    expect(stepIssues("identity", { ...complete, eta: "0" }, races)).toHaveLength(1);
    expect(stepIssues("identity", { ...complete, eta: "1000" }, races)).toHaveLength(1);
    expect(stepIssues("identity", { ...complete, eta: "abc" }, races)).toHaveLength(1);
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

  it("requires the preferred characteristic before submitting", () => {
    expect(canSubmit({ ...complete, caratteristicaPreferita: "" }, races)).toBe(false);
    expect(canSubmit(complete, races)).toBe(true);
  });

  it("sends a null age instead of an empty string", () => {
    expect(creationPayload({ ...complete, eta: "" }).eta).toBeNull();
    expect(creationPayload({ ...complete, eta: "31" }).eta).toBe(31);
  });

  it("trims the free text fields", () => {
    expect(creationPayload({ ...complete, nome: "  Sera  " }).nome).toBe("Sera");
  });
});
