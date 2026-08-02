import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import { formatNumber, TIER_LABELS, type ForgeData, type ForgeInstance } from "./craftingTypes";

type ForgeTab = "fucina" | "miglioramenti" | "fusione";
type ForgeActionData = { forge: ForgeData; forgeResult?: Record<string, unknown> };

function MaterialLadder({
  data,
  selected,
  onSelect,
}: {
  data: ForgeData;
  selected: string;
  onSelect: (key: string) => void;
}) {
  // I materiali sono sette fasce per due rami: la scala verticale rende
  // leggibile a colpo d'occhio fin dove arriva il fabbro.
  const tiers = useMemo(() => {
    const grouped = new Map<number, ForgeData["materials"]>();
    data.materials.forEach((material) => {
      grouped.set(material.tier, [...(grouped.get(material.tier) || []), material]);
    });
    return [...grouped.entries()].sort((a, b) => a[0] - b[0]);
  }, [data.materials]);

  return <div className="forge-ladder" role="table" aria-label="Materiali per fascia">
    {tiers.map(([tier, materials]) => <div className="forge-ladder-row" role="row" key={tier}>
      <span className="forge-tier" role="rowheader">{TIER_LABELS[tier]}</span>
      <div>{materials.map((material) => <button
        type="button"
        role="cell"
        key={material.key}
        className={`forge-material ${material.unlocked ? "unlocked" : "locked"} ${selected === material.key ? "active" : ""}`}
        disabled={!material.unlocked}
        onClick={() => onSelect(material.key)}
        title={material.unlocked
          ? `${material.label} · sbloccato da ${material.unlockedBy}`
          : `Richiede «${material.requiresSkill}»`}
      >
        <strong>{material.label}</strong>
        <small>{material.branch}</small>
        {material.unlocked
          ? <em className={material.quantity > 0 ? "" : "empty"}>{material.quantity}</em>
          : <em className="lock" aria-hidden="true">⌁</em>}
        {material.unlocked && !material.toolsReady && <i className="forge-warn" title="Strumenti insufficienti">!</i>}
      </button>)}</div>
    </div>)}
  </div>;
}

