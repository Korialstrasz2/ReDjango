import { type CSSProperties, type FocusEvent, useEffect, useState } from "react";
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
  type RollRequest,
  cultureRoll,
  emptyDossierInputs,
  genderRoll,
  nameSubtitle,
  poolHint,
  raceRoll,
  resolvePreview,
  rolledParts,
  pushHistory,
} from "./nameRules";

/**
 * Le clip pesano circa 1 MB: passare il mouse lungo l'elenco non deve avviare
 * uno scaricamento per ogni riga sfiorata. L'immagine cambia subito, il video
 * solo quando l'anteprima è rimasta ferma abbastanza.
 */
const CLIP_SETTLE_MS = 260;

type Props = { notify: (message: string, kind?: "success" | "error" | "info") => void };

type Tab = "rapido" | "avanzato";

export function NameTool({ notify }: Props) {
  const catalog = useQuery({ queryKey: ["nameCatalog"], queryFn: () => getData<NameCatalogData>("/api/v1/names") });
  const workspace = useQuery({ queryKey: ["aiWorkspace"], queryFn: () => getData<AIWorkspaceData>("/api/ai/") });

  const [tab, setTab] = useState<Tab>("rapido");
  // La cascata: una razza aperta, e dentro di essa una cultura aperta.
  const [openRace, setOpenRace] = useState<string | null>(null);
  const [openCulture, setOpenCulture] = useState<number | null>(null);
  const [hoverGender, setHoverGender] = useState<NameGender | null>(null);
  const [lastRequest, setLastRequest] = useState<RollRequest | null>(null);
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
  // Diciassette razze in colonna unica spingevano il risultato sotto la piega:
  // giocabili e solo narrative stanno affiancate, senza intestazioni a dirlo.
  const playableRaces = races.filter((entry) => entry.playable);
  const loreRaces = races.filter((entry) => !entry.playable);

  const roll = useMutation({
    mutationFn: (request: RollRequest) => {
      setLastRequest(request);
      return command<{ generatedName: GeneratedName }>("names.generate", { ...request }, "names");
    },
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

  const closeCascade = () => {
    setOpenRace(null);
    setOpenCulture(null);
    setHoverGender(null);
  };

  // Aprire al focus rende la cascata percorribile da tastiera; si chiude solo
  // quando il fuoco lascia davvero l'intero albero, non passando fra i livelli.
  const handleBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) closeCascade();
  };

  const enterRace = (entry: NameRaceEntry) => {
    setOpenRace(entry.race);
    setOpenCulture(null);
    setHoverGender(null);
  };

  const enterCulture = (culture: NameCultureEntry) => {
    setOpenCulture(culture.id);
    setHoverGender(null);
  };

  // Quando nulla è sotto il puntatore l'anteprima resta su ciò che è stato
  // generato per ultimo: il pannello non torna vuoto appena si sposta il mouse.
  const hoveredRace = races.find((entry) => entry.race === openRace) || null;
  const hoveredCulture = openCulture
    ? hoveredRace?.cultures.find((entry) => entry.id === openCulture) || null
    : null;
  const currentCulture = current
    ? races.flatMap((entry) => entry.cultures).find((entry) => entry.id === current.cultureId) || null
    : null;
  const preview = hoveredRace || hoveredCulture
    ? resolvePreview(hoveredRace, hoveredCulture, hoverGender)
    : resolvePreview(null, currentCulture, current?.gender ?? null);

  const [settledClip, setSettledClip] = useState("");
  const previewClip = preview?.clip || "";
  useEffect(() => {
    if (!previewClip) {
      setSettledClip("");
      return;
    }
    const timer = window.setTimeout(() => setSettledClip(previewClip), CLIP_SETTLE_MS);
    return () => window.clearTimeout(timer);
  }, [previewClip]);

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

  const raceItem = (entry: NameRaceEntry, index: number) => {
    const isOpen = openRace === entry.race;
    return <li
      key={entry.race}
      style={{ "--i": index } as CSSProperties}
      onMouseEnter={() => enterRace(entry)}
    >
      <button
        type="button"
        className={isOpen ? "open" : ""}
        data-playable={entry.playable}
        aria-expanded={isOpen}
        title={entry.playable ? `${entry.race} · genera con cultura e genere casuali` : `${entry.race} · solo narrativa`}
        onFocus={() => enterRace(entry)}
        onClick={() => {
          // Il clic genera e apre: su touch, dove il passaggio del mouse
          // non esiste, è l'unico modo di raggiungere le culture.
          enterRace(entry);
          roll.mutate(raceRoll(entry));
        }}
      >
        <strong>{entry.race}</strong>
        <em>{entry.cultures.length}</em>
        <span className="name-cascade-arrow" aria-hidden="true">›</span>
      </button>

      {isOpen && <ul className="name-flyout name-cascade-cultures" aria-label={`Culture ${entry.race}`}>
        {entry.cultures.map((cultureEntry, cultureIndex) => {
          const cultureOpen = openCulture === cultureEntry.id;
          return <li
            key={cultureEntry.id}
            style={{ "--i": cultureIndex } as CSSProperties}
            onMouseEnter={() => enterCulture(cultureEntry)}
          >
            <button
              type="button"
              className={cultureOpen ? "open" : ""}
              aria-expanded={cultureOpen}
              title={`${cultureEntry.name} · ${poolHint(cultureEntry)}`}
              onFocus={() => enterCulture(cultureEntry)}
              onClick={() => {
                enterCulture(cultureEntry);
                roll.mutate(cultureRoll(cultureEntry));
              }}
            >
              <strong>{cultureEntry.name}</strong>
              <span className="name-cascade-arrow" aria-hidden="true">›</span>
            </button>

            {cultureOpen && <div className="name-flyout name-cascade-genders" aria-label={`Genere per ${cultureEntry.name}`}>
              {(["maschile", "femminile"] as const).map((genderValue) => <button
                key={genderValue}
                type="button"
                className={hoverGender === genderValue ? "open" : ""}
                onMouseEnter={() => setHoverGender(genderValue)}
                onFocus={() => setHoverGender(genderValue)}
                onClick={() => roll.mutate(genderRoll(cultureEntry, genderValue))}
              >
                <span aria-hidden="true">{genderValue === "maschile" ? "♂" : "♀"}</span>
                {genderValue === "maschile" ? "Maschile" : "Femminile"}
              </button>)}
            </div>}
          </li>;
        })}
      </ul>}
    </li>;
  };

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
      <p className="name-hint">
        Un clic genera subito, a qualunque livello: sulla razza tira cultura e genere, sulla cultura tira il genere,
        sul genere non lascia nulla al dado.
      </p>

      <div className="name-picker">
      <div className="name-cascade" onMouseLeave={closeCascade} onBlur={handleBlur}>
        <ul className="name-cascade-races" aria-label="Razze giocabili">{playableRaces.map(raceItem)}</ul>
        {loreRaces.length > 0 && <ul className="name-cascade-races name-cascade-lore" aria-label="Razze solo narrative">
          {loreRaces.map(raceItem)}
        </ul>}
      </div>

      <div className="name-rail">
      {/* Il risultato apre la colonna invece di seguire l'elenco: è sullo
          schermo dal primo istante, e passare il mouse sulle razze non lo
          sposta perché a crescere è solo l'anteprima, che gli sta sotto. */}
      <output className={`name-result ${roll.isPending ? "pending" : ""}`} aria-live="polite">
        {current ? <>
          <strong>{current.name}</strong>
          <span>{nameSubtitle(current)}</span>
          {rolledParts(lastRequest) && <small className="name-rolled">{rolledParts(lastRequest)}</small>}
          {current.cultureDescription && <p className="name-culture-note">{current.cultureDescription}</p>}
          {current.alreadyUsed && <em className="name-warning">Un personaggio con questo nome esiste già in campagna.</em>}
          <div className="button-row">
            <button type="button" className="button secondary small" disabled={roll.isPending} onClick={() => lastRequest && roll.mutate(lastRequest)}>Tira di nuovo</button>
            <button type="button" className="button secondary small" onClick={() => copy(current.name)}>Copia</button>
            {canAdvance && <button type="button" className="button secondary small" onClick={() => setTab("avanzato")}>Continua il personaggio</button>}
          </div>
        </> : <span className="name-result-empty">Scegli una razza per cominciare.</span>}
      </output>

      <aside className="name-preview" aria-live="polite" aria-label="Anteprima">
        {preview ? <>
          <figure className="name-preview-stage">
            {preview.image
              ? <img src={preview.image} alt={`${preview.title} · ${preview.subtitle}`} width={640} height={640} />
              : <span className="name-preview-missing" aria-hidden="true">◈</span>}
            {settledClip && settledClip === previewClip && <video
              // La chiave forza il rimontaggio: cambiare `src` a caldo non
              // riavvia sempre la riproduzione.
              key={settledClip}
              className="name-preview-clip"
              src={settledClip}
              poster={preview.image || undefined}
              autoPlay
              muted
              loop
              playsInline
              preload="none"
            />}
          </figure>
          <figcaption className="name-preview-caption">
            <strong>{preview.title}</strong>
            <small>{preview.subtitle}</small>
          </figcaption>
        </> : <p className="name-preview-empty">Passa sopra una razza per vederne il ritratto.</p>}
      </aside>
      </div>
      </div>

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
