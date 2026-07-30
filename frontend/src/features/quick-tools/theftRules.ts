/** Tabelle Elder di "SCASSINARE e BORSEGGIARE" tradotte in un calcolatore.
 *
 * Lo strumento calcola solo la soglia e il modificatore: il tiro, l'usura del
 * set e l'eventuale tiro di Percezione dell'altra persona restano al tavolo.
 */

export type TheftMode = "scasso" | "borseggio";

/** Punto di partenza della prova: livello della serratura oppure oggetto da rubare. */
export type TheftBase = { key: string; label: string; hint: string; threshold: number };

/** Modificatore attivabile con una casella. `group` rende esclusive le voci che
 * nel regolamento descrivono la stessa circostanza (non puoi essere insieme in
 * compagnia amichevole e ostile). */
export type TheftToggle = { key: string; label: string; hint: string; value: number; group?: string };

export type TheftContribution = { key: string; label: string; value: number; note?: string };

export type TheftCheck = {
  base: TheftBase;
  contributions: TheftContribution[];
  /** Somma di caselle e modificatore manuale: il "modificatore finale". */
  modifier: number;
  /** Soglia base più il modificatore finale, mai sotto 1. */
  threshold: number;
  rollBonus: number;
  competence: string;
};

export const THEFT_COMPETENCE: Record<TheftMode, string> = {
  scasso: "Ingegneria",
  borseggio: "Rapidità di mano",
};

export const LOCK_LEVELS: TheftBase[] = [
  { key: "elementare", label: "Elementare", hint: "Catenacci e cassette da mercato.", threshold: 8 },
  { key: "semplice", label: "Semplice", hint: "Porte di casa, bauli da viaggio.", threshold: 10 },
  { key: "comune", label: "Comune", hint: "Botteghe e magazzini sorvegliati.", threshold: 12 },
  { key: "buona", label: "Buona", hint: "Casseforti, celle, dispense nobiliari.", threshold: 14 },
  { key: "eccellente", label: "Eccellente", hint: "Meccanismi da maestro artigiano.", threshold: 16 },
];

export const PICKPOCKET_TARGETS: TheftBase[] = [
  { key: "mela", label: "Oggetto minuto", hint: "Il riferimento Elder: rubare una mela.", threshold: 2 },
  { key: "arma1", label: "Arma a una mano", hint: "Daghe, spade corte, borsette pesanti.", threshold: 4 },
  { key: "arma2", label: "Arma a due mani", hint: "Tutto ciò che non si sfila di nascosto.", threshold: 6 },
];

/** Il metallo nanico non annulla il bonus della manutenzione, solo il malus. */
export const DWARVEN_TOGGLE = "nanico";

export const LOCK_TOGGLES: TheftToggle[] = [
  { key: "curata", label: "Tenuta con cura", hint: "Casa nobiliare, presidio in servizio.", value: 2, group: "manutenzione" },
  { key: "trascurata", label: "In cattivo stato", hint: "Rovine, edifici abbandonati.", value: -2, group: "manutenzione" },
  { key: DWARVEN_TOGGLE, label: "Metallo nanico", hint: "Per sua natura non subisce malus.", value: 0 },
];

export const PICKPOCKET_TOGGLES: TheftToggle[] = [
  { key: "amichevoli", label: "In compagnia amichevole", hint: "Gente che non ti sorveglia.", value: 2, group: "compagnia" },
  { key: "neutrali", label: "In compagnia neutrale", hint: "La sala comune di una taverna.", value: 4, group: "compagnia" },
  { key: "diffidenti", label: "In compagnia ostile", hint: "Persone di cui non ci si fida.", value: 6, group: "compagnia" },
  { key: "borsello", label: "Borsello di monete", hint: "Rubare le monete è sempre più difficile.", value: 2 },
  { key: "dorme", label: "La vittima dorme", hint: "Sonno profondo, non un dormiveglia.", value: -3 },
];

/** Il regolamento lascia al Master l'ampiezza del diversivo, da 1 a 4. */
export const DIVERSION_STEPS = [0, 1, 2, 3, 4];

