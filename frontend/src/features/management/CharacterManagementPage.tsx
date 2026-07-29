import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type {
  CharacterManagementDetail,
  CharacterManagementOverview,
  ManagedRelation,
  ManagementField,
  OrphanRecord,
} from "./types";

type Draft = Record<string, unknown>;
type ManagedActionData = { management?: CharacterManagementDetail | CharacterManagementOverview | null };

function draftValues(fields: ManagementField[], values: Record<string, unknown>): Draft {
  return Object.fromEntries(fields.map((field) => [
    field.key,
    field.type === "json" ? JSON.stringify(values[field.key] ?? {}, null, 2) : values[field.key] ?? "",
  ]));
}

function parsedValues(fields: ManagementField[], values: Draft): Record<string, unknown> {
  // Calculated fields are shown for diagnosis only; sending them back would be
  // pointless work the server discards anyway.
  return Object.fromEntries(fields.filter((field) => !field.readOnly).map((field) => {
    const value = values[field.key];
    if (field.type === "json") return [field.key, JSON.parse(String(value || "{}"))];
    if (field.type === "integer") return [field.key, value === "" && field.nullable ? null : Number(value)];
    if (field.type === "item" || field.type === "effect" || field.type === "campaign" || field.type === "image") {
      return [field.key, value === "" || value == null ? null : Number(value)];
    }
    return [field.key, value];
  }));
}

// The catalogue has thousands of rows and a character sheet has well over a
// hundred slots. Rendering every option in every slot is what made this editor
// heavy, so a slot shows only its current item and searches for the rest.
function ItemSlotPicker({ value, options, onChange }: {
  value: unknown;
  options: Array<{ id: number; name: string; archived: boolean }>;
  onChange: (value: unknown) => void;
}) {
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const search = useQuery({
    queryKey: ["management-slot-items", term],
    queryFn: () => getData<{ items: Array<{ id: number; name: string; archived: boolean }> }>(
      `/api/v1/management/items?limit=25&query=${encodeURIComponent(term)}`,
    ),
    enabled: open && term.trim().length >= 2,
  });
  const current = options.find((item) => String(item.id) === String(value ?? ""));
  if (!open) {
    return <span className="slot-picker">
      <button type="button" className="slot-picker-current" onClick={() => setOpen(true)}>
        {current ? `${current.name}${current.archived ? " · archiviato" : ""}` : "Vuoto"}
      </button>
      {value !== "" && value != null && <button type="button" className="icon-button" aria-label="Svuota casella" onClick={() => onChange("")}>×</button>}
    </span>;
  }
  return <span className="slot-picker open">
    <input autoFocus value={term} placeholder="Cerca un oggetto…" onChange={(event) => setTerm(event.target.value)} />
    <button type="button" className="icon-button" aria-label="Chiudi ricerca" onClick={() => { setOpen(false); setTerm(""); }}>×</button>
    {search.isFetching && <small>Ricerca…</small>}
    {search.data && <div className="slot-picker-results">
      <button type="button" onClick={() => { onChange(""); setOpen(false); setTerm(""); }}>Svuota</button>
      {search.data.items.map((item) => <button key={item.id} type="button" onClick={() => { onChange(String(item.id)); setOpen(false); setTerm(""); }}>
        {item.name}{item.archived ? " · archiviato" : ""}
      </button>)}
      {!search.data.items.length && <small>Nessun risultato.</small>}
    </div>}
  </span>;
}

