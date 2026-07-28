import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { command, getData } from "../../lib/api";
import { playRollSound } from "../../lib/dice";
import { useDiceThrow } from "../../lib/diceThrow";
import type { CharacterSheet, DiceRoll, DiceSetsData, SettingsData } from "../../lib/types";
import { DiceHistory } from "./DiceHistory";
import { DiceVisual } from "./DiceVisual";

type Props = {
  characterId: number | null;
  settings: SettingsData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

function equation(roll: DiceRoll) {
  const die = roll.rolls[0];
  if (!roll.modifier) return `${die}`;
  return `${die} ${roll.modifier > 0 ? "+" : "−"} ${Math.abs(roll.modifier)} = ${roll.total}`;
}

export function DiceTool({ characterId, settings, notify }: Props) {
  const queryClient = useQueryClient();
  const boardRef = useRef<HTMLElement | null>(null);
  const dieRef = useRef<HTMLDivElement | null>(null);
  const resolvedRollRef = useRef<DiceRoll | null>(null);
  const physicsSettledRef = useRef(false);
  const setsQuery = useQuery({ queryKey: ["diceSets", "active"], queryFn: () => getData<DiceSetsData>("/api/v1/dice-sets") });
  const characterQuery = useQuery({
    queryKey: ["character-sheet", characterId],
    queryFn: () => getData<{ character: CharacterSheet }>(`/api/v1/characters/${characterId}/sheet`),
    enabled: Boolean(characterId)
  });
  const preferredSlug = String(settings.ui["dice.default_set"] || "");
  const preferred = setsQuery.data?.diceSets.find((entry) => entry.slug === preferredSlug);
  const fallback = setsQuery.data?.diceSets.find((entry) => entry.id === setsQuery.data?.defaultDiceSetId) || setsQuery.data?.diceSets[0];
  const selected = preferred || fallback;
  const [history, setHistory] = useState<DiceRoll[]>([]);
  const [rolling, setRolling] = useState(false);
  const [activeSides, setActiveSides] = useState(20);
  const [activeTab, setActiveTab] = useState<"roll" | "history">("roll");
  const [rollingValue, setRollingValue] = useState(1);
  const showGroupHistory = settings.security.canManageGameData && settings.ui["master.show_hidden_rolls"] !== false;

  useEffect(() => {
    if (selected && !selected.dice.includes(activeSides)) setActiveSides(selected.dice.includes(20) ? 20 : selected.dice[0]);
  }, [activeSides, selected]);

  useEffect(() => { if (!showGroupHistory) setActiveTab("roll"); }, [showGroupHistory]);

  const completeResolvedRoll = () => {
    const value = resolvedRollRef.current;
    if (!physicsSettledRef.current || !value) return;
    resolvedRollRef.current = null;
    setRollingValue(value.rolls[0]);
    setHistory((current) => [value, ...current].slice(0, 12));
    setRolling(false);
  };

  useDiceThrow({
    enabled: rolling,
    boardRef,
    dieRef,
    sides: activeSides,
    animationDisabled: settings.ui["dice.animation"] === false || settings.ui["accessibility.reduced_motion"] === true,
    onFaceChange: setRollingValue,
    onSettle: () => {
      physicsSettledRef.current = true;
      completeResolvedRoll();
    },
  });

  const roll = useMutation({
    mutationFn: ({ sides, rollModifier = 0 }: { sides: number; rollModifier?: number }) => command<{ diceRoll: DiceRoll }>("dice.roll", {
      sides,
      count: 1,
      modifier: rollModifier,
      diceSetId: selected?.id,
      characterId: characterId || undefined
    }, "dice"),
    onMutate: ({ sides }) => {
      resolvedRollRef.current = null;
      physicsSettledRef.current = false;
      setActiveSides(sides);
      setRollingValue(Math.floor(Math.random() * sides) + 1);
      setRolling(true);
    },
    onSuccess: (result) => {
      const value = result.data.diceRoll;
      void queryClient.invalidateQueries({ queryKey: ["diceHistory"] });
      if (settings.ui["dice.sound"] !== false) playRollSound();
      resolvedRollRef.current = value;
      completeResolvedRoll();
    },
    onError: (error: Error) => {
      resolvedRollRef.current = null;
      setRolling(false);
      notify(error.message, "error");
    }
  });

  const lastRoll = history[0];
  const shownRoll = lastRoll?.sides === activeSides ? lastRoll : null;
  const texture = selected?.textures.find((entry) => entry.sides === activeSides);
  const palette = useMemo(() => ({
    "--dice-surface": selected?.surfaceColor || "#7f2434",
    "--dice-accent": selected?.accentColor || "#d0a95b",
    "--dice-text": selected?.textColor || "#fff4d6"
  } as CSSProperties), [selected]);

  if (setsQuery.isLoading) return <p className="empty-copy">Preparazione dei dadi…</p>;
  if (!selected) return <p className="form-error">Non ci sono set di dadi attivi. Un amministratore deve crearne uno.</p>;
  return <div className="dice-tool" style={palette}>
    {showGroupHistory && <nav className="dice-tool-tabs" role="tablist" aria-label="Sezioni dei dadi" data-component-type="tabset" data-theme="gold">
      <button type="button" role="tab" aria-selected={activeTab === "roll"} className={activeTab === "roll" ? "active" : ""} onClick={() => setActiveTab("roll")}>Tiro</button>
      <button type="button" role="tab" aria-selected={activeTab === "history"} className={activeTab === "history" ? "active" : ""} onClick={() => setActiveTab("history")}>Tiri del gruppo</button>
    </nav>}
    {activeTab === "history" && showGroupHistory ? <section className="group-dice-history" role="tabpanel" data-component-type="panel" data-theme="default">
      <header><div><p className="eyebrow">Cronaca condivisa</p><h3>Ultimi 100 tiri</h3></div><span>Giocatore · personaggio · orario</span></header>
      <DiceHistory />
    </section> : <>
    <section ref={boardRef} className={`dice-altar ${rolling ? "rolling" : "settled"}`} aria-live="polite">
      <div className="dice-altar-runes" aria-hidden="true">✦</div>
      <p>{rolling ? `Il d${activeSides} attraversa il fato…` : shownRoll ? `${shownRoll.notation} · ${shownRoll.diceSetName}` : selected.name}</p>
      <DiceVisual ref={dieRef} sides={activeSides} value={rolling ? rollingValue : shownRoll?.rolls[0] ?? "—"} texture={texture} rolling={rolling} className="dice-hero" />
      <div className="dice-equation">
        {!rolling && shownRoll && <><span>Tiro</span><strong>{equation(shownRoll)}</strong>{shownRoll.modifier !== 0 && <small>Totale finale</small>}</>}
      </div>
    </section>
    <div className="dice-grid" aria-label="Dadi disponibili">{selected.dice.map((side) => <button key={side} type="button" disabled={roll.isPending || rolling} onClick={() => roll.mutate({ sides: side })} aria-label={`Tira d${side}`}>
      <DiceVisual sides={side} value={`d${side}`} texture={selected.textures.find((entry) => entry.sides === side)} />
      <small>Tira</small>
    </button>)}</div>
    {characterQuery.data?.character.diceModifiers?.length ? <section className="modifier-throws"><header><h3>Tiri del personaggio</h3><span>d10 + bonus</span></header><div>{characterQuery.data.character.diceModifiers.map((entry) => <button type="button" key={entry.key} disabled={roll.isPending || rolling || !selected.dice.includes(10)} onClick={() => roll.mutate({ sides: 10, rollModifier: entry.value })}><strong>{entry.label}</strong><span>d10 {entry.value >= 0 ? "+" : "−"} {Math.abs(entry.value)}</span></button>)}</div></section> : null}
    <section className="dice-history"><header><h3>Ultimi tiri</h3>{history.length > 0 && <button type="button" onClick={() => setHistory([])}>Pulisci</button>}</header>{history.length ? <ol>{history.map((entry, index) => <li key={`${entry.rolledAt}-${index}`}><span>{entry.notation}</span><strong>{equation(entry)}</strong><time>{new Date(entry.rolledAt).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}</time></li>)}</ol> : <p className="empty-copy">La cronaca dei tiri di questa sessione apparirà qui.</p>}</section>
    </>}
  </div>;
}