/** Costi Elder dei set, nell'ordine del catalogo oggetti. I bonus sono quelli
 * scritti sugli oggetti in archivio: "Set scassinamento avanzato" vale davvero
 * +4 pur costando più del "qualificato", quindi la voce resta com'è finché la
 * scheda oggetto non viene corretta. */
export const LOCKPICK_SETS: Array<{ key: string; label: string; hint: string; bonus: number }> = [
  { key: "improvvisato", label: "Set improvvisato", hint: "Fermagli e chiodi: malus 3.", bonus: -3 },
  { key: "nessuno", label: "Nessun set", hint: "Solo le tue mani.", bonus: 0 },
  { key: "base", label: "Set base", hint: "75 settim.", bonus: 2 },
  { key: "apprendista", label: "Set da apprendista", hint: "150 settim.", bonus: 4 },
  { key: "qualificato", label: "Set da qualificato", hint: "250 settim.", bonus: 6 },
  { key: "avanzato", label: "Set avanzato", hint: "400 settim.", bonus: 4 },
  { key: "maestro", label: "Set da maestro", hint: "700 settim.", bonus: 8 },
];

export const LOCKPICK_ATTEMPTS = 3;

export function basesForMode(mode: TheftMode): TheftBase[] {
  return mode === "scasso" ? LOCK_LEVELS : PICKPOCKET_TARGETS;
}

export function togglesForMode(mode: TheftMode): TheftToggle[] {
  return mode === "scasso" ? LOCK_TOGGLES : PICKPOCKET_TOGGLES;
}

/** Le caselle di uno stesso gruppo si escludono: attivarne una spegne l'altra. */
export function applyToggle(mode: TheftMode, active: string[], key: string): string[] {
  if (active.includes(key)) return active.filter((entry) => entry !== key);
  const group = togglesForMode(mode).find((toggle) => toggle.key === key)?.group;
  const siblings = group
    ? togglesForMode(mode).filter((toggle) => toggle.group === group).map((toggle) => toggle.key)
    : [];
  return [...active.filter((entry) => !siblings.includes(entry)), key];
}

function clampedManual(manual: number): number {
  if (!Number.isFinite(manual)) return 0;
  return Math.max(-20, Math.min(20, Math.trunc(manual)));
}

export function calculateCheck(
  mode: TheftMode,
  baseKey: string,
  activeToggles: string[],
  diversion: number,
  manual: number,
  setKey: string,
): TheftCheck {
  const bases = basesForMode(mode);
  const base = bases.find((entry) => entry.key === baseKey) || bases[0];
  const dwarven = mode === "scasso" && activeToggles.includes(DWARVEN_TOGGLE);
  const contributions: TheftContribution[] = [];

  togglesForMode(mode).forEach((toggle) => {
    if (!activeToggles.includes(toggle.key) || toggle.key === DWARVEN_TOGGLE) return;
    const cancelled = dwarven && toggle.value < 0;
    contributions.push({
      key: toggle.key,
      label: toggle.label,
      value: cancelled ? 0 : toggle.value,
      note: cancelled ? "annullato dal metallo nanico" : undefined,
    });
  });

  const steps = mode === "borseggio" ? Math.max(0, Math.min(4, Math.trunc(diversion) || 0)) : 0;
  if (steps > 0) contributions.push({ key: "diversivo", label: "Diversivo", value: -steps });

  const manualValue = clampedManual(manual);
  if (manualValue !== 0) contributions.push({ key: "manuale", label: "Modificatore manuale", value: manualValue });

  const modifier = contributions.reduce((total, entry) => total + entry.value, 0);
  return {
    base,
    contributions,
    modifier,
    threshold: Math.max(1, base.threshold + modifier),
    rollBonus: mode === "scasso" ? LOCKPICK_SETS.find((entry) => entry.key === setKey)?.bonus ?? 0 : 0,
    competence: THEFT_COMPETENCE[mode],
  };
}
