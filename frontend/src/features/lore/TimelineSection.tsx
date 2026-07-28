import { useEffect, useMemo, useRef, useState } from "react";

import { ImagePickerModal } from "../../components/ImagePickerModal";
import { Modal } from "../../components/Modal";

export type LoreTimelineEvent = {
  id: number;
  title: string;
  dateLabel: string;
  year: number;
  description: string;
  imageId: number | null;
  imageUrl: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  canEdit: boolean;
};

type TimelineDraft = {
  id: number | null;
  title: string;
  year: string;
  description: string;
  imageId: number | null;
  imageUrl: string;
  tags: string;
};

type Props = {
  events: LoreTimelineEvent[];
  canManage: boolean;
  isPending: boolean;
  run: (action: string, payload: Record<string, unknown>, done?: () => void) => void;
};

export function formatTimelineYear(year: number): string {
  if (year === 0) return "Anno di Dagoth";
  if (year < 0) return `${Math.abs(year)} ${Math.abs(year) === 1 ? "anno" : "anni"} prima di Dagoth`;
  return `${year} ${year === 1 ? "anno" : "anni"} dopo Dagoth`;
}

function eventDraft(event?: LoreTimelineEvent): TimelineDraft {
  return event
    ? {
        id: event.id,
        title: event.title,
        year: String(event.year),
        description: event.description,
        imageId: event.imageId,
        imageUrl: event.imageUrl,
        tags: event.tags.join(", "),
      }
    : { id: null, title: "", year: "0", description: "", imageId: null, imageUrl: "", tags: "" };
}

