import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Modal } from "../../components/Modal";
import { deleteAudioTrack, getData, updateAudioTrack, uploadAudioTrack } from "../../lib/api";
import { filterAudioTracks, formatDuration, formatFileSize, UNTAGGED_FILTER } from "../../lib/audio";
import { useResponsiveLayout } from "../../lib/responsive";
import type { AudioLibraryData, AudioTag, AudioTrack } from "../../lib/types";
import { AudioPlayerControls } from "./AudioPlayerControls";
import { useAudioPlayer } from "./AudioPlayerProvider";

type Props = { notify: (message: string, kind?: "success" | "error" | "info") => void };

/** Reads the length of a chosen file so the library can show it before the first play. */
function measureDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const probe = new Audio();
    const finish = (value: number | null) => { URL.revokeObjectURL(url); resolve(value); };
    probe.preload = "metadata";
    probe.onloadedmetadata = () => finish(Number.isFinite(probe.duration) && probe.duration > 0 ? probe.duration : null);
    probe.onerror = () => finish(null);
    probe.src = url;
  });
}

function TagPicker({ tags, selected, onToggle, idPrefix }: { tags: AudioTag[]; selected: string[]; onToggle: (value: string) => void; idPrefix: string }) {
  return <div className="audio-tag-picker" role="group" aria-label="Tag della traccia">
    {tags.map((tag) => {
      const active = selected.includes(tag.value);
      return <button
        key={`${idPrefix}-${tag.value}`}
        type="button"
        className={active ? "active" : ""}
        aria-pressed={active}
        onClick={() => onToggle(tag.value)}
      >{tag.label}</button>;
    })}
  </div>;
}

