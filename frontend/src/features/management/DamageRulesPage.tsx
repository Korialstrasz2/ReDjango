import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Modal } from "../../components/Modal";
import { command, getData, type ApiClientError } from "../../lib/api";
import type {
  DamageRules,
  DamageRulesData,
  DamageRulesValidation,
} from "../../lib/types";
import { useApp } from "../../App";


type ToolSection = "grid" | "tiers" | "resistances";


export function cloneDamageRules(rules: DamageRules): DamageRules {
  return JSON.parse(JSON.stringify(rules)) as DamageRules;
}


export function damageCellBand(value: number): string {
  if (value <= 0) return "zero";
  if (value < 60) return "low";
  if (value < 100) return "reduced";
  if (value === 100) return "full";
  if (value < 160) return "high";
  return "extreme";
}


function changedCellCount(original: DamageRules, draft: DamageRules): number {
  let changed = 0;
  for (const [level, value] of Object.entries(draft.resistancePercentages)) {
    if (original.resistancePercentages[level] !== value) changed += 1;
  }
  for (const [tier, value] of Object.entries(draft.tierDamageFormulas)) {
    if (original.tierDamageFormulas[tier] !== value) changed += 1;
  }
  for (const [roll, row] of Object.entries(draft.damageMultipliers)) {
    row.forEach((value, index) => {
      if (original.damageMultipliers[roll]?.[index] !== value) changed += 1;
    });
  }
  return changed;
}


