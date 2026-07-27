import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { command, getData } from "../../lib/api";
import type { CharacterSheet, DiceRoll, DiceSetsData, SettingsData } from "../../lib/types";
import { DiceSetManager } from "./DiceSetManager";
import { DiceVisual } from "./DiceVisual";

type Props = {
  characterId: number | null;
  settings: SettingsData;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

function playRollSound() {
  const AudioContextClass = window.AudioContext;
  if (!AudioContextClass) return;
  const context = new AudioContextClass();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = "triangle";
  oscillator.frequency.setValueAtTime(132, context.currentTime);
  oscillator.frequency.exponentialRampToValueAtTime(54, context.currentTime + .22);
  gain.gain.setValueAtTime(.06, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(.001, context.currentTime + .24);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + .25);
  oscillator.addEventListener("ended", () => context.close());
}

function equation(roll: DiceRoll) {
  const die = roll.rolls[0];
  if (!roll.modifier) return `${die}`;
  return `${die} ${roll.modifier > 0 ? "+" : "−"} ${Math.abs(roll.modifier)} = ${roll.total}`;
}

export function DiceTool({ characterId, settings, notify }: Props) {
  const settleTimer = useRef<number | null>(null);
  const throwDurationRef = useRef(620);
  const throwStartedAtRef = useRef(0);
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
  const [rollingValue, setRollingValue] = useState(1);
  const [throwProfile, setThrowProfile] = useState({ bounces: 4, direction: 1, duration: 620 });

  useEffect(() => {
    if (selected && !selected.dice.includes(activeSides)) setActiveSides(selected.dice.includes(20) ? 20 : selected.dice[0]);
  }, [activeSides, selected]);

  useEffect(() => {
    if (!rolling) return;
    const interval = window.setInterval(() => setRollingValue(Math.floor(Math.random() * activeSides) + 1), 48);
    return () => window.clearInterval(interval);
  }, [activeSides, rolling]);

  useEffect(() => () => { if (settleTimer.current) window.clearTimeout(settleTimer.current); }, []);

  const roll = useMutation({
    mutationFn: ({ sides, rollModifier = 0 }: { sides: number; rollModifier?: number }) => command<{ diceRoll: DiceRoll }>("dice.roll", {
      sides,
      count: 1,
      modifier: rollModifier,
      diceSetId: selected?.id,
      characterId: characterId || undefined
    }, "dice"),
    onMutate: ({ sides }) => {
      if (settleTimer.current) window.clearTimeout(settleTimer.current);
      const bounces = Math.floor(Math.random() * 5) + 2;
      const direction = Math.random() < .5 ? -1 : 1;
      const duration = 360 + bounces * 65;
      throwDurationRef.current = duration;
      throwStartedAtRef.current = performance.now();
      setThrowProfile({ bounces, direction, duration });
      setActiveSides(sides);
      setRollingValue(Math.floor(Math.random() * sides) + 1);
      setRolling(true);
    },
    onSuccess: (result) => {
      const value = result.data.diceRoll;
      if (settings.ui["dice.sound"] !== false) playRollSound();
      const settle = () => {
        setRollingValue(value.rolls[0]);
        setHistory((current) => [value, ...current].slice(0, 12));
        setRolling(false);
      };
      if (settings.ui["dice.animation"] === false || settings.ui["accessibility.reduced_motion"] === true) settle();
      else {
        const elapsed = performance.now() - throwStartedAtRef.current;
        settleTimer.current = window.setTimeout(settle, Math.max(0, throwDurationRef.current - elapsed));
      }
    },
    onError: (error: Error) => { setRolling(false); notify(error.message, "error"); }
  });

  const lastRoll = history[0];
  const shownRoll = lastRoll?.sides === activeSides ? lastRoll : null;
  const texture = selected?.textures.find((entry) => entry.sides === activeSides);
  const throwStyle = {
    "--throw-duration": `${throwProfile.duration}ms`,
    "--throw-edge-1": `${throwProfile.direction * 165}px`,
    "--throw-edge-2": `${throwProfile.direction * -145}px`,
    "--throw-edge-3": `${throwProfile.direction * 122}px`,
    "--throw-edge-4": `${throwProfile.direction * -98}px`,
    "--throw-edge-5": `${throwProfile.direction * 72}px`,
    "--throw-edge-6": `${throwProfile.direction * -46}px`
  } as CSSProperties;
  const palette = useMemo(() => ({
    "--dice-surface": selected?.surfaceColor || "#7f2434",
    "--dice-accent": selected?.accentColor || "#d0a95b",
    "--dice-text": selected?.textColor || "#fff4d6"
  } as CSSProperties), [selected]);

  if (setsQuery.isLoading) return <p className="empty-copy">Preparazione dei dadi…</p>;
  if (!selected) return <p className="form-error">Non ci sono set di dadi attivi. Un amministratore deve crearne uno.</p>;
  return <div className="dice-tool" style={palette}>
    <section className={`dice-altar ${rolling ? "rolling" : "settled"}`} style={throwStyle} aria-live="polite">
      <div className="dice-altar-runes" aria-hidden="true">✦</div>
      <p>{rolling ? `Il d${activeSides} attraversa il fato…` : shownRoll ? `${shownRoll.notation} · ${shownRoll.diceSetName}` : selected.name}</p>
      <DiceVisual sides={activeSides} value={rolling ? rollingValue : shownRoll?.rolls[0] ?? "—"} texture={texture} rolling={rolling} className={`dice-hero ${rolling ? `dice-throw-${throwProfile.bounces}` : ""}`} />
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
    {settings.security.canManageAdminSettings && <details className="inline-admin-tool"><summary>Gestisci i set di dadi</summary><DiceSetManager notify={notify} compact /></details>}
  </div>;
}