export function AudioTool({ notify }: Props) {
  const queryClient = useQueryClient();
  const player = useAudioPlayer();
  const { isPhone } = useResponsiveLayout();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const library = useQuery({ queryKey: ["audioLibrary"], queryFn: () => getData<AudioLibraryData>("/api/audio/tracks/") });
  const [query, setQuery] = useState("");
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadTags, setUploadTags] = useState<string[]>(["musica"]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [editing, setEditing] = useState<AudioTrack | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<AudioTrack | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);

  const tags = library.data?.tags || [];
  const tracks = useMemo(() => library.data?.tracks || [], [library.data]);
  const visible = useMemo(() => filterAudioTracks(tracks, query, filterTags), [filterTags, query, tracks]);

  // The visible selection is the queue: skipping follows what the master is looking at.
  const { syncQueue } = player;
  useEffect(() => { syncQueue(visible); }, [syncQueue, visible]);

  const applyLibrary = (data: AudioLibraryData) => queryClient.setQueryData(["audioLibrary"], data);

  const upload = useMutation({
    mutationFn: async () => {
      if (!uploadFile) throw new Error("Scegli un file audio.");
      const duration = await measureDuration(uploadFile);
      return uploadAudioTrack(uploadFile, uploadTitle.trim() || uploadFile.name.replace(/\.[^.]+$/, ""), uploadTags, duration);
    },
    onSuccess: (result) => {
      applyLibrary(result.data);
      setUploadFile(null);
      setUploadTitle("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      notify(result.events[0]?.message || "Traccia aggiunta.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const save = useMutation({
    mutationFn: (track: AudioTrack) => updateAudioTrack(track.id, { title: editTitle.trim() || track.title, tags: editTags }),
    onSuccess: (result) => {
      applyLibrary(result.data);
      setEditing(null);
      notify(result.events[0]?.message || "Traccia aggiornata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const remove = useMutation({
    mutationFn: (track: AudioTrack) => deleteAudioTrack(track.id),
    onSuccess: (result, track) => {
      player.forget(track.id);
      applyLibrary(result.data);
      setEditing(null);
      setDeleteCandidate(null);
      notify(result.events[0]?.message || "Traccia eliminata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const toggleFilterTag = (value: string) => setFilterTags((current) => current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value]);
  const toggleUploadTag = (value: string) => setUploadTags((current) => current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value]);
  const toggleEditTag = (value: string) => setEditTags((current) => current.includes(value) ? current.filter((entry) => entry !== value) : [...current, value]);
  const startEditing = (track: AudioTrack) => {
    setEditing(track);
    setEditTitle(track.title);
    setEditTags(track.tags);
  };
  const requestDelete = (track: AudioTrack) => {
    if (isPhone) {
      setDeleteCandidate(track);
      return;
    }
    if (window.confirm(`Eliminare definitivamente ${track.title}?`)) remove.mutate(track);
  };

  const submitUpload = (event: FormEvent) => {
    event.preventDefault();
    if (!upload.isPending) upload.mutate();
  };

  if (library.isLoading) return <p className="empty-copy">Apertura della colonna sonora…</p>;
  if (library.isError) return <p className="form-error">{(library.error as Error).message}</p>;

  const canManage = library.data?.canManage === true;
  const filterTagOptions: AudioTag[] = [...tags, { value: UNTAGGED_FILTER, label: "Senza tag" }];

  return <div className="audio-tool" data-component-type="panel" data-theme="parchment">
    <section className="audio-now-playing" data-component-type="panel" data-theme="gold" aria-live="polite">
      <div>
        <p className="eyebrow">In riproduzione</p>
        <h3>{player.current?.title || "Nessuna traccia"}</h3>
        <small>{player.current ? player.current.tagLabels.join(" · ") || "Senza tag" : "Scegli una traccia dall'elenco."}</small>
      </div>
      <AudioPlayerControls />
    </section>

    <section className="audio-filters" data-component-type="toolbar" data-theme="default">
      <label className="audio-search">
        <span className="sr-only">Cerca una traccia</span>
        <input type="search" value={query} placeholder="Cerca per nome o tag…" onChange={(event) => setQuery(event.target.value)} />
      </label>
      <TagPicker tags={filterTagOptions} selected={filterTags} onToggle={toggleFilterTag} idPrefix="filter" />
      {filterTags.length > 0 && <button type="button" className="button secondary" onClick={() => setFilterTags([])}>Azzera filtri</button>}
    </section>

    <section className="audio-track-list" aria-label="Tracce disponibili">
      {visible.length ? <ol>
        {visible.map((track) => {
          const active = player.current?.id === track.id;
          return <li key={track.id} className={active ? "active" : ""} data-state={active && player.playing ? "playing" : "idle"}>
            <button type="button" className="audio-track-play" onClick={() => active && player.playing ? player.toggle() : player.play(track, visible)} aria-label={active && player.playing ? `Metti in pausa ${track.title}` : `Riproduci ${track.title}`}>
              <span aria-hidden="true">{active && player.playing ? "⏸" : "▶"}</span>
            </button>
            <div className="audio-track-identity">
              <strong>{track.title}</strong>
              <small>{track.tagLabels.length ? track.tagLabels.join(" · ") : "Senza tag"}</small>
            </div>
            <span className="audio-track-duration">{formatDuration(track.durationSeconds)}</span>
            {canManage && <button type="button" className="icon-button" onClick={() => startEditing(track)} aria-label={`Modifica ${track.title}`} title="Modifica">✎</button>}
          </li>;
        })}
      </ol> : <p className="empty-copy">{tracks.length ? "Nessuna traccia corrisponde ai filtri." : "La colonna sonora è ancora vuota."}</p>}
    </section>

    {canManage && <details className="audio-manager inline-admin-tool">
      <summary>Aggiungi una traccia</summary>
      <form className="audio-upload-form" onSubmit={submitUpload}>
        <label>File audio
          <input
            ref={fileInputRef}
            type="file"
            accept=".mp3,.ogg,.oga,.opus,.wav,.m4a,.flac,.webm,audio/*"
            onChange={(event) => {
              const file = event.target.files?.[0] || null;
              setUploadFile(file);
              if (file && !uploadTitle.trim()) setUploadTitle(file.name.replace(/\.[^.]+$/, ""));
            }}
          />
        </label>
        <label>Nome<input value={uploadTitle} maxLength={180} onChange={(event) => setUploadTitle(event.target.value)} placeholder="Titolo della traccia" /></label>
        <div className="audio-upload-tags"><span>Tag</span><TagPicker tags={tags} selected={uploadTags} onToggle={toggleUploadTag} idPrefix="upload" /></div>
        <p className="muted-copy">MP3, OGG, OPUS, WAV, M4A, FLAC o WebM, fino a 50 MB.{uploadFile ? ` Selezionato: ${uploadFile.name} (${formatFileSize(uploadFile.size)}).` : ""}</p>
        <button className="button primary" disabled={upload.isPending || !uploadFile}>{upload.isPending ? "Caricamento…" : "Carica traccia"}</button>
      </form>
    </details>}

    {editing && canManage && <section className="audio-editor" data-component-type="panel" data-theme="parchment" aria-label={`Modifica ${editing.title}`}>
      <header><h4>Modifica traccia</h4><button type="button" className="icon-button" onClick={() => setEditing(null)} aria-label="Chiudi la modifica">×</button></header>
      <label>Nome<input value={editTitle} maxLength={180} onChange={(event) => setEditTitle(event.target.value)} /></label>
      <div className="audio-upload-tags"><span>Tag</span><TagPicker tags={tags} selected={editTags} onToggle={toggleEditTag} idPrefix="edit" /></div>
      <div className="button-row">
        <button type="button" className="button primary" disabled={save.isPending} onClick={() => save.mutate(editing)}>Salva</button>
        <button type="button" className="button danger" disabled={remove.isPending} onClick={() => requestDelete(editing)}>Elimina</button>
      </div>
    </section>}

    {deleteCandidate && isPhone && <Modal
      title="Elimina traccia"
      responsiveMode="dialog"
      closeOnBackdrop={false}
      onClose={() => !remove.isPending && setDeleteCandidate(null)}
      footer={<>
        <button type="button" className="button secondary" data-modal-initial-focus disabled={remove.isPending} onClick={() => setDeleteCandidate(null)}>Annulla</button>
        <button type="button" className="button danger" disabled={remove.isPending} onClick={() => remove.mutate(deleteCandidate)}>
          {remove.isPending ? "Eliminazione…" : "Elimina definitivamente"}
        </button>
      </>}
    >
      <p>Eliminare definitivamente <strong>{deleteCandidate.title}</strong>?</p>
      <p className="muted-copy">Questa operazione non può essere annullata.</p>
    </Modal>}
  </div>;
}
