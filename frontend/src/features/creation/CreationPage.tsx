import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type { AlchemyBrewResult, AlchemyCatalogReagent, AlchemyCreationData } from "../../lib/types";
import { projectedBrew, selectedQuantity, type AlchemyColor, type AlchemySelection } from "./mechanics";

type CreationTab = "alchemy" | "forge" | "enchant";
type AlchemyActionData = {
  creation: AlchemyCreationData;
  alchemyResult?: AlchemyBrewResult | null;
  extractedReagent?: AlchemyCatalogReagent | null;
};

const COLOR_ORDER: AlchemyColor[] = ["rosso", "verde", "blu"];

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

function EmptyWorkshop({ kind }: { kind: "forge" | "enchant" }) {
  const copy = kind === "forge"
    ? {
        eyebrow: "Secondo banco",
        title: "Forgiatura in ricostruzione",
        text: "Tipi di oggetto, materiali, lingotti e miglioramenti dell'Elder verranno tradotti in ricette validate e collegate al catalogo oggetti.",
      }
    : {
        eyebrow: "Terzo banco",
        title: "Incantamento in ricostruzione",
        text: "Altari, gemme, cariche e pergamene entreranno qui con calcoli server-side e risultati verificabili prima di consumare risorse.",
      };
  return <section className="panel creation-roadmap-panel">
    <span className="creation-roadmap-rune" aria-hidden="true">{kind === "forge" ? "◇" : "✧"}</span>
    <div><p className="eyebrow">{copy.eyebrow}</p><h2>{copy.title}</h2><p>{copy.text}</p></div>
  </section>;
}