function normalizedTags(raw: string): string[] {
  const seen = new Set<string>();
  return raw
    .split(",")
    .map((entry) => entry.trim())
    .filter((entry) => {
      const key = entry.toLocaleLowerCase("it");
      if (!entry || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

export function TimelineSection({ events, canManage, isPending, run }: Props) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(events[0]?.id ?? null);
  const [draft, setDraft] = useState<TimelineDraft | null>(null);
  const [imagePickerOpen, setImagePickerOpen] = useState(false);
  const railRef = useRef<HTMLOListElement>(null);

  const visibleEvents = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("it");
    if (!needle) return events;
    return events.filter((event) =>
      `${event.title} ${event.description} ${event.dateLabel} ${event.tags.join(" ")}`
        .toLocaleLowerCase("it")
        .includes(needle)
    );
  }, [events, query]);

  useEffect(() => {
    if (!visibleEvents.some((event) => event.id === selectedId)) {
      setSelectedId(visibleEvents[0]?.id ?? null);
    }
  }, [selectedId, visibleEvents]);

  const selected = visibleEvents.find((event) => event.id === selectedId) ?? null;

  const selectEvent = (eventId: number) => {
    setSelectedId(eventId);
    requestAnimationFrame(() => {
      railRef.current
        ?.querySelector<HTMLElement>(`[data-timeline-event-id="${eventId}"]`)
        ?.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
    });
  };

  const selectRelative = (offset: number) => {
    if (!visibleEvents.length) return;
    const currentIndex = Math.max(0, visibleEvents.findIndex((event) => event.id === selectedId));
    const nextIndex = Math.max(0, Math.min(visibleEvents.length - 1, currentIndex + offset));
    selectEvent(visibleEvents[nextIndex].id);
  };

  const submit = () => {
    if (!draft || !draft.title.trim() || draft.year.trim() === "") return;
    run("lore.timeline.save", {
      values: {
        id: draft.id,
        title: draft.title,
        year: Number(draft.year),
        description: draft.description,
        imageId: draft.imageId,
        tags: normalizedTags(draft.tags),
      },
    }, () => setDraft(null));
  };

  return <>
    <section
      className="lore-section lore-timeline-section"
      data-component-type="panel"
      data-theme="lore"
      role="tabpanel"
      id="lore-panel-timeline"
      aria-labelledby="lore-tab-timeline"
    >
      <div className="lore-section-header">
        <div>
          <h2>Timeline</h2>
          <p>La storia del mondo e della campagna, ordinata rispetto alla caduta di Dagoth Ur.</p>
        </div>
        {canManage && <div className="lore-actions">
          <button type="button" data-action="lore.timeline.create" onClick={() => setDraft(eventDraft())}>
            Nuovo evento
          </button>
        </div>}
      </div>

      <div className="lore-timeline-toolbar" data-component-type="toolbar" data-theme="lore">
        <label>
          <span>Cerca nella cronologia</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Titolo, testo o etichetta"
          />
        </label>
        <span className="lore-timeline-count">
          {visibleEvents.length === 1 ? "1 evento" : `${visibleEvents.length} eventi`}
        </span>
        <div className="lore-timeline-navigation">
          <button
            type="button"
            aria-label="Evento precedente"
            disabled={!selected || visibleEvents[0]?.id === selected.id}
            onClick={() => selectRelative(-1)}
          >←</button>
          <button
            type="button"
            aria-label="Evento successivo"
            disabled={!selected || visibleEvents[visibleEvents.length - 1]?.id === selected.id}
            onClick={() => selectRelative(1)}
          >→</button>
        </div>
      </div>

      {!visibleEvents.length
        ? <p className="lore-empty">Nessun evento corrisponde alla ricerca.</p>
        : <div className="lore-history-rail">
            <ol
              ref={railRef}
              className="lore-history-events"
              aria-label="Eventi della Timeline"
              onKeyDown={(event) => {
                if (event.key === "ArrowLeft") {
                  event.preventDefault();
                  selectRelative(-1);
                } else if (event.key === "ArrowRight") {
                  event.preventDefault();
                  selectRelative(1);
                }
              }}
            >
              {visibleEvents.map((timelineEvent) => <li key={timelineEvent.id}>
                <button
                  type="button"
                  className={timelineEvent.id === selectedId ? "active" : ""}
                  data-component-type="card"
                  data-theme="lore"
                  data-timeline-event-id={timelineEvent.id}
                  aria-pressed={timelineEvent.id === selectedId}
                  onClick={() => selectEvent(timelineEvent.id)}
                >
                  {timelineEvent.imageUrl
                    ? <img src={timelineEvent.imageUrl} alt="" />
                    : <span className="lore-history-placeholder" aria-hidden="true">◇</span>}
                  <span className="lore-history-card-copy">
                    <strong>{timelineEvent.title}</strong>
                    <small>{formatTimelineYear(timelineEvent.year)}</small>
                  </span>
                  <span className="lore-history-marker" aria-hidden="true" />
                </button>
              </li>)}
            </ol>
          </div>}

      {selected && <article
        className={`lore-timeline-inspector${selected.imageUrl ? "" : " without-image"}`}
        data-component-type="inspector"
        data-theme="lore"
      >
        {selected.imageUrl && <img src={selected.imageUrl} alt="" className="lore-timeline-inspector-image" />}
        <div className="lore-timeline-inspector-body">
          <header>
            <div>
              <span className="lore-timeline-date">{formatTimelineYear(selected.year)}</span>
              <h3>{selected.title}</h3>
            </div>
            {canManage && selected.canEdit && <div className="lore-actions">
              <button type="button" data-action="lore.timeline.edit" onClick={() => setDraft(eventDraft(selected))}>
                Modifica
              </button>
              <button type="button" className="danger" data-action="lore.timeline.archive" onClick={() => {
                if (window.confirm(`Archiviare l'evento “${selected.title}”?`)) {
                  run("lore.timeline.archive", { id: selected.id });
                }
              }}>Archivia</button>
            </div>}
          </header>
          {selected.tags.length > 0 && <div className="lore-timeline-tags">
            {selected.tags.map((tag) => <span key={tag} className="lore-tag">{tag}</span>)}
          </div>}
          {selected.description
            ? <p>{selected.description}</p>
            : <p className="lore-empty">Nessuna descrizione registrata.</p>}
        </div>
      </article>}
    </section>

    {draft && <Modal
      title={draft.id ? "Modifica evento della Timeline" : "Nuovo evento della Timeline"}
      onClose={() => setDraft(null)}
      wide
    >
      <div className="lore-form lore-timeline-form">
        <div className="lore-form-row">
          <label><span>Titolo</span>
            <input
              value={draft.title}
              maxLength={180}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
              autoFocus
            />
          </label>
          <label className="lore-timeline-year-field"><span>Anno da Dagoth</span>
            <input
              type="number"
              value={draft.year}
              onChange={(event) => setDraft({ ...draft, year: event.target.value })}
            />
          </label>
        </div>
        <p className="lore-hint">Usa numeri negativi per gli anni precedenti e 0 per l'anno della caduta di Dagoth Ur.</p>
        <label><span>Descrizione</span>
          <textarea
            rows={8}
            value={draft.description}
            onChange={(event) => setDraft({ ...draft, description: event.target.value })}
          />
        </label>
        <label><span>Etichette</span>
          <input
            value={draft.tags}
            onChange={(event) => setDraft({ ...draft, tags: event.target.value })}
            placeholder="TES, Quarta Era, Morrowind"
          />
        </label>
        <div className="lore-timeline-image-field">
          {draft.imageUrl
            ? <img src={draft.imageUrl} alt="" />
            : <span className="lore-history-placeholder" aria-hidden="true">◇</span>}
          <div>
            <strong>Immagine dell'evento</strong>
            <span>Usa una scena già presente nell'Archivio immagini oppure caricane una nuova.</span>
            <div className="lore-form-row">
              <button type="button" onClick={() => setImagePickerOpen(true)}>Scegli immagine</button>
              {draft.imageId && <button type="button" onClick={() => setDraft({ ...draft, imageId: null, imageUrl: "" })}>
                Rimuovi immagine
              </button>}
            </div>
          </div>
        </div>
        <footer className="lore-card-actions">
          <button
            type="button"
            className="primary"
            data-action="lore.timeline.save"
            disabled={isPending || !draft.title.trim() || draft.year.trim() === ""}
            onClick={submit}
          >Salva</button>
          <button type="button" onClick={() => setDraft(null)}>Annulla</button>
        </footer>
      </div>
    </Modal>}

    {draft && imagePickerOpen && <ImagePickerModal
      selectedId={draft.imageId}
      usageType="scene"
      defaultGroup="Timeline"
      defaultTitle={draft.title}
      onSelect={(asset) => setDraft({
        ...draft,
        imageId: asset?.id ?? null,
        imageUrl: asset?.url ?? "",
      })}
      onClose={() => setImagePickerOpen(false)}
    />}
  </>;
}
