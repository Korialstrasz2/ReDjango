import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type { CharacterSheet } from "../../lib/types";
import {
  CREATION_STEPS,
  MAX_AGE,
  MIN_AGE,
  canSubmit,
  creationPayload,
  emptyDraft,
  stepIssues,
  withRace,
  type Bonus,
  type CharacteristicOption,
  type CreationDraft,
  type CreationStep,
  type RaceOption,
} from "./steps";

type CreationOptions = {
  races: RaceOption[];
  extraValue: string;
  characteristics: CharacteristicOption[];
  sexes: Array<{ value: string; label: string }>;
  preferredCharacteristicFormula: string;
  startingLevel: number;
  campaignName: string;
  quota: { used: number; max: number | null; canCreate: boolean };
};

const STEP_LABELS: Record<CreationStep, { number: string; title: string; hint: string }> = {
  identity: { number: "01", title: "Identità", hint: "Chi è" },
  race: { number: "02", title: "Razza", hint: "Da dove viene" },
  preferred: { number: "03", title: "Caratteristica preferita", hint: "In cosa eccelle" },
  summary: { number: "04", title: "Riepilogo", hint: "Conferma" },
};

function IdentityStep({ draft, options, update }: { draft: CreationDraft; options: CreationOptions; update: (patch: Partial<CreationDraft>) => void }) {
  return <section className="panel new-pg-step">
    <header><p className="eyebrow">Passo 01</p><h2>Identità</h2><p>Nome, età e sesso sono obbligatori. Nulla di qui ha effetti meccanici.</p></header>
    <div className="form-grid">
      <label>Nome<input value={draft.nome} onChange={(event) => update({ nome: event.target.value })} maxLength={180} required autoFocus /></label>
      <label>Età<input value={draft.eta} onChange={(event) => update({ eta: event.target.value })} type="number" min={MIN_AGE} max={MAX_AGE} required /></label>
      <label>Sesso
        <select value={draft.sesso} onChange={(event) => update({ sesso: event.target.value })} required>
          <option value="" disabled>Scegli…</option>
          {options.sexes.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
        </select>
      </label>
    </div>
    <label>Dettagli personaggio<textarea value={draft.dettagliPersonaggio} onChange={(event) => update({ dettagliPersonaggio: event.target.value })} rows={3} maxLength={4000} placeholder="Una descrizione breve, quella che compare nella scheda." /></label>
    <label>Background<textarea value={draft.background} onChange={(event) => update({ background: event.target.value })} rows={6} maxLength={8000} placeholder="La storia lunga. Finisce nella sezione Background del diario e si può riscrivere quando vuoi." /></label>
  </section>;
}

/* I bonus elencati qui sono quelli che la scheda applica da sola: `growth` dice
   dove arriva la crescita, così nessuno li somma una seconda volta a mano. */
function BonusList({ bonuses, empty }: { bonuses: Bonus[]; empty: string }) {
  if (!bonuses.length) return <p className="new-pg-detail-empty">{empty}</p>;
  return <ul className="new-pg-bonus-list">
    {bonuses.map((bonus) => <li key={`${bonus.label}:${bonus.value}`} data-kind={bonus.kind}>
      <span>{bonus.label}{bonus.growth && <small>{bonus.growth}</small>}</span><strong>{bonus.value}</strong>
    </li>)}
  </ul>;
}

/* Ciò che il motore non sa applicare. Va detto esplicitamente: una regola che
   non compare né fra i bonus automatici né qui sparisce dal tavolo. */
function ManualNote({ text }: { text: string }) {
  if (!text) return null;
  return <p className="new-pg-manual-note"><strong>Da segnare a mano</strong>{text}</p>;
}

function AutomationBadge({ automated, manual }: { automated: boolean; manual: boolean }) {
  const state = automated && manual ? "partial" : automated ? "auto" : "manual";
  const label = state === "partial" ? "In parte automatico" : state === "auto" ? "Automatico" : "Solo promemoria";
  return <span className="new-pg-automation" data-state={state}>{label}</span>;
}

/* Il pannello mostra soltanto ciò che automatic_race_effects applica davvero:
   modificatori della razza, tratto razziale ed effetto della sottorazza scelta. */
function RaceDetailPanel({ race, subrace }: { race?: RaceOption; subrace?: string }) {
  if (!race) return <aside className="new-pg-detail" aria-live="polite">
    <p className="new-pg-detail-empty">Scegli una razza per vederne modificatori e tratto.</p>
  </aside>;
  const chosen = race.subraces.find((entry) => entry.value === subrace);
  return <aside className="new-pg-detail" aria-live="polite">
    <p className="eyebrow">Cosa applica</p>
    <h3>{race.label}</h3>
    <section>
      <h4>Modificatori alle caratteristiche</h4>
      <BonusList bonuses={race.modifiers} empty="Nessun modificatore." />
    </section>
    <section>
      <h4>Tratto razziale <AutomationBadge automated={race.trait.bonuses.length > 0} manual={!!race.trait.manual} /></h4>
      {race.trait.note && <p>{race.trait.note}</p>}
      <BonusList bonuses={race.trait.bonuses} empty="Niente che la scheda possa applicare da sola." />
      <ManualNote text={race.trait.manual} />
    </section>
    <section>
      <h4>
        {chosen ? `Sottorazza: ${chosen.label}` : "Sottorazza"}
        {chosen && <AutomationBadge automated={chosen.bonuses.length > 0} manual={!!chosen.manual} />}
      </h4>
      {chosen
        ? <>
            {chosen.note && <p>{chosen.note}</p>}
            <BonusList bonuses={chosen.bonuses} empty="Niente che la scheda possa applicare da sola." />
            <ManualNote text={chosen.manual} />
          </>
        : <p className="new-pg-detail-empty">{race.subraces.length ? "Scegline una per vederne l'effetto." : `${race.label} non ha sottorazze.`}</p>}
    </section>
    <p className="new-pg-detail-footnote">I bonus di sottorazza crescono di nuovo a livello 5, 10, 15 e 20.</p>
  </aside>;
}

function RaceStep({ draft, options, update }: { draft: CreationDraft; options: CreationOptions; update: (patch: Partial<CreationDraft>) => void }) {
  const race = options.races.find((entry) => entry.value === draft.razza);
  return <section className="panel new-pg-step">
    <header><p className="eyebrow">Passo 02</p><h2>Razza e sottorazza</h2><p>Modificatori, tratto razziale ed effetto della sottorazza vengono applicati automaticamente alla scheda: non vanno ricreati a mano.</p></header>
    <div className="new-pg-choice-layout">
      <div>
        <div className="new-pg-race-grid" role="radiogroup" aria-label="Razza">
          {options.races.map((entry) => <button
            type="button"
            key={entry.value}
            role="radio"
            aria-checked={draft.razza === entry.value}
            className={draft.razza === entry.value ? "active" : ""}
            onClick={() => update(withRace(draft, entry.value))}
          >
            <strong>{entry.label}</strong>
            <small>{entry.subraces.length ? `${entry.subraces.length} sottorazze` : "nessuna sottorazza"}</small>
          </button>)}
        </div>
        {race && race.subraces.length > 0 && <label className="new-pg-subrace">Sottorazza di {race.label}
          <select value={draft.sottorazza} onChange={(event) => update({ sottorazza: event.target.value })}>
            <option value="">Scegli…</option>
            {race.subraces.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}
          </select>
        </label>}
        {race && race.subraces.length === 0 && <p className="new-pg-inline-hint">{race.label} non ha sottorazze: si prosegue così.</p>}
      </div>
      <RaceDetailPanel race={race} subrace={draft.sottorazza} />
    </div>
    <aside className="callout"><strong>La guida «Creare un nuovo PG» elenca i modificatori di ogni razza</strong><p>Aprila dalle <Link to="/guides?guida=Creare%20un%20nuovo%20PG">Guide</Link> se vuoi confrontare i bonus prima di scegliere.</p></aside>
  </section>;
}

/* "Alimenta" arriva dalle formule del profilo Formule_base attivo, non da un
   elenco scritto a mano: se un amministratore cambia una formula, cambia qui. */
function CharacteristicDetailPanel({ characteristic, preferredFormula }: { characteristic?: CharacteristicOption; preferredFormula: string }) {
  if (!characteristic) return <aside className="new-pg-detail" aria-live="polite">
    <p className="new-pg-detail-empty">Scegli una caratteristica per leggere cosa fa.</p>
  </aside>;
  return <aside className="new-pg-detail" aria-live="polite">
    <p className="eyebrow">Cosa fa</p>
    <h3>{characteristic.label}</h3>
    <p>{characteristic.description}</p>
    <section>
      <h4>Alimenta</h4>
      {characteristic.feeds.length
        ? <ul className="new-pg-bonus-list">{characteristic.feeds.map((feed) => <li key={feed} data-kind="bonus"><span>{feed}</span></li>)}</ul>
        : <p className="new-pg-detail-empty">Nessun valore derivato la richiama nelle formule attive.</p>}
    </section>
    <section>
      <h4>Se la scegli</h4>
      <p>Un effetto permanente aggiunge «{preferredFormula}» a {characteristic.label}, che si somma al bonus di livello «{characteristic.levelFormula || "—"}» ricevuto da tutte e nove: cresce quindi al doppio della velocità.</p>
    </section>
  </aside>;
}

function PreferredStep({ draft, options, update }: { draft: CreationDraft; options: CreationOptions; update: (patch: Partial<CreationDraft>) => void }) {
  const characteristic = options.characteristics.find((entry) => entry.value === draft.caratteristicaPreferita);
  return <section className="panel new-pg-step">
    <header><p className="eyebrow">Passo 03</p><h2>Caratteristica preferita</h2><p>È l'unica scelta meccanica della creazione. Genera un effetto permanente che aggiunge «{options.preferredCharacteristicFormula}» alla caratteristica scelta, cioè +1 ogni cinque livelli.</p></header>
    <div className="new-pg-choice-layout">
      <div className="new-pg-characteristic-grid" role="radiogroup" aria-label="Caratteristica preferita">
        {options.characteristics.map((entry) => <button
          type="button"
          key={entry.value}
          role="radio"
          aria-checked={draft.caratteristicaPreferita === entry.value}
          className={draft.caratteristicaPreferita === entry.value ? "active" : ""}
          onClick={() => update({ caratteristicaPreferita: entry.value })}
        >{entry.label}</button>)}
      </div>
      <CharacteristicDetailPanel characteristic={characteristic} preferredFormula={options.preferredCharacteristicFormula} />
    </div>
    <aside className="callout"><strong>Il bonus di livello lo ricevono comunque tutte le caratteristiche</strong><p>ReDjango applica già da solo la formula di livello a tutte e nove. La preferita si somma a quella, quindi cresce al doppio della velocità delle altre. In Elder Django il bonus esisteva solo sulla preferita.</p></aside>
  </section>;
}

function SummaryStep({ draft, options }: { draft: CreationDraft; options: CreationOptions }) {
  const race = options.races.find((entry) => entry.value === draft.razza);
  const subrace = race?.subraces.find((entry) => entry.value === draft.sottorazza);
  const preferred = options.characteristics.find((entry) => entry.value === draft.caratteristicaPreferita);
  return <section className="panel new-pg-step">
    <header><p className="eyebrow">Passo 04</p><h2>Riepilogo</h2><p>Controlla e conferma. Nome, età, sesso e testi restano modificabili dalla scheda.</p></header>
    <dl className="new-pg-summary">
      <div><dt>Nome</dt><dd>{draft.nome.trim() || "—"}</dd></div>
      <div><dt>Età</dt><dd>{draft.eta.trim() || "—"}</dd></div>
      <div><dt>Sesso</dt><dd>{options.sexes.find((entry) => entry.value === draft.sesso)?.label || "—"}</dd></div>
      <div><dt>Razza</dt><dd>{race?.label || "—"}</dd></div>
      <div><dt>Sottorazza</dt><dd>{subrace?.label || "nessuna"}</dd></div>
      <div><dt>Caratteristica preferita</dt><dd>{preferred?.label || "—"}</dd></div>
      <div><dt>Livello iniziale</dt><dd>{options.startingLevel}</dd></div>
      <div><dt>Campagna</dt><dd>{options.campaignName || "nessuna campagna attiva"}</dd></div>
    </dl>
    <aside className="callout"><strong>Il personaggio nasce vuoto</strong><p>Zero Punti Esperienza in ogni riserva, nessuna competenza, nessuna abilità, nessuna moneta e nessun equipaggiamento. Tutto il resto si guadagna giocando.</p></aside>
  </section>;
}

export function NewCharacterPage() {
  const { notify } = useApp();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [stepIndex, setStepIndex] = useState(0);
  const [draft, setDraft] = useState<CreationDraft>(emptyDraft);
  const [showIssues, setShowIssues] = useState(false);

  const query = useQuery({
    queryKey: ["character-creation-options"],
    queryFn: () => getData<CreationOptions>("/api/v1/characters/creation-options"),
  });

  const createMutation = useMutation({
    mutationFn: () => command<{ character?: CharacterSheet | null }>("characters.create", creationPayload(draft), "nuovo-pg"),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ["personaggi"] });
      await queryClient.invalidateQueries({ queryKey: ["character-creation-options"] });
      notify(response.events[0]?.message || "Personaggio creato.");
      const created = response.data.character;
      navigate(created ? `/character/${created.id}` : "/");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const options = query.data;
  const step = CREATION_STEPS[stepIndex];
  const issues = options ? stepIssues(step, draft, options.races) : [];
  const update = (patch: Partial<CreationDraft>) => {
    setDraft((current) => ({ ...current, ...patch }));
    setShowIssues(false);
  };
  const goNext = () => {
    if (issues.length) {
      setShowIssues(true);
      return;
    }
    setShowIssues(false);
    setStepIndex((current) => Math.min(current + 1, CREATION_STEPS.length - 1));
  };

  const header = <header className="page-header"><div><p className="eyebrow">Compagnia</p><h1>Nuovo PG</h1></div><Link className="button secondary" to="/">Torna alla selezione</Link></header>;

  if (query.isLoading) return <div className="page new-pg-page">{header}<section className="panel loading-state">Preparazione della scheda…</section></div>;
  if (query.isError || !options) return <div className="page new-pg-page">{header}<section className="panel form-error">{(query.error as Error)?.message || "Cataloghi non disponibili."}</section></div>;
  if (!options.quota.canCreate) return <div className="page new-pg-page">{header}<section className="panel empty-state">
    <h2>Hai raggiunto il numero massimo di personaggi</h2>
    <p>Hai {options.quota.used} personaggi giocabili su {options.quota.max} disponibili. Chiedi al Master di archiviarne uno prima di crearne un altro.</p>
    <Link className="button primary" to="/">Torna alla selezione</Link>
  </section></div>;

  return <div className="page new-pg-page">
    {header}
    <nav className="new-pg-tabs" aria-label="Passi della creazione">
      {CREATION_STEPS.map((entry, index) => <button
        type="button"
        key={entry}
        className={index === stepIndex ? "active" : ""}
        aria-current={index === stepIndex ? "step" : undefined}
        disabled={index > stepIndex}
        onClick={() => setStepIndex(index)}
      ><span>{STEP_LABELS[entry].number}</span><strong>{STEP_LABELS[entry].title}</strong><small>{STEP_LABELS[entry].hint}</small></button>)}
    </nav>

    {step === "identity" && <IdentityStep draft={draft} options={options} update={update} />}
    {step === "race" && <RaceStep draft={draft} options={options} update={update} />}
    {step === "preferred" && <PreferredStep draft={draft} options={options} update={update} />}
    {step === "summary" && <SummaryStep draft={draft} options={options} />}

    {showIssues && issues.length > 0 && <aside className="panel form-error" role="alert">{issues.join(" ")}</aside>}

    <div className="new-pg-actions">
      <button className="button secondary" type="button" disabled={stepIndex === 0} onClick={() => { setShowIssues(false); setStepIndex((current) => Math.max(current - 1, 0)); }}>Indietro</button>
      {step === "summary"
        ? <button className="button primary" type="button" disabled={createMutation.isPending || !canSubmit(draft, options.races)} onClick={() => createMutation.mutate()}>
            {createMutation.isPending ? "Creazione…" : "Crea il personaggio"}
          </button>
        : <button className="button primary" type="button" onClick={goNext}>Avanti</button>}
    </div>
  </div>;
}