function AlchemyWorkbench({ data }: { data: AlchemyCreationData }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [ingredients, setIngredients] = useState<AlchemySelection[]>([]);
  const [potionColor, setPotionColor] = useState<AlchemyColor>("rosso");
  const [effect, setEffect] = useState("");
  const [setItemId, setSetItemId] = useState<number | null>(data.rules.defaultSetId ?? null);
  const [lastBrew, setLastBrew] = useState<AlchemyBrewResult | null>(null);
  const [lastExtraction, setLastExtraction] = useState<AlchemyCatalogReagent | null>(null);

  const family = data.potionFamilies.find((entry) => entry.color === potionColor);
  useEffect(() => {
    if (!family?.effects.includes(effect)) setEffect(family?.effects[0] || "");
  }, [effect, family]);

  const baseSetBonus = Number(data.rules.baseSetBonus ?? 1);
  const selectedSet = data.sets.find((entry) => entry.id === setItemId) || null;
  const setBonus = selectedSet ? selectedSet.bonus : baseSetBonus;
  // A set can leave the bag between two refreshes: fall back to the auto-selected one.
  useEffect(() => {
    if (setItemId !== null && !data.sets.some((entry) => entry.id === setItemId)) {
      setSetItemId(data.rules.defaultSetId ?? null);
    }
  }, [data.rules.defaultSetId, data.sets, setItemId]);

  const estimate = useMemo(
    () => projectedBrew(data.multipliers, ingredients, potionColor, setBonus),
    [data.multipliers, ingredients, potionColor, setBonus],
  );
  const hasPotionColor = ingredients.some((ingredient) => ingredient.color === potionColor);

  const brewMutation = useMutation({
    mutationFn: () => command<AlchemyActionData>("alchemy.brew", {
      characterId: data.character.id,
      ingredients,
      potionColor,
      effect,
      setItemId,
    }, "creation"),
    onSuccess: (response) => {
      queryClient.setQueryData(["creation", data.character.id], response.data.creation);
      queryClient.invalidateQueries({ queryKey: ["character-sheet", data.character.id] });
      setLastBrew(response.data.alchemyResult || null);
      setIngredients([]);
      notify(response.events[0]?.message || "Miscela distillata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const extractMutation = useMutation({
    mutationFn: () => command<AlchemyActionData>("alchemy.extract", { characterId: data.character.id }, "creation"),
    onSuccess: (response) => {
      queryClient.setQueryData(["creation", data.character.id], response.data.creation);
      queryClient.invalidateQueries({ queryKey: ["character-sheet", data.character.id] });
      setLastExtraction(response.data.extractedReagent || null);
      notify(response.events[0]?.message || "Reagente estratto.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const addIngredient = (color: AlchemyColor, level: number, available: number) => {
    const alreadySelected = selectedQuantity(ingredients, color, level);
    if (ingredients.length >= data.rules.maxIngredients) {
      notify("Il banco contiene già quattro reagenti.", "info");
      return;
    }
    if (alreadySelected >= available) {
      notify("Non hai altri reagenti di questo tipo nella borsa.", "error");
      return;
    }
    setIngredients((current) => [...current, { color, level }]);
  };

  const stockByColor = COLOR_ORDER.map((color) => ({
    color,
    label: data.potionFamilies.find((entry) => entry.color === color)?.label || color,
    entries: data.bag.stock.filter((entry) => entry.color === color),
  }));

  return <div className="alchemy-workspace">
    <section className="panel alchemy-stock-panel">
      <header className="alchemy-section-heading">
        <div><p className="eyebrow">Alchimia&Contenitori</p><h2>Tre essenze, quattro livelli</h2></div>
        <div className="alchemy-capacity" aria-label={`${data.bag.occupied} spazi occupati su ${data.bag.capacity}`}>
          <strong>{data.bag.occupied}/{data.bag.capacity}</strong><span>{data.bag.remaining} liberi</span>
        </div>
      </header>
      <div className="alchemy-stock-matrix" role="table" aria-label="Reagenti per colore e livello">
        <div className="alchemy-matrix-head" role="row"><span /><span>Lv 1</span><span>Lv 2</span><span>Lv 3</span><span>Lv 4</span></div>
        {stockByColor.map((row) => <div className={`alchemy-stock-row color-${row.color}`} role="row" key={row.color}>
          <strong role="rowheader"><i aria-hidden="true" />{row.label}</strong>
          {row.entries.map((entry) => {
            const selected = selectedQuantity(ingredients, row.color, entry.level);
            const remaining = entry.quantity - selected;
            const multiplier = data.multipliers.levels.find((value) => value.level === entry.level)?.value || 0;
            return <button
              type="button"
              role="cell"
              key={entry.key}
              disabled={remaining <= 0 || ingredients.length >= data.rules.maxIngredients}
              onClick={() => addIngredient(row.color, entry.level, entry.quantity)}
              aria-label={`Aggiungi ${row.label} livello ${entry.level}; ${remaining} disponibili`}
            >
              <span className="alchemy-stock-count">{remaining}</span>
              <small>× {formatNumber(multiplier)}</small>
              {selected > 0 && <em>{selected} al banco</em>}
            </button>;
          })}
        </div>)}
      </div>
      {data.bag.unclassified.length > 0 && <aside className="alchemy-data-warning">
        <strong>Dati da classificare</strong>
        <span>{data.bag.unclassified.map((entry) => `${entry.label} ×${entry.quantity}`).join(", ")}. Restano conservati ma non entrano nelle ricette.</span>
      </aside>}
      <div className="alchemy-extraction">
        <div><strong>Estrazione</strong><span>Pesca uno dei {data.catalog.length} reagenti storici e lo converte nel suo colore/livello.</span></div>
        {lastExtraction && <output className={`extraction-result color-${lastExtraction.color}`}><i aria-hidden="true" />{lastExtraction.name}<small>{lastExtraction.colorLabel} · Lv {lastExtraction.level}</small></output>}
        <button className="button secondary" type="button" disabled={extractMutation.isPending || !data.bag.id} onClick={() => extractMutation.mutate()}>
          {extractMutation.isPending ? "Estrazione…" : "Estrai reagente"}
        </button>
      </div>
    </section>

    <section className="panel alchemy-bench-panel">
      <header className="alchemy-section-heading"><div><p className="eyebrow">Banco di distillazione</p><h2>Componi la miscela</h2></div><span className="alchemy-step">1–4 reagenti</span></header>
      <div className="alchemy-slots" aria-label="Reagenti sul banco">
        {Array.from({ length: data.rules.maxIngredients }, (_, index) => {
          const ingredient = ingredients[index];
          return ingredient
            ? <button type="button" className={`alchemy-slot filled color-${ingredient.color}`} key={index} onClick={() => setIngredients((current) => current.filter((_, itemIndex) => itemIndex !== index))} aria-label={`Rimuovi reagente ${ingredient.color} livello ${ingredient.level}`}>
                <i aria-hidden="true" /><strong>Lv {ingredient.level}</strong><small>Rimuovi</small>
              </button>
            : <div className="alchemy-slot" key={index}><span>{index + 1}</span><small>Vuoto</small></div>;
        })}
      </div>
      <fieldset className="alchemy-color-choice">
        <legend>Famiglia della pozione</legend>
        <div>{data.potionFamilies.map((entry) => <button type="button" key={entry.color} className={`color-${entry.color} ${potionColor === entry.color ? "active" : ""}`} onClick={() => setPotionColor(entry.color)}><i aria-hidden="true" />{entry.label}</button>)}</div>
      </fieldset>
      <div className="alchemy-brew-form">
        <label>Effetto
          <select value={effect} onChange={(event) => setEffect(event.target.value)}>{family?.effects.map((name) => <option key={name}>{name}</option>)}</select>
        </label>
        <label>Set alchemico
          <select value={setItemId ?? ""} onChange={(event) => setSetItemId(event.target.value ? Number(event.target.value) : null)}>
            <option value="">Nessun set · ×{formatNumber(baseSetBonus)}</option>
            {data.sets.map((entry) => <option key={entry.id} value={entry.id}>
              {entry.name} · {entry.bonusPercent > 0 ? `+${formatNumber(entry.bonusPercent)}%` : "nessun bonus"} · {entry.sourceLabel}
            </option>)}
          </select>
        </label>
      </div>
      <p className="alchemy-inline-hint">
        {data.sets.length === 0
          ? "Nessun set alchemico nello zaino, nei contenitori o fra le risorse del gruppo: si distilla a mani nude."
          : selectedSet
            ? `${selectedSet.name} · bonus ×${formatNumber(selectedSet.bonus)} · ${selectedSet.shared ? "condiviso con il gruppo" : selectedSet.sourceLabel}${selectedSet.id === data.rules.defaultSetId ? " · selezionato in automatico (qualità migliore)" : ""}`
          : "Stai distillando senza set: il bonus resta quello base."}
      </p>
      <div className="alchemy-formula-card">
        <div><span>Somma livelli</span><strong>{formatNumber(estimate.levelTotal)}</strong></div>
        <span aria-hidden="true">×</span>
        <div><span>Set + abilità {family?.label.toLowerCase()}</span><strong>{formatNumber(estimate.setBonus)} + {formatNumber(estimate.abilityBonus)}</strong></div>
        <span aria-hidden="true">=</span>
        <div className="alchemy-potency"><span>Potenza</span><strong>{formatNumber(estimate.potency)}</strong><small>{estimate.potionLevel ? `Pozione Lv ${estimate.potionLevel}` : "Sotto soglia 3"}</small></div>
      </div>
      {!hasPotionColor && ingredients.length > 0 && <p className="alchemy-inline-hint">Aggiungi almeno un reagente {family?.label.toLowerCase()} per questa famiglia.</p>}
      <button className="button primary alchemy-brew-button" type="button" disabled={brewMutation.isPending || !ingredients.length || !effect || !hasPotionColor || !data.bag.id} onClick={() => brewMutation.mutate()}>
        {brewMutation.isPending ? "Distillazione…" : "Distilla e consuma i reagenti"}
      </button>
      {lastBrew && <aside className={`alchemy-result-card color-${lastBrew.potionColor}`}>
        <p className="eyebrow">Ultima distillazione</p><strong>{lastBrew.effect} · {lastBrew.potionLevelLabel}</strong>
        <span>Potenza {formatNumber(lastBrew.potency)} · {lastBrew.potionColorLabel}</span>
      </aside>}
    </section>

    <section className="panel alchemy-reference-panel">
      <div><p className="eyebrow">Regola leggibile</p><h2>Soglie e catalogo</h2><p>{data.rules.formula}. Le soglie avanzano di 3 punti.</p></div>
      <div className="alchemy-thresholds">{data.thresholds.map((threshold) => <span className={estimate.potionLevel === threshold.level ? "active" : ""} key={threshold.level}><small>Lv {threshold.level}</small><strong>{threshold.minimumPotency}+</strong></span>)}</div>
      <details><summary>Consulta i {data.catalog.length} reagenti storici</summary><div className="alchemy-catalog">{COLOR_ORDER.map((color) => <div key={color} className={`color-${color}`}><h3><i aria-hidden="true" />{data.potionFamilies.find((entry) => entry.color === color)?.label}</h3>{[1, 2, 3, 4].map((level) => <section key={level}><strong>Livello {level}</strong><p>{data.catalog.filter((entry) => entry.color === color && entry.level === level).map((entry) => entry.name).join(" · ") || "Nessun reagente"}</p></section>)}</div>)}</div></details>
    </section>
  </div>;
}

export function CreationPage() {
  const { personaggi } = useApp();
  const [tab, setTab] = useState<CreationTab>("alchemy");
  const characterId = personaggi.giocatore.activePersonaggioId;
  const query = useQuery({
    queryKey: ["creation", characterId],
    queryFn: () => getData<AlchemyCreationData>(`/api/v1/characters/${characterId}/creation`),
    enabled: Boolean(characterId),
  });

  if (!characterId) return <div className="page creation-page"><header className="page-header"><div><p className="eyebrow">Laboratorio</p><h1>Creazione</h1></div></header><section className="panel empty-state"><h2>Scegli prima un personaggio</h2><p>Le scorte alchemiche e i moltiplicatori appartengono al personaggio attivo.</p><Link className="button primary" to="/characters">Scegli personaggio</Link></section></div>;
  return <div className="page creation-page">
    <header className="page-header"><div><p className="eyebrow">Laboratorio · {query.data?.character.name || "Personaggio attivo"}</p><h1>Creazione</h1></div><Link className="button secondary" to={`/character/${characterId}`}>Torna alla scheda</Link></header>
    <nav className="creation-tabs" aria-label="Banchi di creazione">
      <button type="button" className={tab === "alchemy" ? "active" : ""} onClick={() => setTab("alchemy")}><span>01</span><strong>Alchimia</strong><small>Operativa</small></button>
      <button type="button" className={tab === "forge" ? "active" : ""} onClick={() => setTab("forge")}><span>02</span><strong>Forgiatura</strong><small>In ricostruzione</small></button>
      <button type="button" className={tab === "enchant" ? "active" : ""} onClick={() => setTab("enchant")}><span>03</span><strong>Incantamento</strong><small>In ricostruzione</small></button>
    </nav>
    {tab === "alchemy" && (query.isLoading
      ? <section className="panel loading-state">Preparazione del banco alchemico…</section>
      : query.isError
        ? <section className="panel form-error">{(query.error as Error).message}</section>
        : query.data && <AlchemyWorkbench data={query.data} />)}
    {tab === "forge" && <EmptyWorkshop kind="forge" />}
    {tab === "enchant" && <EmptyWorkshop kind="enchant" />}
  </div>;
}
