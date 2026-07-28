import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import { playRollSound } from "../../lib/dice";
import { useDiceThrow } from "../../lib/diceThrow";
import type { CompetenceCatalog, CompetenceEntry, CompetenceRoll, DiceSetsData } from "../../lib/types";
import { DiceHistory } from "../quick-tools/DiceHistory";
import { DiceVisual } from "../quick-tools/DiceVisual";
import { latestDieValue, rollEquation, techniqueEnergyCost, techniqueUnlocked, type CompetenceTechnique } from "./mechanics";

type CompetenceActionData = { competencies: CompetenceCatalog; competenceRoll?: CompetenceRoll | null };
type EditableTrack = "base" | "mastery";
type SummaryTab = "current" | "guidelines";
type HistoryTab = "character" | "group";
type MutationInput =
  | { action: "competencies.upgrade"; payload: { characterId: number; competenceKey: string; track: EditableTrack; targetRank: number } }
  | { action: "competencies.roll"; payload: { characterId: number; competenceKey: string; technique: CompetenceTechnique; diceSetId?: number } }
  | { action: "competencies.reroll"; payload: { characterId: number; rollId: number } };

const SEGMENTS = Array.from({ length: 7 }, (_, index) => index + 1);

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value}`;
}

function techniqueLabel(technique: CompetenceTechnique) {
  if (technique === "focus") return "impulso";
  if (technique === "amplify") return "impulso maggiore";
  return "tiro normale";
}

function SegmentBar({ value, tone, label }: { value: number; tone: "base" | "mastery" | "extra"; label: string }) {
  const filled = tone === "extra" ? Math.min(7, Math.abs(value)) : Math.max(0, Math.min(7, value));
  return <span className={`competence-segments ${tone} ${value < 0 ? "negative" : ""}`} aria-label={`${label}: ${tone === "extra" ? signed(value) : `${value} su 7`}`}>
    {SEGMENTS.map((rank) => <i key={rank} className={rank <= filled ? "filled" : ""} />)}
  </span>;
}

function CompactCard({ entry, active, onSelect }: { entry: CompetenceEntry; active: boolean; onSelect: () => void }) {
  return <button type="button" className={`competence-card ${active ? "active" : ""}`} onClick={onSelect} aria-pressed={active} data-competence-key={entry.key}>
    <span className="competence-card-icon"><img src={entry.iconUrl} alt="" /></span>
    <span className="competence-card-copy"><strong>{entry.name}<small> - {entry.attribute || entry.category}</small></strong></span>
    <span className="competence-card-total"><small>d{entry.dieSides}</small><strong>{signed(entry.rollModifier)}</strong></span>
    <span className="competence-card-bars">
      <span><b>B</b><SegmentBar value={entry.baseRank} tone="base" label="Base" /></span>
      <span><b>M</b><SegmentBar value={entry.masteryRank} tone="mastery" label="Maestria" /></span>
      <span><b>E</b><SegmentBar value={entry.effectiveExtra} tone="extra" label="Extra" /><em>{signed(entry.effectiveExtra)}</em></span>
    </span>
  </button>;
}

function EditableRankTrack({
  label,
  tone,
  value,
  nextCost,
  availableXp,
  disabled,
  onAdjust,
}: {
  label: string;
  tone: EditableTrack;
  value: number;
  nextCost: number | null;
  availableXp: number;
  disabled: boolean;
  onAdjust: (targetRank: number) => void;
}) {
  const refund = value;
  const canIncrease = nextCost != null && nextCost <= availableXp;
  return <section className={`competence-track ${tone}`} data-component-type="field" data-theme="arcane">
    <header><span>{label}</span><strong>{value}</strong></header>
    <SegmentBar value={value} tone={tone} label={label} />
    <footer>
      <button type="button" className="competence-rank-control" aria-label={`Riduci ${label} a ${Math.max(0, value - 1)}${value > 0 ? ` e recupera ${refund} PE` : ""}`} title={value > 0 ? `Recupera ${refund} PE` : `${label} è già a zero`} disabled={disabled || value <= 0} onClick={() => onAdjust(value - 1)}>−</button>
      <span>{value > 0 ? `− restituisce ${refund} PE` : "grado minimo"}<i />{nextCost == null ? "grado massimo" : `+ costa ${nextCost} PE`}</span>
      <button type="button" className="competence-rank-control" aria-label={`Aumenta ${label} a ${Math.min(7, value + 1)}${nextCost != null ? ` al costo di ${nextCost} PE` : ""}`} title={nextCost == null ? `${label} è già al massimo` : `Spendi ${nextCost} PE`} disabled={disabled || !canIncrease} onClick={() => onAdjust(value + 1)}>+</button>
    </footer>
  </section>;
}

function ExtraTrack({ entry }: { entry: CompetenceEntry }) {
  return <section className="competence-track extra readonly" data-component-type="field" data-theme="muted">
    <header><span>Extra</span><strong>{signed(entry.effectiveExtra)}</strong></header>
    <SegmentBar value={entry.effectiveExtra} tone="extra" label="Extra effettivo" />
  </section>;
}

export function CompetenciesPage() {
  const { personaggi, settings, notify } = useApp();
  const queryClient = useQueryClient();
  const characterId = personaggi.giocatore.activePersonaggioId;
  const boardRef = useRef<HTMLDivElement | null>(null);
  const dieRef = useRef<HTMLDivElement | null>(null);
  const resolvedRollRef = useRef<CompetenceRoll | null>(null);
  const physicsSettledRef = useRef(false);
  const [selectedKey, setSelectedKey] = useState("");
  const [summaryTab, setSummaryTab] = useState<SummaryTab>("current");
  const [historyTab, setHistoryTab] = useState<HistoryTab>("character");
  const [technique, setTechnique] = useState<CompetenceTechnique>("standard");
  const [rolling, setRolling] = useState(false);
  const [rollingValue, setRollingValue] = useState(1);
  const [lastRoll, setLastRoll] = useState<CompetenceRoll | null>(null);
  const catalogQuery = useQuery({ queryKey: ["competencies", characterId], queryFn: () => getData<CompetenceCatalog>(`/api/v1/characters/${characterId}/competencies`), enabled: Boolean(characterId) });
  const diceSetsQuery = useQuery({ queryKey: ["diceSets", "active"], queryFn: () => getData<DiceSetsData>("/api/v1/dice-sets"), enabled: Boolean(characterId) });
  const data = catalogQuery.data;
  const selected = data?.competencies.find((entry) => entry.key === selectedKey) || data?.competencies[0];
  const reducedMotion = settings.ui["accessibility.reduced_motion"] === true;
  const showGroupHistory = settings.security.canManageGameData && settings.ui["master.show_hidden_rolls"] !== false;

  useEffect(() => { if (!selectedKey && data?.competencies[0]) setSelectedKey(data.competencies[0].key); }, [data, selectedKey]);
  useEffect(() => { if (selected && !techniqueUnlocked(selected.masteryRank, technique)) setTechnique("standard"); }, [selected, technique]);
  useEffect(() => { if (!showGroupHistory) setHistoryTab("character"); }, [showGroupHistory]);

  const completeResolvedRoll = () => {
    const resolved = resolvedRollRef.current;
    if (!physicsSettledRef.current || !resolved) return;
    resolvedRollRef.current = null;
    setLastRoll(resolved);
    setRollingValue(latestDieValue(resolved) ?? 1);
    setRolling(false);
  };

  useDiceThrow({
    enabled: rolling,
    boardRef,
    dieRef,
    sides: selected?.dieSides ?? 20,
    animationDisabled: reducedMotion || settings.ui["dice.animation"] === false,
    onFaceChange: setRollingValue,
    onSettle: () => {
      physicsSettledRef.current = true;
      completeResolvedRoll();
    },
  });

  const mutation = useMutation({
    mutationFn: (input: MutationInput) => command<CompetenceActionData>(input.action, input.payload, "competenze"),
    onMutate: (input) => {
      if (input.action === "competencies.roll" || input.action === "competencies.reroll") {
        resolvedRollRef.current = null;
        physicsSettledRef.current = false;
        setRollingValue(Math.floor(Math.random() * (selected?.dieSides ?? 20)) + 1);
        setRolling(true);
      }
    },
    onSuccess: async (result, input) => {
      queryClient.setQueryData(["competencies", characterId], result.data.competencies);
      if (result.data.competenceRoll) {
        const resolved = result.data.competenceRoll;
        void queryClient.invalidateQueries({ queryKey: ["diceHistory"] });
        if (settings.ui["dice.sound"] !== false) playRollSound();
        resolvedRollRef.current = resolved;
        completeResolvedRoll();
      } else setRolling(false);
      await Promise.all([queryClient.invalidateQueries({ queryKey: ["character-sheet", characterId] }), queryClient.invalidateQueries({ queryKey: ["personaggi"] })]);
      if (input.action !== "competencies.roll") notify(result.events[0]?.message || "Competenza aggiornata.");
    },
    onError: (error: Error) => {
      resolvedRollRef.current = null;
      setRolling(false);
      notify(error.message, "error");
    },
  });

  const diceSet = useMemo(() => {
    if (!selected || !diceSetsQuery.data) return undefined;
    const preferredSlug = String(settings.ui["dice.default_set"] || "");
    const sets = diceSetsQuery.data.diceSets;
    return sets.find((entry) => entry.slug === preferredSlug && entry.dice.includes(selected.dieSides)) || sets.find((entry) => entry.id === diceSetsQuery.data?.defaultDiceSetId && entry.dice.includes(selected.dieSides)) || sets.find((entry) => entry.dice.includes(selected.dieSides));
  }, [diceSetsQuery.data, selected, settings.ui]);

  if (!characterId) return <div className="page competencies-empty"><section className="hero-panel"><div><p className="eyebrow">Competenze</p><h1>Scegli prima un personaggio</h1><p>Le competenze e i tiri appartengono al personaggio attivo.</p></div><Link className="button primary" to="/characters">Scegli personaggio</Link></section></div>;
  if (catalogQuery.isLoading || !data || !selected) return <div className="page competencies-loading"><div className="competence-sigil">✧</div><p>Le competenze prendono forma…</p></div>;
  if (catalogQuery.error) return <div className="page"><section className="panel"><h1>Competenze non disponibili</h1><p className="form-error">{(catalogQuery.error as Error).message}</p></section></div>;

  const energyCost = techniqueEnergyCost(selected.masteryRank, technique);
  const rollDisabled = mutation.isPending || rolling || !diceSet;
  const shownRoll = lastRoll?.competenceKey === selected.key ? lastRoll : data.recentRolls.find((entry) => entry.competenceKey === selected.key) || null;
  const dieValue = rolling ? rollingValue : latestDieValue(shownRoll) ?? `d${selected.dieSides}`;
  const selectedIndex = Math.max(0, data.competencies.findIndex((entry) => entry.key === selected.key));
  const backdrop = data.backgrounds[selectedIndex % Math.max(1, data.backgrounds.length)];
  const backdropStyle = { "--competence-backdrop": backdrop ? `url(${backdrop})` : "none" } as CSSProperties;
  const dicePalette = { "--dice-surface": diceSet?.surfaceColor || "#6d2637", "--dice-accent": diceSet?.accentColor || "#d9b96f", "--dice-text": diceSet?.textColor || "#fff6dc" } as CSSProperties;

  const selectCompetence = (key: string) => {
    setSelectedKey(key);
    setTechnique("standard");
    setLastRoll(null);
    if (window.matchMedia("(max-width: 900px)").matches) document.querySelector(".competence-detail")?.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
  };
  const adjustRank = (track: EditableTrack, targetRank: number) => {
    const currentRank = track === "base" ? selected.baseRank : selected.masteryRank;
    if (targetRank < currentRank) {
      // Intentionally advisory only: no removal counter is stored or checked. This warning is meant solely to discourage repeated reductions.
      const accepted = window.confirm("È possibile rimuovere punti competenze massimo 3 volte a personaggio. Vuoi continuare?");
      if (!accepted) return;
    }
    mutation.mutate({ action: "competencies.upgrade", payload: { characterId, competenceKey: selected.key, track, targetRank } });
  };
  const rollSelectedCompetence = () => {
    if (energyCost > data.character.energyCurrent) {
      const accepted = window.confirm("Usare Energia farà aumentare la stanchezza. Continuare?");
      if (!accepted) return;
    }
    mutation.mutate({ action: "competencies.roll", payload: { characterId, competenceKey: selected.key, technique, diceSetId: diceSet?.id } });
  };

  return <div className="page competencies-page" style={backdropStyle} data-component-type="competencies-workspace" data-theme="arcane">
    <section className="competence-workbench">
      <aside className="competence-index" aria-label="Tutte le competenze" data-component-type="list" data-theme="default">
        <div>{data.competencies.map((entry) => <CompactCard key={entry.key} entry={entry} active={entry.key === selected.key} onSelect={() => selectCompetence(entry.key)} />)}</div>
      </aside>

      <main className="competence-detail" data-selected-competence={selected.key}>
        <article className="competence-focus-main" style={backdropStyle} data-component-type="panel" data-theme="default">
          <header>
            <div className="competence-focus-icon"><span /><img src={selected.iconUrl} alt="" /></div>
            <div><p className="eyebrow">{selected.attribute || selected.category}</p><h2>{selected.name}</h2></div>
            <div className="competence-modifier"><small>Modificatore</small><strong>{signed(selected.rollModifier)}</strong><span>d{selected.dieSides}</span></div>
          </header>
          <nav className="competence-summary-tabs" role="tablist" aria-label="Riepilogo della competenza" data-component-type="tabset" data-theme="gold">
            <button type="button" role="tab" aria-selected={summaryTab === "current"} className={summaryTab === "current" ? "active" : ""} onClick={() => setSummaryTab("current")}>Attuale</button>
            <button type="button" role="tab" aria-selected={summaryTab === "guidelines"} className={summaryTab === "guidelines" ? "active" : ""} onClick={() => setSummaryTab("guidelines")}>Linee guida</button>
          </nav>
          {summaryTab === "current" ? <div className="competence-tracks" role="tabpanel">
            <EditableRankTrack label="Base" tone="base" value={selected.baseRank} nextCost={selected.nextBaseCost ?? null} availableXp={data.character.xpAvailable} disabled={mutation.isPending} onAdjust={(targetRank) => adjustRank("base", targetRank)} />
            <EditableRankTrack label="Maestria" tone="mastery" value={selected.masteryRank} nextCost={selected.nextMasteryCost ?? null} availableXp={data.character.xpAvailable} disabled={mutation.isPending} onAdjust={(targetRank) => adjustRank("mastery", targetRank)} />
            <ExtraTrack entry={selected} />
          </div> : <section className="competence-summary-guidelines competence-thresholds" role="tabpanel" aria-label="Interpretazioni del risultato">
            {selected.thresholds.length ? <ol>{selected.thresholds.map((threshold) => <li key={threshold.score}><strong>{threshold.score}+</strong><span>{threshold.text}</span></li>)}</ol> : <p className="empty-copy">Nessun esempio numerico per questa competenza.</p>}
          </section>}
        </article>

        <section className="competence-understage">
          <aside className="competence-roll-workspace" style={dicePalette} data-component-type="panel" data-theme="arcane">
            <div ref={boardRef} className={`competence-dice-stage ${rolling ? "rolling" : ""}`} aria-live="polite">
              <header><h2>{selected.name}</h2><p>{rollEquation(selected, technique)}</p></header>
              <span className="competence-rune-ring" aria-hidden="true">✦　✧　✦　✧</span>
              <DiceVisual ref={dieRef} sides={selected.dieSides} value={dieValue} texture={diceSet?.textures.find((entry) => entry.sides === selected.dieSides)} rolling={rolling} className="competence-die" />
              {!rolling && shownRoll && <div className="competence-roll-result"><small>Ultimo risultato</small><strong>{shownRoll.total}</strong><span>{latestDieValue(shownRoll)} al dado · {signed(shownRoll.modifier)} mod.</span></div>}
            </div>
            <div className="competence-techniques">{([["standard", "Tiro normale", "Nessun costo"], ["focus", "Impulso +1", `${techniqueEnergyCost(selected.masteryRank, "focus")} Energia`], ["amplify", "Impulso maggiore +2", `${techniqueEnergyCost(selected.masteryRank, "amplify")} Energia`]] as Array<[CompetenceTechnique, string, string]>).map(([key, label, cost]) => <button key={key} type="button" className={technique === key ? "active" : ""} disabled={!techniqueUnlocked(selected.masteryRank, key)} onClick={() => setTechnique(key)}><strong>{label}</strong><span>{techniqueUnlocked(selected.masteryRank, key) ? cost : `Maestria ${key === "focus" ? 1 : 3}`}</span></button>)}</div>
            <button type="button" className="button primary competence-roll-button" data-energy-overdraw={energyCost > data.character.energyCurrent ? "true" : "false"} disabled={rollDisabled} onClick={rollSelectedCompetence}>{rolling ? "Il dado è in volo…" : `Tira d${selected.dieSides}`}</button>
            {shownRoll?.canReroll && <button type="button" className="button secondary competence-reroll-button" disabled={mutation.isPending || rolling} onClick={() => mutation.mutate({ action: "competencies.reroll", payload: { characterId, rollId: shownRoll.id } })}>Rilancia gratis · {shownRoll.rerollsRemaining} rimasti</button>}
            {!diceSet && <p className="form-error">Nessun set attivo contiene il d{selected.dieSides}.</p>}
          </aside>
        </section>

        <article className="competence-mastery-road" aria-label="Gradi di maestria" data-component-type="panel" data-theme="arcane">
          <ol>{selected.masteryFeatures.map((feature) => <li key={feature.key} className={feature.unlocked ? "unlocked" : "locked"}><strong>{feature.rank}</strong><span><b>{feature.title}</b><small>{feature.description}</small></span><i>{feature.unlocked ? "Attiva" : "Chiusa"}</i></li>)}</ol>
        </article>

        <section className="competence-history" data-component-type="panel" data-theme="default">
          <header><div><p className="eyebrow">Cronaca recente</p><h2>{historyTab === "group" ? "Tiri del gruppo" : "Ultimi tiri"}</h2></div>{showGroupHistory && <nav className="competence-history-tabs" role="tablist" aria-label="Cronologia dei tiri" data-component-type="tabset" data-theme="gold"><button type="button" role="tab" aria-selected={historyTab === "character"} className={historyTab === "character" ? "active" : ""} onClick={() => setHistoryTab("character")}>Personaggio</button><button type="button" role="tab" aria-selected={historyTab === "group"} className={historyTab === "group" ? "active" : ""} onClick={() => setHistoryTab("group")}>Tiri del gruppo</button></nav>}</header>
          {historyTab === "group" && showGroupHistory ? <DiceHistory /> : data.recentRolls.length ? <div>{data.recentRolls.map((roll) => <button key={roll.id} type="button" onClick={() => selectCompetence(roll.competenceKey)}><span>{roll.competenceName}<small>d{roll.dieSides} · {techniqueLabel(roll.technique as CompetenceTechnique)}</small></span><strong>{roll.total}</strong><time>{roll.rolledAt ? new Date(roll.rolledAt).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" }) : ""}</time></button>)}</div> : <p className="empty-copy">I tiri di competenza compariranno qui.</p>}
        </section>
      </main>
    </section>
  </div>;
}
