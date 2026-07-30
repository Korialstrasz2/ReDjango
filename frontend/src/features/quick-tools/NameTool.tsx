import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import { command, generateNpcDossier, generateNpcPortrait, getData } from "../../lib/api";
import type {
  AIWorkspaceData,
  GeneratedName,
  MediaAsset,
  NameCatalogData,
  NameCultureEntry,
  NameGender,
  NameRaceEntry,
  NpcDossierResult,
} from "../../lib/types";
import {
  DOSSIER_FIELDS,
  defaultCultureFor,
  emptyDossierInputs,
  genderLabel,
  nameSubtitle,
  poolSize,
  pushHistory,
} from "./nameRules";

type Props = { notify: (message: string, kind?: "success" | "error" | "info") => void };

type Tab = "rapido" | "avanzato";

export function NameTool({ notify }: Props) {
  const catalog = useQuery({ queryKey: ["nameCatalog"], queryFn: () => getData<NameCatalogData>("/api/v1/names") });
  const workspace = useQuery({ queryKey: ["aiWorkspace"], queryFn: () => getData<AIWorkspaceData>("/api/ai/") });

  const [tab, setTab] = useState<Tab>("rapido");
  const [raceName, setRaceName] = useState("");
  const [cultureId, setCultureId] = useState<number | null>(null);
  const [gender, setGender] = useState<NameGender>("casuale");
  const [current, setCurrent] = useState<GeneratedName | null>(null);
  const [history, setHistory] = useState<GeneratedName[]>([]);
  const [inputs, setInputs] = useState(emptyDossierInputs());
  const [withContext, setWithContext] = useState(false);
  const [dossier, setDossier] = useState<NpcDossierResult | null>(null);
  const [description, setDescription] = useState("");
  const [role, setRole] = useState("");
  const [portrait, setPortrait] = useState<MediaAsset | null>(null);
  const [saved, setSaved] = useState(false);

  const races = catalog.data?.races ?? [];
  const race: NameRaceEntry | null = races.find((entry) => entry.race === raceName) || null;
  const cultures = race?.cultures ?? [];
  const culture: NameCultureEntry | null =
    cultures.find((entry) => entry.id === cultureId) || defaultCultureFor(race);

  const roll = useMutation({
    mutationFn: () =>
      command<{ generatedName: GeneratedName }>(
        "names.generate",
        culture ? { cultureId: culture.id, gender } : { race: raceName, gender },
        "names",
      ),
    onSuccess: (result) => {
      const generated = result.data.generatedName;
      setCurrent(generated);
      setHistory((entries) => pushHistory(entries, generated));
      // Un nome nuovo invalida la bozza che descriveva quello vecchio.
      setDossier(null);
      setPortrait(null);
      setSaved(false);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const askDossier = useMutation({
    mutationFn: () =>
      generateNpcDossier({
        name: current?.name,
        race: current?.race,
        culture: current?.culture,
        gender: current?.gender,
        cultureDescription: current?.cultureDescription,
        includeCampaignContext: withContext,
        ...inputs,
      }),
    onSuccess: (result) => {
      setDossier(result.data);
      setDescription(result.data.description);
      setRole(result.data.draft.ruolo);
      setSaved(false);
      notify("Bozza pronta: rivedila prima di salvare.", "info");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const drawPortrait = useMutation({
    mutationFn: () =>
      generateNpcPortrait({ name: current?.name, draft: dossier?.draft, subject: dossier?.subject }),
    onSuccess: (result) => {
      setPortrait(result.data.asset);
      notify(result.events[0]?.message || "Ritratto generato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const save = useMutation({
    mutationFn: () =>
      command(
        "lore.character.save",
        {
          values: {
            id: null,
            name: current?.name,
            role,
            description,
            portraitId: portrait?.id ?? null,
            factionId: null,
            // I segreti del Master restano suoi: la visibilità si concede a mano.
            visibleToPlayers: false,
          },
        },
        "names",
      ),
    onSuccess: () => {
      setSaved(true);
      notify(`${current?.name} salvato fra i Personaggi Lore, nascosto ai giocatori.`);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      notify(`«${value}» copiato.`, "info");
    } catch {
      notify("La copia non è disponibile in questo browser.", "error");
    }
  };

  const selectRace = (entry: NameRaceEntry) => {
    setRaceName(entry.race);
    setCultureId(defaultCultureFor(entry)?.id ?? null);
  };

  const poolHint = useMemo(() => {
    if (!culture) return "";
    const first = poolSize(culture, gender);
    return culture.surnameCount
      ? `${first} nomi · ${culture.surnameCount} cognomi`
      : `${first} nomi · nessun cognome in questa cultura`;
  }, [culture, gender]);

  if (catalog.isLoading) return <p className="empty-copy">Apertura dei registri…</p>;
  if (catalog.isError) return <p className="form-error">{(catalog.error as Error).message}</p>;
  if (!races.length) {
    return <div className="name-empty" data-component-type="panel" data-theme="parchment">
      <h3>Nessun bacino di nomi</h3>
      <p className="muted-copy">Importa le culture Elder con <code>manage.py import_legacy_names --apply</code>, oppure aggiungine una da Django Admin.</p>
    </div>;
  }

  const ai = workspace.data;
  const canAdvance = Boolean(ai?.canManage && ai?.ready);
  const allowContext = Boolean(ai?.npcGeneration?.allowCampaignContext);

  return <div className="name-tool" data-component-type="panel" data-theme="parchment">
    <nav className="name-tabs" role="tablist" aria-label="Modalità del generatore" data-component-type="tabset" data-theme="gold">
      <button type="button" role="tab" aria-selected={tab === "rapido"} className={tab === "rapido" ? "active" : ""} onClick={() => setTab("rapido")}>
        <span aria-hidden="true">◈</span><strong>Rapido</strong><small>Razza e genere</small>
      </button>
      <button type="button" role="tab" aria-selected={tab === "avanzato"} className={tab === "avanzato" ? "active" : ""} onClick={() => setTab("avanzato")} disabled={!current}>
        <span aria-hidden="true">✳</span><strong>Avanzato</strong><small>Dossier e ritratto</small>
      </button>
    </nav>

    {tab === "rapido" ? <section className="name-quick" role="tabpanel" aria-label="Generazione rapida">
      <fieldset className="name-races">
        <legend>Razza</legend>
        <div>{races.map((entry) => <button
          key={entry.race}
          type="button"
          className={entry.race === raceName ? "active" : ""}
          aria-pressed={entry.race === raceName}
          data-playable={entry.playable}
          title={entry.playable ? entry.race : `${entry.race} · solo narrativa`}
          onClick={() => selectRace(entry)}
        ><strong>{entry.race}</strong><em>{entry.cultures.length > 1 ? `${entry.cultures.length} culture` : "1 cultura"}</em></button>)}</div>
      </fieldset>

      <fieldset className="name-genders">
        <legend>Genere</legend>
        <div>{(catalog.data?.genders ?? []).map((entry) => <button
          key={entry.value}
          type="button"
          className={entry.value === gender ? "active" : ""}
          aria-pressed={entry.value === gender}
          onClick={() => setGender(entry.value)}
        >{entry.label}</button>)}</div>
      </fieldset>

      {cultures.length > 1 && <fieldset className="name-cultures">
        <legend>Cultura <small>facoltativa</small></legend>
        <select
          value={culture ? String(culture.id) : ""}
          onChange={(event) => setCultureId(event.target.value ? Number(event.target.value) : null)}
        >
          {cultures.map((entry) => <option key={entry.id} value={String(entry.id)}>{entry.name}</option>)}
        </select>
        {culture?.description && <p className="name-culture-note">{culture.description}</p>}
      </fieldset>}

      <div className="name-actions">
        <button type="button" className="button primary" disabled={!raceName || roll.isPending} onClick={() => roll.mutate()}>
          {roll.isPending ? "…" : current ? "Genera un altro nome" : "Genera nome"}
        </button>
        {poolHint && <small className="muted-copy">{poolHint}</small>}
      </div>

      {current && <output className="name-result" aria-live="polite">
        <strong>{current.name}</strong>
        <span>{nameSubtitle(current)}{current.requestedGender === "casuale" ? " · tirato" : ""}</span>
        {current.alreadyUsed && <em className="name-warning">Un personaggio con questo nome esiste già in campagna.</em>}
        <div className="button-row">
          <button type="button" className="button secondary small" onClick={() => copy(current.name)}>Copia</button>
          {canAdvance && <button type="button" className="button secondary small" onClick={() => setTab("avanzato")}>Continua il personaggio</button>}
        </div>
      </output>}

      {history.length > 1 && <details className="name-history">
        <summary>Nomi precedenti ({history.length - 1})</summary>
        <ul>{history.slice(1).map((entry) => <li key={entry.name}>
          <button type="button" onClick={() => setCurrent(entry)}><strong>{entry.name}</strong><small>{nameSubtitle(entry)}</small></button>
          <button type="button" className="button secondary small" onClick={() => copy(entry.name)}>Copia</button>
        </li>)}</ul>
      </details>}
    </section> : <section className="name-advanced" role="tabpanel" aria-label="Dossier del personaggio">
      {!canAdvance ? <div className="name-empty">
        <h3>Dossier non disponibile</h3>
        <p className="muted-copy">
          {ai?.canManage
            ? "Serve un provider di chat configurato: la modalità rapida continua a funzionare senza."
            : "Solo Master e Amministratori possono generare un dossier."}
        </p>
        {ai?.canManage && <Link className="button primary" to="/tools/ai">Apri Gestione AI</Link>}
      </div> : <>
        <header className="name-advanced-head">
          <div><p className="eyebrow">{nameSubtitle(current!)}</p><h3>{current!.name}</h3></div>
          <button type="button" className="button secondary small" onClick={() => setTab("rapido")}>Cambia nome</button>
        </header>

        <div className="name-inputs">
          {DOSSIER_FIELDS.map((field) => <label key={field.key}>
            <span>{field.label}</span>
            <input
              type="text"
              value={inputs[field.key]}
              maxLength={200}
              placeholder={field.placeholder}
              onChange={(event) => setInputs({ ...inputs, [field.key]: event.target.value })}
            />
          </label>)}
        </div>

        <label className={`name-context ${withContext ? "checked" : ""}`} title="Lore, fazioni, stato della campagna e note condivise, come sfondo">
          <input type="checkbox" checked={withContext && allowContext} disabled={!allowContext} onChange={(event) => setWithContext(event.target.checked)} />
          <span className="name-context-copy">
            <strong>Usa il contesto della campagna</strong>
            <small>{allowContext
              ? "Lore, fazioni e note condivise entrano solo come sfondo, non come istruzioni."
              : "Disattivato da Gestione AI."}</small>
          </span>
        </label>

        <div className="name-actions">
          <button type="button" className="button primary" disabled={askDossier.isPending} onClick={() => askDossier.mutate()}>
            {askDossier.isPending ? "Sto abbozzando…" : dossier ? "Rigenera la bozza" : "Genera dossier"}
          </button>
          {dossier && <small className="muted-copy">{dossier.provider.name}{dossier.provider.model ? ` · ${dossier.provider.model}` : ""}</small>}
        </div>

        {dossier && <div className="name-draft">
          <p className="name-draft-note">Bozza da rivedere: nulla è stato salvato.</p>
          <label><span>Ruolo</span><input type="text" value={role} maxLength={160} onChange={(event) => setRole(event.target.value)} /></label>
          <label><span>Descrizione</span><textarea rows={8} value={description} maxLength={8000} onChange={(event) => setDescription(event.target.value)} /></label>

          {dossier.draft.ganci.length > 0 && <ul className="name-hooks">
            {dossier.draft.ganci.map((hook) => <li key={hook}>{hook}</li>)}
          </ul>}

          {dossier.contextUsed && <details className="name-context-trace">
            <summary>Contesto usato ({dossier.contextCharacters} caratteri)</summary>
            <ul>{dossier.contextTrace.map((entry) => <li key={entry.name} data-state={entry.ok ? "ok" : "skipped"}>
              <span aria-hidden="true">{entry.ok ? "◆" : "—"}</span>{entry.name}
              <em>{entry.ok ? `${entry.characters} caratteri` : "non disponibile"}</em>
            </li>)}</ul>
          </details>}

          <div className="name-portrait">
            <div>
              <p className="eyebrow">Ritratto</p>
              <small className="muted-copy">{dossier.portrait.size} · qualità {dossier.portrait.quality} · passo a pagamento</small>
            </div>
            <button type="button" className="button secondary" disabled={drawPortrait.isPending} onClick={() => drawPortrait.mutate()}>
              {drawPortrait.isPending ? "Generazione…" : portrait ? "Rigenera ritratto" : "Genera ritratto"}
            </button>
          </div>
          {portrait && <figure className="name-portrait-result">
            <img src={portrait.url} alt={portrait.title} />
            <figcaption>{portrait.title} · già nell'Archivio immagini</figcaption>
          </figure>}

          <footer className="name-save">
            <button type="button" className="button primary" disabled={save.isPending || saved || !description.trim()} onClick={() => save.mutate()}>
              {saved ? "Salvato" : save.isPending ? "Salvataggio…" : "Salva come Personaggio Lore"}
            </button>
            {saved
              ? <Link className="button secondary small" to="/lore">Apri in Lore</Link>
              : <small className="muted-copy">Nascosto ai giocatori finché non lo rendi visibile da Lore.</small>}
          </footer>
        </div>}
      </>}
    </section>}
  </div>;
}