function FieldControl({
  field,
  value,
  detail,
  onChange,
}: {
  field: ManagementField;
  value: unknown;
  detail: CharacterManagementDetail;
  onChange: (value: unknown) => void;
}) {
  if (field.readOnly) {
    return <textarea className="code-input" rows={8} readOnly value={typeof value === "string" ? value : JSON.stringify(value ?? {}, null, 2)} />;
  }
  if (field.type === "campaign") {
    return <select value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}>
      {detail.options.campaigns.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
    </select>;
  }
  if (field.type === "image") {
    const known = detail.options.images.find((image) => String(image.id) === String(value ?? ""));
    return <span className="portrait-field">
      <input value={String(value ?? "")} placeholder="ID immagine" onChange={(event) => onChange(event.target.value.trim())} />
      <small>{known ? known.name : value ? "Immagine non trovata" : "Nessun ritratto"}</small>
    </span>;
  }
  if (field.type === "boolean") {
    return <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />;
  }
  if (field.type === "textarea" || field.type === "json") {
    return <textarea
      rows={field.type === "json" ? 8 : 5}
      className={field.type === "json" ? "code-input" : ""}
      value={String(value ?? "")}
      onChange={(event) => onChange(event.target.value)}
      spellCheck={field.type !== "json"}
    />;
  }
  if (field.type === "select") {
    return <select value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}>
      {(field.choices || []).map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
    </select>;
  }
  if (field.type === "item") {
    return <ItemSlotPicker value={value} options={detail.options.items} onChange={onChange} />;
  }
  if (field.type === "effect") {
    return <select value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}>
      <option value="">Vuoto</option>
      {detail.options.effects.map((effect) => <option key={effect.id} value={effect.id}>{effect.name}</option>)}
    </select>;
  }
  return <input
    type={field.type === "integer" ? "number" : "text"}
    min={field.minimum}
    value={String(value ?? "")}
    onChange={(event) => onChange(event.target.value)}
  />;
}

function RelatedRecordEditor({
  relation,
  detail,
  values,
  onChange,
}: {
  relation: ManagedRelation;
  detail: CharacterManagementDetail;
  values: Draft;
  onChange: (key: string, value: unknown) => void;
}) {
  const hasManySlots = relation.kind === "zaino" || relation.kind === "faretra" || relation.kind === "effetti";
  const [showEmpty, setShowEmpty] = useState(!hasManySlots);
  if (!relation.present) {
    return <div className="management-empty-state"><strong>{relation.label} non collegato</strong><p>Apri la scheda Orfani per trovare e collegare un record disponibile.</p></div>;
  }
  const visibleFields = relation.fields.filter((field) => showEmpty || !field.key.match(/^(slot|effetto)_/) || values[field.key] !== "");
  return <section className="related-editor" aria-label={`Modifica ${relation.label}`}>
    <div className="section-toolbar">
      <div><p className="eyebrow">Record #{relation.id}</p><h3>{relation.label}</h3></div>
      {hasManySlots && <button className="button secondary small" type="button" onClick={() => setShowEmpty((current) => !current)}>
        {showEmpty ? "Nascondi spazi vuoti" : "Mostra tutti gli spazi"}
      </button>}
    </div>
    <div className="management-form-grid">
      {visibleFields.map((field) => <label key={field.key} className={field.type === "textarea" || field.type === "json" ? "wide" : ""}>
        <span>{field.label}</span>
        <FieldControl field={field} value={values[field.key]} detail={detail} onChange={(value) => onChange(field.key, value)} />
      </label>)}
    </div>
    {hasManySlots && !showEmpty && visibleFields.length <= 1 && <p className="muted-copy">Il record non contiene ancora oggetti. Mostra tutti gli spazi per aggiungerne uno.</p>}
  </section>;
}