function DamageRulesReview({
  validation,
  saving,
  onClose,
  onConfirm,
}: {
  validation: DamageRulesValidation;
  saving: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <Modal surface="tools"
      title="Conferma regole del danno"
      onClose={onClose}
      wide
      className="damage-rules-validation-modal"
      footer={<>
        <button type="button" className="button secondary" onClick={onClose}>
          Torna alla modifica
        </button>
        <button
          type="button"
          className="button primary"
          disabled={saving || validation.changedCount === 0}
          onClick={onConfirm}
        >
          {saving ? "Salvataggio…" : "Conferma e applica al combattimento"}
        </button>
      </>}
    >
      <section className="damage-rules-review" data-component-type="panel" data-theme="combat">
        <header>
          <span aria-hidden="true">✓</span>
          <div>
            <p className="eyebrow">Controllo server completato</p>
            <h3>{validation.message}</h3>
          </div>
        </header>
        <div>
          <article><strong>{validation.changeCounts.multipliers}</strong><span>Celle griglia</span></article>
          <article><strong>{validation.changeCounts.tiers}</strong><span>Formule Tier</span></article>
          <article><strong>{validation.changeCounts.resistances}</strong><span>Resistenze</span></article>
        </div>
        {validation.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        <small>
          Dopo il salvataggio, ogni nuovo attacco userà immediatamente questo profilo.
        </small>
      </section>
    </Modal>
  );
}


export function DamageRulesPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const importRef = useRef<HTMLInputElement>(null);
  const query = useQuery({
    queryKey: ["management", "damage-rules"],
    queryFn: () =>
      getData<DamageRulesData>("/api/v1/management/damage-rules"),
  });
  const [draft, setDraft] = useState<DamageRules | null>(null);
  const [section, setSection] = useState<ToolSection>("grid");
  const [previewRoll, setPreviewRoll] = useState(10);
  const [previewDifference, setPreviewDifference] = useState(0);
  const [previewResistance, setPreviewResistance] = useState(0);
  const [previewTier, setPreviewTier] = useState(0);
  const [rowFill, setRowFill] = useState(100);
  const [columnFill, setColumnFill] = useState(100);
  const [gridOffset, setGridOffset] = useState(20);
  const [validation, setValidation] =
    useState<DamageRulesValidation | null>(null);

  useEffect(() => {
    if (query.data) setDraft(cloneDamageRules(query.data.rules));
  }, [query.data]);

  const changed = useMemo(
    () => query.data && draft
      ? changedCellCount(query.data.rules, draft)
      : 0,
    [draft, query.data],
  );
  const differences = useMemo(() => {
    if (!draft) return [];
    return Array.from(
      {
        length:
          draft.bounds.attackDifferenceMaximum
          - draft.bounds.attackDifferenceMinimum
          + 1,
      },
      (_, index) => draft.bounds.attackDifferenceMinimum + index,
    );
  }, [draft]);
  const rolls = useMemo(() => {
    if (!draft) return [];
    return Array.from(
      { length: draft.bounds.d20Maximum - draft.bounds.d20Minimum + 1 },
      (_, index) => draft.bounds.d20Minimum + index,
    );
  }, [draft]);

  const validateMutation = useMutation({
    mutationFn: () =>
      command<{ management: { validation: DamageRulesValidation } }>(
        "management.damageRules.validate",
        { rules: draft },
        "settings",
      ),
    onSuccess: (response) => {
      setValidation(response.data.management.validation);
      notify("Regole del danno validate. Controlla il riepilogo.");
    },
    onError: (error: ApiClientError) => notify(error.message, "error"),
  });
  const saveMutation = useMutation({
    mutationFn: (previewToken: string) =>
      command<{ management: { damageRules: DamageRulesData } }>(
        "management.damageRules.save",
        { rules: draft, previewToken },
        "settings",
      ),
    onSuccess: (response) => {
      const data = response.data.management.damageRules;
      queryClient.setQueryData(["management", "damage-rules"], data);
      setDraft(cloneDamageRules(data.rules));
      setValidation(null);
      notify("Regole del danno salvate e attive in Combattimento.");
    },
    onError: (error: ApiClientError) => {
      setValidation(null);
      notify(error.message, "error");
    },
  });

  const updateMultiplier = (roll: number, difference: number, value: number) => {
    setDraft((current) => {
      if (!current) return current;
      const row = [...current.damageMultipliers[String(roll)]];
      row[difference - current.bounds.attackDifferenceMinimum] = value;
      return {
        ...current,
        damageMultipliers: {
          ...current.damageMultipliers,
          [String(roll)]: row,
        },
      };
    });
    setValidation(null);
  };
  const fillRow = () => {
    if (!draft) return;
    const width = differences.length;
    setDraft({
      ...draft,
      damageMultipliers: {
        ...draft.damageMultipliers,
        [String(previewRoll)]: Array.from({ length: width }, () => rowFill),
      },
    });
    setValidation(null);
  };
  const fillColumn = () => {
    if (!draft) return;
    const index =
      previewDifference - draft.bounds.attackDifferenceMinimum;
    const damageMultipliers = Object.fromEntries(
      Object.entries(draft.damageMultipliers).map(([roll, row]) => {
        const next = [...row];
        next[index] = columnFill;
        return [roll, next];
      }),
    );
    setDraft({ ...draft, damageMultipliers });
    setValidation(null);
  };
  const offsetGrid = () => {
    if (!draft) return;
    const damageMultipliers = Object.fromEntries(
      Object.entries(draft.damageMultipliers).map(([roll, row]) => [
        roll,
        row.map((value) => Math.max(0, Math.min(1_000, value + gridOffset))),
      ]),
    );
    setDraft({ ...draft, damageMultipliers });
    setValidation(null);
  };

  const exportRules = () => {
    if (!draft) return;
    const blob = new Blob(
      [JSON.stringify(draft, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "redjango-regole-danno.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };
  const importRules = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !query.data) return;
    try {
      const parsed = JSON.parse(await file.text()) as DamageRules;
      if (
        !parsed
        || typeof parsed !== "object"
        || !parsed.damageMultipliers
        || !parsed.tierDamageFormulas
        || !parsed.resistancePercentages
      ) {
        throw new Error("Il file non contiene un profilo danno completo.");
      }
      const expected = query.data.rules;
      const completeGrid = Object.entries(expected.damageMultipliers).every(
        ([roll, row]) =>
          Array.isArray(parsed.damageMultipliers[roll])
          && parsed.damageMultipliers[roll].length === row.length,
      );
      const completeTiers = Object.keys(expected.tierDamageFormulas).every(
        (tier) => typeof parsed.tierDamageFormulas[tier] === "string",
      );
      const completeResistances = Object.keys(
        expected.resistancePercentages,
      ).every(
        (level) =>
          typeof parsed.resistancePercentages[level] === "number",
      );
      if (!completeGrid || !completeTiers || !completeResistances) {
        throw new Error(
          "Il profilo non contiene tutte le righe, i Tier o le resistenze richieste.",
        );
      }
      setDraft(cloneDamageRules({
        ...parsed,
        version: 1,
        bounds: { ...expected.bounds },
      }));
      setValidation(null);
      notify("Profilo importato localmente. Validalo prima di salvarlo.", "info");
    } catch (error) {
      notify(
        error instanceof Error ? error.message : "File JSON non valido.",
        "error",
      );
    }
  };

  if (query.isPending || !draft) {
    return <div className="page"><p>Caricamento Tool Danno…</p></div>;
  }
  if (query.error || !query.data) {
    return <div className="page"><section className="panel"><h1>Tool Danno</h1><p>{(query.error as Error)?.message || "Profilo non disponibile."}</p></section></div>;
  }

  const previewIndex =
    previewDifference - draft.bounds.attackDifferenceMinimum;
  const previewMultiplier =
    draft.damageMultipliers[String(previewRoll)]?.[previewIndex] ?? 0;
  const clampedResistance = Math.max(
    draft.bounds.resistanceLevelMinimum,
    Math.min(draft.bounds.resistanceLevelMaximum, previewResistance),
  );
  const previewResistancePercent =
    draft.resistancePercentages[String(clampedResistance)] ?? 0;
  const previewTierFormula =
    draft.tierDamageFormulas[String(previewTier)] || "No Danno";

  return (
    <div
      className="page damage-rules-page"
      data-component-type="view"
      data-theme="combat"
    >
      <header className="page-header">
        <div>
          <p className="eyebrow">Variabili globali · Combattimento</p>
          <h1>Tool Danno</h1>
          <p>
            Modifica il profilo realmente usato dal motore: resistenze,
            formule Tier e tutti i {query.data.counts.d20Rows * query.data.counts.attackDifferenceColumns}
            {" "}moltiplicatori d20.
          </p>
        </div>
        <div className="button-row">
          <Link className="button secondary" to="/tools/variables">
            ← Gestione Variabili
          </Link>
          <button type="button" className="button secondary" onClick={exportRules}>
            Esporta JSON
          </button>
          <button type="button" className="button secondary" onClick={() => importRef.current?.click()}>
            Importa JSON
          </button>
          <input ref={importRef} type="file" accept="application/json,.json" hidden onChange={importRules} />
          <button
            type="button"
            className="button primary"
            disabled={!changed || validateMutation.isPending}
            onClick={() => validateMutation.mutate()}
          >
            {validateMutation.isPending ? "Validazione…" : `Valida ${changed} modifiche`}
          </button>
        </div>
      </header>

      <section className="damage-rules-summary" data-component-type="panel" data-theme="gold">
        <article><span>Celle griglia</span><strong>{query.data.counts.d20Rows * query.data.counts.attackDifferenceColumns}</strong></article>
        <article><span>Formule Tier</span><strong>{query.data.counts.damageTiers}</strong></article>
        <article><span>Livelli resistenza</span><strong>{query.data.counts.resistanceLevels}</strong></article>
        <article className={changed ? "dirty" : ""}><span>Modifiche locali</span><strong>{changed}</strong></article>
      </section>

      <section className="damage-rules-behaviour" data-component-type="panel" data-theme="dark">
        <p><strong>Resistenze:</strong> {query.data.behaviour.resistanceOutsideRange}</p>
        <p><strong>Tier:</strong> {query.data.behaviour.tierOutsideRange}</p>
        <p><strong>Griglia:</strong> {query.data.behaviour.gridLookup}</p>
      </section>

      <nav className="damage-rules-tabs" role="tablist" aria-label="Sezioni Tool Danno" data-component-type="tabset" data-theme="combat">
        <button type="button" role="tab" aria-selected={section === "grid"} className={section === "grid" ? "active" : ""} onClick={() => setSection("grid")}>Moltiplicatori d20</button>
        <button type="button" role="tab" aria-selected={section === "tiers"} className={section === "tiers" ? "active" : ""} onClick={() => setSection("tiers")}>Tier danno</button>
        <button type="button" role="tab" aria-selected={section === "resistances"} className={section === "resistances" ? "active" : ""} onClick={() => setSection("resistances")}>Resistenze</button>
      </nav>

      {section === "grid" && <>
        <section className="damage-grid-tools" data-component-type="toolbar" data-theme="dark">
          <label>d20
            <input type="number" min={draft.bounds.d20Minimum} max={draft.bounds.d20Maximum} value={previewRoll} onChange={(event) => setPreviewRoll(Math.max(1, Math.min(20, Number(event.target.value) || 1)))} />
          </label>
          <label>Differenza
            <input type="number" min={draft.bounds.attackDifferenceMinimum} max={draft.bounds.attackDifferenceMaximum} value={previewDifference} onChange={(event) => setPreviewDifference(Math.max(-25, Math.min(45, Number(event.target.value) || 0)))} />
          </label>
          <output data-band={damageCellBand(previewMultiplier)}>
            Risultato: <strong>{previewMultiplier}%</strong> del danno
          </output>
          <label>Riempi riga con
            <input type="number" min="0" max="1000" value={rowFill} onChange={(event) => setRowFill(Number(event.target.value) || 0)} />
          </label>
          <button type="button" onClick={fillRow}>Applica alla riga d20 {previewRoll}</button>
          <label>Riempi colonna con
            <input type="number" min="0" max="1000" value={columnFill} onChange={(event) => setColumnFill(Number(event.target.value) || 0)} />
          </label>
          <button type="button" onClick={fillColumn}>Applica a differenza {previewDifference}</button>
          <label>Varia tutta la griglia
            <input type="number" min="-1000" max="1000" value={gridOffset} onChange={(event) => setGridOffset(Number(event.target.value) || 0)} />
          </label>
          <button type="button" onClick={offsetGrid}>Somma a tutte le celle</button>
        </section>
        <section className="damage-grid-shell" data-component-type="table" data-theme="combat">
          <table className="damage-multiplier-grid">
            <thead><tr><th>d20 \ Δ</th>{differences.map((difference) => <th key={difference} className={difference === previewDifference ? "selected" : ""}>{difference}</th>)}</tr></thead>
            <tbody>{rolls.map((roll) => <tr key={roll}>
              <th className={roll === previewRoll ? "selected" : ""}>{roll}</th>
              {differences.map((difference, index) => {
                const value = draft.damageMultipliers[String(roll)][index];
                return <td key={difference} data-band={damageCellBand(value)} className={roll === previewRoll && difference === previewDifference ? "selected" : ""}>
                  <input
                    type="number"
                    min="0"
                    max="1000"
                    step="1"
                    value={value}
                    aria-label={`d20 ${roll}, differenza ${difference}`}
                    onFocus={() => { setPreviewRoll(roll); setPreviewDifference(difference); }}
                    onChange={(event) => updateMultiplier(roll, difference, Number(event.target.value) || 0)}
                  />
                </td>;
              })}
            </tr>)}</tbody>
          </table>
        </section>
      </>}

      {section === "tiers" && <section className="damage-tier-workspace" data-component-type="panel" data-theme="default">
        <header><div><p className="eyebrow">Da -5 a 30</p><h2>Formule del danno per Tier</h2></div><label>Prova Tier<input type="number" value={previewTier} onChange={(event) => setPreviewTier(Number(event.target.value) || 0)} /></label><output>{previewTierFormula}</output></header>
        <p>Se il Tier finale non possiede una formula, il colpo resta riuscito ma il danno automatico è zero.</p>
        <div>{Object.keys(draft.tierDamageFormulas).sort((a, b) => Number(a) - Number(b)).map((tier) => <label key={tier} className={query.data.rules.tierDamageFormulas[tier] !== draft.tierDamageFormulas[tier] ? "dirty" : ""}>
          <span>Tier <strong>{tier}</strong></span>
          <input
            value={draft.tierDamageFormulas[tier]}
            spellCheck={false}
            onChange={(event) => {
              setDraft({ ...draft, tierDamageFormulas: { ...draft.tierDamageFormulas, [tier]: event.target.value } });
              setValidation(null);
            }}
          />
        </label>)}</div>
      </section>}

      {section === "resistances" && <section className="damage-resistance-workspace" data-component-type="panel" data-theme="default">
        <header><div><p className="eyebrow">Clamping Elder</p><h2>Percentuale per livello di resistenza</h2></div><label>Prova livello<input type="number" value={previewResistance} onChange={(event) => setPreviewResistance(Number(event.target.value) || 0)} /></label><output>Livello effettivo {clampedResistance}: <strong>{previewResistancePercent}%</strong></output></header>
        <p>Il valore percentuale viene sottratto al danno; una percentuale negativa aumenta il danno ricevuto.</p>
        <div>{Object.keys(draft.resistancePercentages).sort((a, b) => Number(a) - Number(b)).map((level) => <label key={level} className={query.data.rules.resistancePercentages[level] !== draft.resistancePercentages[level] ? "dirty" : ""}>
          <span>Livello <strong>{level}</strong></span>
          <span><input
            type="number"
            min="-500"
            max="100"
            step="1"
            value={draft.resistancePercentages[level]}
            onChange={(event) => {
              setDraft({ ...draft, resistancePercentages: { ...draft.resistancePercentages, [level]: Number(event.target.value) || 0 } });
              setValidation(null);
            }}
          /><b>%</b></span>
        </label>)}</div>
      </section>}

      <footer className="damage-rules-savebar">
        <div><strong>{changed ? `${changed} modifiche non salvate` : "Profilo sincronizzato"}</strong><span>Le modifiche locali non influenzano il combattimento finché non vengono validate e salvate.</span></div>
        <button type="button" className="button secondary" disabled={!changed} onClick={() => { setDraft(cloneDamageRules(query.data.rules)); setValidation(null); }}>Annulla modifiche</button>
        <button type="button" className="button secondary" onClick={() => { setDraft(cloneDamageRules(query.data.defaults)); setValidation(null); }}>Ripristina valori Elder</button>
        <button type="button" className="button primary" disabled={!changed || validateMutation.isPending} onClick={() => validateMutation.mutate()}>Valida prima di salvare</button>
      </footer>

      {validation && <DamageRulesReview validation={validation} saving={saveMutation.isPending} onClose={() => setValidation(null)} onConfirm={() => saveMutation.mutate(validation.previewToken)} />}
    </div>
  );
}
