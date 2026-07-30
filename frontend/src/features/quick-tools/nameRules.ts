import type { GeneratedName, NameCultureEntry, NameGender, NameRaceEntry } from "../../lib/types";

/** Quanti nomi restano consultabili dopo un tiro nuovo. */
export const HISTORY_LIMIT = 10;

/** I cinque campi del dossier: pochi, e già precompilati da quello che il DB sa. */
export const DOSSIER_FIELDS = [
  { key: "eta", label: "Età", placeholder: "34, anziano, giovanissimo…" },
  { key: "stato", label: "Condizione", placeholder: "Povero, benestante, esule…" },
  { key: "occupazione", label: "Occupazione", placeholder: "Fabbro, guardia, ricettatore…" },
  { key: "luogo", label: "Dove lo si incontra", placeholder: "Taverna, mercato, accampamento…" },
  { key: "tratti", label: "Spunto libero", placeholder: "L'unica cosa che conta di questo PNG…" },
] as const;

export type DossierField = (typeof DOSSIER_FIELDS)[number]["key"];

export type DossierInputs = Record<DossierField, string>;

export const emptyDossierInputs = (): DossierInputs =>
  DOSSIER_FIELDS.reduce((accumulator, field) => ({ ...accumulator, [field.key]: "" }), {} as DossierInputs);

export function genderLabel(gender: NameGender): string {
  if (gender === "maschile") return "Maschile";
  if (gender === "femminile") return "Femminile";
  return "Casuale";
}

/** La cultura da usare quando il Master non ne ha scelta una: quella omonima della razza. */
export function defaultCultureFor(race: NameRaceEntry | null): NameCultureEntry | null {
  if (!race) return null;
  return race.cultures.find((entry) => entry.name === race.defaultCulture) || race.cultures[0] || null;
}

/** Quante voci ha davvero un bacino, per il genere richiesto. */
export function poolSize(culture: NameCultureEntry, gender: NameGender): number {
  if (gender === "maschile") return culture.maleCount || culture.femaleCount;
  if (gender === "femminile") return culture.femaleCount || culture.maleCount;
  return Math.max(culture.maleCount, culture.femaleCount);
}

/**
 * La cronologia tiene il nome nuovo in testa e non ammette doppioni: rigenerare
 * dieci volte deve lasciare dieci nomi diversi da riconsultare, non dieci righe
 * con lo stesso nome.
 */
export function pushHistory(history: GeneratedName[], entry: GeneratedName): GeneratedName[] {
  const withoutDuplicate = history.filter((item) => item.name !== entry.name);
  return [entry, ...withoutDuplicate].slice(0, HISTORY_LIMIT);
}

/** Sottotitolo di un nome generato, per la riga di cronologia. */
export function nameSubtitle(entry: GeneratedName): string {
  const parts = [entry.culture, genderLabel(entry.gender).toLowerCase()];
  if (entry.culture !== entry.race) parts.unshift(entry.race);
  return parts.join(" · ");
}