function CharacterEditor({ detail, onDeleted }: { detail: CharacterManagementDetail; onDeleted: () => void }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [section, setSection] = useState("profile");
  const [profile, setProfile] = useState<Draft>(() => draftValues(detail.profileFields, detail.profile));
  const [relations, setRelations] = useState<Record<string, Draft>>(() => Object.fromEntries(
    detail.relations.map((relation) => [relation.kind, draftValues(relation.fields, relation.values)]),
  ));
  const [formError, setFormError] = useState("");
  const [showDeletePrompt, setShowDeletePrompt] = useState(false);
  const groupedProfileFields = useMemo(() => detail.profileFields.reduce<Record<string, ManagementField[]>>((groups, field) => {
    (groups[field.group] ||= []).push(field);
    return groups;
  }, {}), [detail.profileFields]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const relationPayload = Object.fromEntries(detail.relations.filter((relation) => relation.present).map((relation) => [
        relation.kind,
        parsedValues(relation.fields, relations[relation.kind] || {}),
      ]));
      return command<ManagedActionData>("management.characters.update", {
        characterId: detail.character.id,
        profile: parsedValues(detail.profileFields, profile),
        relations: relationPayload,
      }, "management-characters");
    },
    onSuccess: async (response) => {
      const updated = response.data.management;
      if (updated && "character" in updated) {
        queryClient.setQueryData(["management-character", detail.character.id], updated);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["management-characters"] }),
        queryClient.invalidateQueries({ queryKey: ["personaggi"] }),
        queryClient.invalidateQueries({ queryKey: ["character", detail.character.id] }),
      ]);
      setFormError("");
      notify("Personaggio e record collegati salvati.");
    },
    onError: (error: Error) => { setFormError(error.message); notify(error.message, "error"); },
  });

  const deleteMutation = useMutation({
    mutationFn: () => command<ManagedActionData>("management.characters.delete", {
      characterId: detail.character.id,
      previewToken: detail.deletionPreview.token,
    }, "management-characters"),
    onSuccess: async () => {
      queryClient.removeQueries({ queryKey: ["management-character", detail.character.id] });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["management-characters"] }),
        queryClient.invalidateQueries({ queryKey: ["personaggi"] }),
      ]);
      notify(`${detail.character.name} è stato eliminato.`);
      onDeleted();
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const save = () => {
    try {
      setFormError("");
      saveMutation.mutate();
    } catch (error) {
      setFormError(error instanceof Error ? `JSON non valido: ${error.message}` : "Controlla i dati strutturati.");
    }
  };
  const activeRelation = detail.relations.find((relation) => relation.kind === section);

  return <section className="panel management-editor" data-component-type="panel" data-theme="default">
    <header className="management-editor-header">
      <div><p className="eyebrow">#{detail.character.id} · {detail.character.type}</p><h2>{detail.character.name}</h2><p>Livello {detail.character.level} · {detail.character.internalName}</p></div>
      <div className="button-row"><Link className="button secondary" to={`/character/${detail.character.id}`}>Apri scheda</Link><button className="button primary" type="button" onClick={save} disabled={saveMutation.isPending}>Salva tutto</button></div>
    </header>
    {formError && <p className="form-error" role="alert">{formError}</p>}
    <nav className="management-record-tabs" aria-label="Record del personaggio">
      <button className={section === "profile" ? "active" : ""} onClick={() => setSection("profile")}>Dati personaggio</button>
      {detail.relations.map((relation) => <button key={relation.kind} className={section === relation.kind ? "active" : ""} data-state={relation.present ? "ready" : "missing"} onClick={() => setSection(relation.kind)}>{relation.label}{!relation.present && " · mancante"}</button>)}
      <button className={section === "containers" ? "active" : ""} onClick={() => setSection("containers")}>Contenitori{detail.inventoryContainers.length ? ` · ${detail.inventoryContainers.length}` : ""}</button>
      <button className={section === "danger" ? "active danger" : "danger"} onClick={() => setSection("danger")}>Eliminazione</button>
    </nav>

    {section === "profile" && <div className="profile-editor-groups">
      {Object.entries(groupedProfileFields).map(([group, fields]) => <fieldset key={group}><legend>{group}</legend><div className="management-form-grid">
        {fields.map((field) => <label key={field.key} className={field.type === "textarea" || field.type === "json" ? "wide" : ""}><span>{field.label}</span><FieldControl field={field} value={profile[field.key]} detail={detail} onChange={(value) => setProfile((current) => ({ ...current, [field.key]: value }))} /></label>)}
      </div></fieldset>)}
    </div>}
    {activeRelation && <RelatedRecordEditor
      key={activeRelation.kind}
      relation={activeRelation}
      detail={detail}
      values={relations[activeRelation.kind] || {}}
      onChange={(key, value) => setRelations((current) => ({ ...current, [activeRelation.kind]: { ...current[activeRelation.kind], [key]: value } }))}
    />}
    {section === "containers" && <section className="inventory-container-view" data-component-type="panel" data-theme="parchment">
      <header><p className="eyebrow">Sola lettura</p><h3>Contenitori inventario</h3><p>Questo è lo zaino a slot usato in gioco, con capienza e giacenze. Le schede Zaino e Faretra qui sopra modificano invece i vecchi record a 50 caselle: se una scheda mostra oggetti inattesi, confronta le due.</p></header>
      {detail.inventoryContainers.length ? detail.inventoryContainers.map((container) => <article key={container.id} data-component-type="card" data-theme="default">
        <header><strong>{container.name}</strong><small>{container.scope} · {container.entries.length}/{container.capacity} caselle{container.weightless ? " · senza peso" : ""}</small></header>
        {container.entries.length ? <ul className="inventory-container-entries">{container.entries.map((entry) => <li key={entry.slot}>
          <span>{entry.slot}</span><strong>{entry.name}</strong>{entry.isReagent && <em>reagente</em>}<b>×{entry.quantity}</b>
        </li>)}</ul> : <p className="muted-copy">Contenitore vuoto.</p>}
      </article>) : <div className="management-empty-state"><strong>Nessun contenitore</strong><p>Questo personaggio non ha ancora uno zaino a slot: usa solo i record legacy.</p></div>}
    </section>}
    {section === "danger" && <section className="deletion-preview" data-component-type="panel" data-theme="danger">
      <header><p className="eyebrow">Anteprima obbligatoria</p><h3>Record interessati dall'eliminazione</h3><p>I record rossi saranno eliminati. Quelli condivisi restano nel database.</p></header>
      <div className="deletion-records">{detail.deletionPreview.records.map((record) => <article key={`${record.kind}:${record.id ?? "none"}`} data-state={record.status}>
        <span>{record.willDelete ? "Elimina" : record.status === "shared" ? "Conserva" : "Nessuna azione"}</span><strong>{record.label} {record.id ? `#${record.id}` : ""}</strong><b>{record.name}</b><small>{record.detail}</small>
      </article>)}</div>
      <button className="button danger" type="button" disabled={deleteMutation.isPending} onClick={() => setShowDeletePrompt(true)}>Elimina personaggio e record evidenziati</button>
      {showDeletePrompt && <div className="modal-overlay" onClick={() => setShowDeletePrompt(false)}><div className="modal confirm-dialog" onClick={(e) => e.stopPropagation()} role="alertdialog" aria-label="Conferma eliminazione"><p>Eliminare <strong>{detail.character.name}</strong> e tutti i record evidenziati?</p><div className="button-row"><button className="button secondary" type="button" onClick={() => setShowDeletePrompt(false)}>No</button><button className="button danger" type="button" disabled={deleteMutation.isPending} onClick={() => { setShowDeletePrompt(false); deleteMutation.mutate(); }}>Sì</button></div></div></div>}
    </section>}
  </section>;
}

