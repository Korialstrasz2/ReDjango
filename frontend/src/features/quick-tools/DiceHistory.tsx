import { useQuery } from "@tanstack/react-query";

import { getData } from "../../lib/api";
import type { DiceHistoryData, DiceHistoryRoll } from "../../lib/types";


function rollDetail(roll: DiceHistoryRoll) {
  const dice = roll.rolls.join(", ");
  if (roll.rolls.length === 1 && !roll.modifier) return dice;
  return `${dice}${roll.modifier ? ` ${roll.modifier > 0 ? "+" : "−"} ${Math.abs(roll.modifier)}` : ""}`;
}


export function DiceHistory() {
  const historyQuery = useQuery({
    queryKey: ["diceHistory"],
    queryFn: () => getData<DiceHistoryData>("/api/v1/dice-history"),
  });

  if (historyQuery.isLoading) return <p className="empty-copy">Raccolta degli ultimi tiri…</p>;
  if (historyQuery.error) return <p className="form-error">{(historyQuery.error as Error).message}</p>;
  const rolls = historyQuery.data?.rolls || [];
  if (!rolls.length) return <p className="empty-copy">I tiri dei giocatori compariranno qui.</p>;

  return <ol className="group-dice-history-list" data-component-type="list" data-theme="default">
    {rolls.map((roll) => <li key={roll.id}>
      <span className="group-dice-history-owner">
        <strong>{roll.characterName || "Tiro libero"}</strong>
        <small>{roll.playerName}</small>
      </span>
      <span className="group-dice-history-context">
        <strong>{roll.label || roll.sourceLabel}</strong>
        <small>{roll.sourceLabel} · {roll.notation}{roll.diceSetName ? ` · ${roll.diceSetName}` : ""}</small>
      </span>
      <span className="group-dice-history-result">
        <small>{rollDetail(roll)}</small>
        <strong>{roll.total}</strong>
      </span>
      <time dateTime={roll.rolledAt}>{new Date(roll.rolledAt).toLocaleString("it-IT", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })}</time>
    </li>)}
  </ol>;
}
