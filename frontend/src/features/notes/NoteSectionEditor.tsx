import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { command, getData } from "../../lib/api";
import type { CharacterNotesData, CharacterSheet, NoteSection } from "../../lib/types";

export const NOTE_SECTIONS: Array<{ id: NoteSection; label: string; description: string; glyph: string }> = [
  { id: "appunti", label: "Appunti", description: "Pensieri, nomi e dettagli da ricordare.", glyph: "⌑" },
  { id: "missioni", label: "Missioni", description: "Obiettivi, indizi e prossimi passi.", glyph: "⚑" },
  { id: "zaino", label: "Zaino", description: "Scorte, oggetti affidati e cose da recuperare.", glyph: "◇" },
  { id: "furto", label: "Furto", description: "Cariche dei set da scasso, poteri particolari e colpi in sospeso.", glyph: "⚿" },
  { id: "combat", label: "Combattimento", description: "Tattiche, avversari e promemoria per gli scontri.", glyph: "⚔" },
  { id: "competenze", label: "Competenze", description: "Nuance, usi creativi, bonus permanenti e promemoria sui tiri.", glyph: "✧" },
  { id: "crafting", label: "Crafting", description: "Materiali, ricette e progetti in corso.", glyph: "⚒" },
  { id: "viaggio", label: "Viaggio", description: "Rotte, luoghi, incontri e pericoli sulla strada.", glyph: "⌁" },
  { id: "background", label: "Background", description: "Storia personale, legami e motivazioni.", glyph: "◈" },
];

type Props = {
  characterId: number;
  section: NoteSection;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
  initialContent?: string;
  rows?: number;
  compact?: boolean;
  minimal?: boolean;
};

type NotesActionData = { notes: CharacterNotesData };
type SheetData = { character: CharacterSheet; effectCatalog: unknown[] };
type SaveStatus = "idle" | "dirty" | "saving" | "saved" | "error";

export function NoteSectionEditor({ characterId, section, notify, initialContent = "", rows = 18, compact = false, minimal = false }: Props) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["character-notes", characterId],
    queryFn: () => getData<CharacterNotesData>(`/api/v1/characters/${characterId}/notes`),
    enabled: Number.isFinite(characterId),
  });
  const definition = NOTE_SECTIONS.find((entry) => entry.id === section)!;
  const remoteContent = query.data?.sections[section] ?? initialContent;
  const [value, setValue] = useState(remoteContent);
  const [status, setStatus] = useState<SaveStatus>("idle");
  const valueRef = useRef(value);
  const dirtyRef = useRef(false);
  const lastQueuedRef = useRef<string | null>(null);
  const queueRef = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    valueRef.current = value;
  }, [value]);

  useEffect(() => {
    setValue(remoteContent);
    valueRef.current = remoteContent;
    dirtyRef.current = false;
    lastQueuedRef.current = remoteContent;
    setStatus("idle");
  }, [characterId, section]);

  useEffect(() => {
    if (!dirtyRef.current && valueRef.current !== remoteContent) {
      setValue(remoteContent);
      valueRef.current = remoteContent;
      lastQueuedRef.current = remoteContent;
    }
  }, [remoteContent]);

  const updateCaches = useCallback((notes: CharacterNotesData) => {
    queryClient.setQueryData(["character-notes", characterId], notes);
    queryClient.setQueryData<SheetData>(["character-sheet", characterId], (current) => current ? {
      ...current,
      character: { ...current.character, notes: notes.sections },
    } : current);
  }, [characterId, queryClient]);

  const persist = useCallback((content: string) => {
    if (content === lastQueuedRef.current) return;
    lastQueuedRef.current = content;
    setStatus("saving");
    queueRef.current = queueRef.current
      .catch(() => undefined)
      .then(async () => {
        const result = await command<NotesActionData>("notes.updateSection", { characterId, section, content }, section === "zaino" ? "character" : "notes");
        updateCaches(result.data.notes);
        if (valueRef.current === result.data.notes.sections[section]) {
          dirtyRef.current = false;
          setStatus("saved");
        } else {
          setStatus("dirty");
        }
      })
      .catch((error: Error) => {
        if (lastQueuedRef.current === content) lastQueuedRef.current = null;
        setStatus("error");
        notify(error.message, "error");
      });
  }, [characterId, notify, section, updateCaches]);

  useEffect(() => {
    if (!dirtyRef.current || value === remoteContent) return;
    const timer = window.setTimeout(() => persist(value), 800);
    return () => window.clearTimeout(timer);
  }, [persist, remoteContent, value]);

  const changeValue = (content: string) => {
    setValue(content);
    valueRef.current = content;
    dirtyRef.current = content !== remoteContent;
    setStatus(content === remoteContent ? "idle" : "dirty");
  };

  const statusLabel = status === "saving" ? "Salvataggio…" : status === "saved" ? "Salvato" : status === "error" ? "Salvataggio non riuscito" : status === "dirty" ? "Da salvare" : "Salvataggio automatico";

  return <section className={`note-section-editor ${compact ? "compact" : ""} ${minimal ? "minimal" : ""}`} data-component-type="form" data-theme="parchment" data-note-section={section}>
    {!minimal && <header>
      <div><span aria-hidden="true">{definition.glyph}</span><div><h3>{definition.label}</h3><p>{definition.description}</p></div></div>
      <small className={`note-save-status ${status}`} aria-live="polite">{statusLabel}</small>
    </header>}
    {minimal && <div className="note-editor-minimal-meta">
      <span>{definition.description}</span>
      <small className={`note-save-status ${status}`} aria-live="polite">{statusLabel}</small>
    </div>}
    {query.isError && !query.data ? <p className="form-error">{(query.error as Error).message}</p> : <textarea
      aria-label={`Note ${definition.label}`}
      maxLength={30000}
      rows={rows}
      value={value}
      disabled={query.isLoading && !initialContent}
      placeholder={`Scrivi qui le note per ${definition.label.toLocaleLowerCase("it")}…`}
      onChange={(event) => changeValue(event.target.value)}
      onBlur={() => persist(valueRef.current)}
      onKeyDown={(event) => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase("it") === "s") {
          event.preventDefault();
          persist(valueRef.current);
        }
      }}
    />}
  </section>;
}