function OrphanRow({ record, overview }: { record: OrphanRecord; overview: CharacterManagementOverview }) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const candidates = overview.characters.filter((character) => character.missingRelations.includes(record.kind));
  const [characterId, setCharacterId] = useState<number | undefined>(candidates[0]?.id);
  const mutation = useMutation({
    mutationFn: () => command<ManagedActionData>("management.characters.attach", { characterId, kind: record.kind, recordId: record.id }, "management-characters"),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["management-characters"] }),
        queryClient.invalidateQueries({ queryKey: ["management-character"] }),
        queryClient.invalidateQueries({ queryKey: ["personaggi"] }),
      ]);
      notify(`${record.label} collegato al personaggio.`);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const deleteMutation = useMutation({
    mutationFn: () => command<ManagedActionData>("management.characters.deleteOrphan", { kind: record.kind, recordId: record.id }, "management-characters"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["management-characters"] });
      notify(`${record.label} eliminato.`);
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  return <article className="orphan-row" data-component-type="card" data-theme="muted">
    <div><span>{record.label} · #{record.id}</span><strong>{record.name}</strong><p>{record.reason}</p><small>{record.contents}</small></div>
    <div className="orphan-attach">
      {record.attachable && <><select value={characterId || ""} onChange={(event) => setCharacterId(Number(event.target.value) || undefined)}><option value="">Nessun personaggio compatibile</option>{candidates.map((character) => <option key={character.id} value={character.id}>{character.name}</option>)}</select><button className="button secondary small" disabled={!characterId || mutation.isPending} onClick={() => mutation.mutate()}>Collega</button></>}
      <button className="button danger small" disabled={deleteMutation.isPending} onClick={() => {
        if (window.confirm(`Eliminare definitivamente ${record.label.toLocaleLowerCase("it")} «${record.name}»?\n\nViene rimosso solo questo record. Gli oggetti e gli effetti che contiene restano nel catalogo.`)) deleteMutation.mutate();
      }}>Elimina</button>
    </div>
  </article>;
}