function Fucina({ data }: { data: ForgeData }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const unlocked = data.materials.filter((material) => material.unlocked);
  const [material, setMaterial] = useState(unlocked[0]?.key || "");
  const [category, setCategory] = useState("");

  const craft = useMutation({
    mutationFn: (blueprintItemId: number) =>
      command<ForgeActionData>("forge.craft", { characterId: data.character.id, blueprintItemId }, "creation"),
    onSuccess: (response) => {
      queryClient.setQueryData(["forge", data.character.id], response.data.forge);
      queryClient.invalidateQueries({ queryKey: ["character-sheet", data.character.id] });
      notify(response.events[0]?.message || "Oggetto forgiato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const blueprints = data.blueprints.filter(
    (entry) => entry.material === material && (!category || entry.category === category),
  );
  const categories = [...new Set(data.blueprints.filter((entry) => entry.material === material).map((entry) => entry.category))];
  const categoryLabel = (key: string) =>
    data.blueprints.find((entry) => entry.category === key)?.categoryLabel || key;

  if (!unlocked.length) return <section className="panel empty-state">
    <h2>La fucina è spenta</h2>
    <p>Serve almeno «Fabbro 2» per lavorare il primo materiale. Le fasce successive si aprono con Fabbro 3, Fabbro 4 e le specializzazioni.</p>
  </section>;

  return <div className="forge-workspace">
    <section className="panel forge-materials-panel">
      <header className="alchemy-section-heading">
        <div><p className="eyebrow">Materiali</p><h2>Sette fasce, due rami</h2></div>
        <div className="alchemy-capacity">
          <strong>{data.tools.level || "—"}</strong>
          <span>{data.tools.name ? "strumenti" : "senza strumenti"}</span>
        </div>
      </header>
      <MaterialLadder data={data} selected={material} onSelect={setMaterial} />
      {!data.tools.level && <aside className="alchemy-data-warning">
        <strong>Nessuno strumento da fabbro</strong>
        <span>Senza strumenti non si forgia nulla: servono almeno quelli di livello pari alla fascia del materiale.</span>
      </aside>}
    </section>

    <section className="panel forge-bench-panel">
      <header className="alchemy-section-heading">
        <div><p className="eyebrow">Progetti</p><h2>{data.materials.find((entry) => entry.key === material)?.label || "Scegli un materiale"}</h2></div>
        <span className="alchemy-step">{blueprints.length} modelli</span>
      </header>
      {categories.length > 1 && <div className="forge-filter-row">
        <button type="button" className={category ? "" : "active"} onClick={() => setCategory("")}>Tutti</button>
        {categories.map((key) => <button type="button" key={key} className={category === key ? "active" : ""} onClick={() => setCategory(key)}>
          {categoryLabel(key)}
        </button>)}
      </div>}
      <div className="forge-blueprint-list">
        {blueprints.map((entry) => <button
          type="button"
          key={entry.itemId}
          className="forge-blueprint"
          disabled={!entry.canForge || craft.isPending}
          onClick={() => craft.mutate(entry.itemId)}
          title={entry.blockedReason || `Forgia ${entry.name}`}
        >
          <span className="forge-blueprint-name">
            <strong>{entry.name}</strong>
            <small>{entry.categoryLabel}{entry.quantity > 1 ? ` · resa ×${entry.quantity}` : ""}</small>
          </span>
          <span className="forge-cost">
            <strong>{entry.ingots}</strong>
            <small>lingotti · {entry.hours}h</small>
          </span>
        </button>)}
        {!blueprints.length && <p className="alchemy-inline-hint">Nessun modello forgiabile in questo materiale.</p>}
      </div>
      {blueprints.some((entry) => !entry.canForge) && <p className="alchemy-inline-hint">
        {blueprints.find((entry) => !entry.canForge)?.blockedReason}
      </p>}
    </section>
  </div>;
}

function ImprovementPanel({ data, instance }: { data: ForgeData; instance: ForgeInstance }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [useFatigue, setUseFatigue] = useState(false);

  const improve = useMutation({
    mutationFn: (improvementKey: string) =>
      command<ForgeActionData>("forge.improve", {
        characterId: data.character.id,
        instanceId: instance.instanceId,
        improvementKey,
        useFatigue,
      }, "creation"),
    onSuccess: (response) => {
      queryClient.setQueryData(["forge", data.character.id], response.data.forge);
      queryClient.invalidateQueries({ queryKey: ["character-sheet", data.character.id] });
      notify(response.events[0]?.message || "Miglioramento applicato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const budget = instance.pointsMax + (useFatigue ? instance.fatigueBonus : 0);
  const remaining = Math.max(0, budget - instance.pointsSpent);

  return <>
    <div className="forge-budget">
      <div>
        <span>Punti miglioramento</span>
        <strong>{instance.pointsSpent}<small> / {budget}</small></strong>
      </div>
      <div className="forge-budget-bar" aria-hidden="true">
        {Array.from({ length: Math.max(budget, 1) }, (_, index) => <i key={index} className={index < instance.pointsSpent ? "spent" : ""} />)}
      </div>
      <p>{instance.budgetFormula}</p>
    </div>

    {instance.fatigueBonus > 0 && <label className="forge-fatigue-toggle">
      <input type="checkbox" checked={useFatigue} onChange={(event) => setUseFatigue(event.target.checked)} />
      <span>Spendi 1 Stanchezza per un punto extra <small>«Il meglio che posso»</small></span>
    </label>}

    {!instance.improvable
      ? <p className="alchemy-inline-hint">{instance.blockedReason}</p>
      : <div className="forge-improvement-grid">
          {instance.options.map((option) => {
            const affordable = option.nextCost <= remaining;
            return <button
              type="button"
              key={option.key}
              className={`forge-improvement ${option.stack ? "owned" : ""}`}
              disabled={!affordable || improve.isPending}
              onClick={() => improve.mutate(option.key)}
              title={affordable ? `Costa ${option.nextCost} punti` : `Servono ${option.nextCost} punti, ne restano ${remaining}`}
            >
              <span>
                <strong>{option.label}</strong>
                {option.mode === "rule" && <em className="forge-table-badge">regola da tavolo</em>}
              </span>
              <span className="forge-improvement-cost">
                <strong>{option.nextCost}</strong>
                {option.stack > 0 && <small>×{option.stack} presi</small>}
              </span>
            </button>;
          })}
        </div>}

    {instance.tableRules.length > 0 && <aside className="forge-rules-note">
      <strong>Regole da arbitrare</strong>
      <ul>{instance.tableRules.map((rule) => <li key={rule}>{rule}</li>)}</ul>
    </aside>}
  </>;
}

function Miglioramenti({ data }: { data: ForgeData }) {
  const [selectedId, setSelectedId] = useState(data.improvable[0]?.instanceId || 0);
  const instance = data.improvable.find((entry) => entry.instanceId === selectedId) || data.improvable[0];

  if (!data.improvable.length) return <section className="panel empty-state">
    <h2>Nessun esemplare al banco</h2>
    <p>Si migliorano solo gli oggetti usciti dalla tua fucina. Forgiane uno dalla scheda Fucina e comparirà qui.</p>
  </section>;

  return <div className="forge-workspace">
    <section className="panel forge-instance-panel">
      <header className="alchemy-section-heading">
        <div><p className="eyebrow">I tuoi esemplari</p><h2>{data.improvable.length} pezzi</h2></div>
      </header>
      <div className="forge-instance-list">
        {data.improvable.map((entry) => <button
          type="button"
          key={entry.instanceId}
          className={`forge-instance ${entry.instanceId === instance?.instanceId ? "active" : ""}`}
          onClick={() => setSelectedId(entry.instanceId)}
        >
          <strong>{entry.name}</strong>
          <small>{entry.materialLabel} · fascia {TIER_LABELS[entry.tier]} · {formatNumber(entry.weight)} peso</small>
          <em>{entry.pointsSpent}/{entry.pointsMax}</em>
        </button>)}
      </div>
    </section>

    <section className="panel forge-bench-panel">
      <header className="alchemy-section-heading">
        <div><p className="eyebrow">Miglioramenti</p><h2>{instance?.name}</h2></div>
        <span className="alchemy-step">costo ×2 a ogni ripetizione</span>
      </header>
      {instance && <ImprovementPanel data={data} instance={instance} />}
    </section>
  </div>;
}

function Fusione({ data }: { data: ForgeData }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const melt = useMutation({
    mutationFn: (instanceId: number) =>
      command<ForgeActionData>("forge.melt", { characterId: data.character.id, instanceId }, "creation"),
    onSuccess: (response) => {
      queryClient.setQueryData(["forge", data.character.id], response.data.forge);
      queryClient.invalidateQueries({ queryKey: ["character-sheet", data.character.id] });
      notify(response.events[0]?.message || "Oggetto fuso.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  if (!data.capability.canMelt) return <section className="panel empty-state">
    <h2>Ti manca «Scioglitore»</h2>
    <p>Senza quell'abilità non puoi fondere gli oggetti per recuperarne il materiale.</p>
  </section>;

  return <section className="panel">
    <header className="alchemy-section-heading">
      <div><p className="eyebrow">Scioglitore</p><h2>Recupera il materiale</h2></div>
      <span className="alchemy-step">torna il metallo speso per crearlo</span>
    </header>
    <div className="forge-instance-list wide">
      {data.improvable.map((entry) => <button
        type="button"
        key={entry.instanceId}
        className="forge-instance"
        disabled={melt.isPending}
        onClick={() => melt.mutate(entry.instanceId)}
      >
        <strong>{entry.name}</strong>
        <small>{entry.materialLabel} · {entry.pointsSpent} punti spesi andranno persi</small>
        <em>fondi</em>
      </button>)}
      {!data.improvable.length && <p className="alchemy-inline-hint">Non hai esemplari da fondere.</p>}
    </div>
  </section>;
}

export function ForgeWorkbench({ characterId }: { characterId: number }) {
  const [tab, setTab] = useState<ForgeTab>("fucina");
  const query = useQuery({
    queryKey: ["forge", characterId],
    queryFn: () => getData<ForgeData>(`/api/v1/characters/${characterId}/creation/forge`),
    enabled: Boolean(characterId),
  });

  if (query.isLoading) return <section className="panel loading-state">Accensione della fucina…</section>;
  if (query.isError) return <section className="panel form-error">{(query.error as Error).message}</section>;
  if (!query.data) return null;
  const data = query.data;

  return <div className="crafting-bench">
    <nav className="crafting-subtabs" aria-label="Banchi di forgiatura">
      <button type="button" className={tab === "fucina" ? "active" : ""} onClick={() => setTab("fucina")}>Fucina</button>
      <button type="button" className={tab === "miglioramenti" ? "active" : ""} onClick={() => setTab("miglioramenti")}>
        Miglioramenti{data.improvable.length ? <em>{data.improvable.length}</em> : null}
      </button>
      <button type="button" className={tab === "fusione" ? "active" : ""} onClick={() => setTab("fusione")}>Fusione</button>
    </nav>

    {tab === "fucina" && <Fucina data={data} />}
    {tab === "miglioramenti" && <Miglioramenti data={data} />}
    {tab === "fusione" && <Fusione data={data} />}

    {data.tableRules.length > 0 && <section className="panel forge-rules-panel">
      <p className="eyebrow">Abilità che il motore non calcola</p>
      <ul>{data.tableRules.map((rule) => <li key={rule.skill}><strong>{rule.skill}</strong> — {rule.text}</li>)}</ul>
    </section>}
  </div>;
}
