import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type { DiceHistoryData } from "../../lib/types";

const PAGE_SIZE = 50;
const PERIODS = [
  { value: 0, label: "Sempre" },
  { value: 1, label: "Ultime 24 ore" },
  { value: 7, label: "Ultimi 7 giorni" },
  { value: 30, label: "Ultimi 30 giorni" },
];

export function DiceHistoryPanel({ notify }: { notify: (message: string, kind?: "success" | "error" | "info") => void }) {
  const { settings } = useApp();
  const queryClient = useQueryClient();
  const drawerHistoryVisible = settings.ui["master.show_hidden_rolls"] !== false;
  const [player, setPlayer] = useState("");
  const [source, setSource] = useState("");
  const [sinceDays, setSinceDays] = useState(0);
  const [offset, setOffset] = useState(0);
  const [showStatistics, setShowStatistics] = useState(false);
  const [purgeDays, setPurgeDays] = useState(30);

  const parameters = new URLSearchParams({
    player,
    source,
    since_days: String(sinceDays),
    limit: String(PAGE_SIZE),
    offset: String(offset),
    statistics: String(showStatistics),
  });
  const historyQuery = useQuery({
    queryKey: ["dice-history-admin", parameters.toString()],
    queryFn: () => getData<DiceHistoryData>(`/api/v1/dice-history?${parameters}`),
    placeholderData: (previous) => previous,
  });
  const purgeMutation = useMutation({
    mutationFn: () => command<{ management?: { archived?: number } }>("diceHistory.purge", { olderThanDays: purgeDays }, "dice-history-admin"),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ["dice-history-admin"] });
      await queryClient.invalidateQueries({ queryKey: ["diceHistory"] });
      setOffset(0);
      notify(`${response.data.management?.archived ?? 0} tiri archiviati.`);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const data = historyQuery.data;
  const statistics = data?.statistics;

  return <section className="panel dice-history-admin" data-component-type="panel" data-theme="dark">
    <header className="section-toolbar">
      <div>
        <p className="eyebrow">Registro del gruppo</p>
        <h2>Storico dei tiri</h2>
        <p>Ogni tiro rapido e ogni prova di competenza vengono registrati. Qui puoi filtrarli, confrontarli e archiviare i più vecchi.</p>
      </div>
    </header>
    <p className="muted-copy">
      {drawerHistoryVisible
        ? "«Mostra i tiri nascosti» è attivo in Impostazioni: i Master vedono lo storico del gruppo anche dal cassetto Dadi."
        : "«Mostra i tiri nascosti» è disattivato in Impostazioni: i Master non vedono lo storico dal cassetto Dadi. Questa pagina resta comunque completa."}
    </p>

    <div className="management-filterbar dice-history-filters">
      <label>Giocatore<select value={player} onChange={(event) => { setPlayer(event.target.value); setOffset(0); }}>
        <option value="">Tutti</option>
        {(data?.players || []).map((name) => <option key={name} value={name}>{name}</option>)}
      </select></label>
      <label>Origine<select value={source} onChange={(event) => { setSource(event.target.value); setOffset(0); }}>
        <option value="">Tutte</option>
        {(data?.sources || []).map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
      </select></label>
      <label>Periodo<select value={sinceDays} onChange={(event) => { setSinceDays(Number(event.target.value)); setOffset(0); }}>
        {PERIODS.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
      </select></label>
      <label className="inline-check"><input type="checkbox" checked={showStatistics} onChange={(event) => setShowStatistics(event.target.checked)} /> Mostra statistiche</label>
      <strong>{data?.total ?? 0}</strong>
    </div>

    {historyQuery.error && <p className="form-error">{(historyQuery.error as Error).message}</p>}

    {showStatistics && statistics && <div className="dice-history-statistics">
      <article><h3>Per giocatore</h3><table className="data-table"><thead><tr><th>Giocatore</th><th>Tiri</th><th>Dadi</th><th>Media dado</th><th>Media totale</th></tr></thead><tbody>
        {statistics.byPlayer.map((row) => <tr key={row.name}><td>{row.name}</td><td>{row.rolls}</td><td>{row.dice}</td><td>{row.averageDie}</td><td>{row.averageTotal}</td></tr>)}
      </tbody></table></article>
      <article><h3>Per set di dadi</h3><table className="data-table"><thead><tr><th>Set</th><th>Tiri</th><th>Media dado</th></tr></thead><tbody>
        {statistics.byDiceSet.map((row) => <tr key={row.name}><td>{row.name}</td><td>{row.rolls}</td><td>{row.averageDie}</td></tr>)}
      </tbody></table></article>
      <article><h3>Facce uscite</h3><p className="muted-copy">Conteggio grezzo dei singoli dadi nel filtro corrente, utile solo con molti tiri.</p><ul className="dice-face-distribution">
        {statistics.faceDistribution.map((entry) => <li key={entry.face}><span>{entry.face}</span><b>{entry.count}</b></li>)}
      </ul></article>
    </div>}

    <div className="table-scroll">
      <table className="data-table dice-history-table">
        <thead><tr><th>Quando</th><th>Giocatore</th><th>Personaggio</th><th>Contesto</th><th>Tiro</th><th>Totale</th></tr></thead>
        <tbody>{(data?.rolls || []).map((roll) => <tr key={roll.id}>
          <td>{new Date(roll.rolledAt).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</td>
          <td>{roll.playerName}</td>
          <td>{roll.characterName || "—"}</td>
          <td>{roll.label || roll.sourceLabel}<small>{roll.diceSetName}</small></td>
          <td>{roll.notation} [{roll.rolls.join(", ")}]{roll.modifier ? ` ${roll.modifier > 0 ? "+" : "−"} ${Math.abs(roll.modifier)}` : ""}</td>
          <td><strong>{roll.total}</strong></td>
        </tr>)}</tbody>
      </table>
      {!data?.rolls.length && <div className="management-empty-state"><strong>Nessun tiro</strong><p>Cambia i filtri o attendi la prossima sessione.</p></div>}
    </div>

    <footer className="managed-item-pager">
      <button type="button" className="button secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← Precedenti</button>
      <span>{Math.floor(offset / PAGE_SIZE) + 1} / {Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))}</span>
      <button type="button" className="button secondary small" disabled={!data?.hasMore} onClick={() => setOffset(offset + PAGE_SIZE)}>Successivi →</button>
    </footer>

    <div className="dice-history-purge">
      <label>Archivia i tiri più vecchi di<input type="number" min={1} max={3650} value={purgeDays} onChange={(event) => setPurgeDays(Number(event.target.value))} /> giorni</label>
      <button type="button" className="button danger small" disabled={purgeMutation.isPending} onClick={() => {
        if (window.confirm(`Archiviare tutti i tiri più vecchi di ${purgeDays} giorni?\n\nRestano nel database e non vengono cancellati, ma spariscono dal registro.`)) purgeMutation.mutate();
      }}>{purgeMutation.isPending ? "Archiviazione…" : "Archivia"}</button>
    </div>
  </section>;
}