export function CharacterManagementPage() {
  const [mode, setMode] = useState<"characters" | "orphans">("characters");
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [onlyIncomplete, setOnlyIncomplete] = useState(false);
  const [campaignFilter, setCampaignFilter] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const overviewQuery = useQuery({
    queryKey: ["management-characters", campaignFilter],
    queryFn: () => getData<CharacterManagementOverview>(`/api/v1/management/characters?campaign=${encodeURIComponent(campaignFilter)}`),
  });
  const detailQuery = useQuery({
    queryKey: ["management-character", selectedId],
    queryFn: () => getData<CharacterManagementDetail>(`/api/v1/management/characters/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const overview = overviewQuery.data;
  useEffect(() => {
    if (!selectedId && overview?.characters.length) setSelectedId(overview.characters[0].id);
  }, [overview, selectedId]);
  const normalized = query.trim().toLocaleLowerCase("it");
  const characters = (overview?.characters || []).filter((character) => {
    const matches = !normalized || `${character.name} ${character.internalName} ${character.type}`.toLocaleLowerCase("it").includes(normalized);
    return matches && (!onlyIncomplete || character.missingRelations.length > 0);
  });
  const orphans = (overview?.orphans || []).filter((record) => {
    const matches = !normalized || `${record.name} ${record.label} ${record.reason}`.toLocaleLowerCase("it").includes(normalized);
    return matches && (!kind || record.kind === kind);
  });

  return <div className="page management-page">
    <header className="page-header"><div><p className="eyebrow">Gestione del gioco</p><h1>Personaggi e record collegati</h1></div><Link className="button secondary" to="/tools">Tutti gli strumenti</Link></header>
    <div className="management-mode-tabs" role="tablist"><button role="tab" aria-selected={mode === "characters"} className={mode === "characters" ? "active" : ""} onClick={() => setMode("characters")}>Personaggi</button><button role="tab" aria-selected={mode === "orphans"} className={mode === "orphans" ? "active" : ""} onClick={() => setMode("orphans")}>Record orfani <span>{overview?.orphans.length || 0}</span></button></div>
    <section className="panel management-filterbar" data-component-type="toolbar" data-theme="default"><label>Cerca<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nome, tipo o identificativo…" /></label>{mode === "characters" ? <><label>Campagna<select value={campaignFilter} onChange={(event) => setCampaignFilter(event.target.value)}><option value="">Tutte</option><option value="none">Senza campagna</option>{(overview?.campaigns || []).filter((entry) => entry.value).map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label><label className="inline-check"><input type="checkbox" checked={onlyIncomplete} onChange={(event) => setOnlyIncomplete(event.target.checked)} /> Solo con record mancanti</label></> : <label>Tipo record<select value={kind} onChange={(event) => setKind(event.target.value)}><option value="">Tutti</option>{overview?.relationKinds.map((entry) => <option key={entry.value} value={entry.value}>{entry.label}</option>)}</select></label>}</section>
    {overviewQuery.isLoading && <section className="panel"><p>Caricamento archivio personaggi…</p></section>}
    {overviewQuery.error && <section className="panel danger-panel"><p>{(overviewQuery.error as Error).message}</p></section>}
    {mode === "characters" && overview && <div className="character-management-layout">
      <aside className="panel managed-character-list"><header><strong>{characters.length} personaggi</strong><small>Seleziona una scheda da gestire</small></header>{characters.map((character) => <button key={character.id} className={selectedId === character.id ? "active" : ""} onClick={() => setSelectedId(character.id)}><span><strong>{character.name}</strong><small>{character.type} · livello {character.level} · {character.campaignName || "senza campagna"}</small></span>{character.missingRelations.length > 0 && <b title="Record mancanti">{character.missingRelations.length}</b>}</button>)}</aside>
      <div>{detailQuery.isLoading && <section className="panel"><p>Caricamento dati e relazioni…</p></section>}{detailQuery.data && <CharacterEditor key={`${detailQuery.data.character.id}:${detailQuery.data.character.updatedAt}`} detail={detailQuery.data} onDeleted={() => setSelectedId(null)} />}</div>
    </div>}
    {mode === "orphans" && overview && <section className="orphan-workspace"><div className="orphan-explanation"><strong>Che cosa significa “orfano”?</strong><p>È un record previsto per un personaggio ma non collegato ad alcuna scheda. Puoi filtrarlo, controllarlo e collegarlo solo a un personaggio che ne è privo.</p></div>{orphans.length ? <div className="orphan-list">{orphans.map((record) => <OrphanRow key={`${record.kind}:${record.id}`} record={record} overview={overview} />)}</div> : <div className="management-empty-state"><strong>Nessun record orfano trovato</strong><p>Il filtro corrente non mostra anomalie.</p></div>}</section>}
  </div>;
}
