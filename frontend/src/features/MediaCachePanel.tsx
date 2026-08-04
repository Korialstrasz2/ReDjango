import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  activateMediaCache,
  clearMediaCache,
  downloadMediaCache,
  getMediaCacheManifest,
  importMediaCachePackage,
  mediaCacheSupported,
  mediaStorageStatus,
  requestPersistentMediaStorage,
  type MediaCacheDownloadResult,
  type MediaCacheProgress,
  type MediaStorageStatus,
} from "../lib/mediaCache";

type Props = {
  userId: number;
  campaignId: number | null;
  canExportPackage: boolean;
  notify: (message: string, kind?: "success" | "error" | "info") => void;
};

function bytes(value: number | null): string {
  if (value === null) return "non disponibile";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

export function MediaCachePanel({ userId, campaignId, canExportPackage, notify }: Props) {
  const supported = mediaCacheSupported();
  const manifest = useQuery({
    queryKey: ["media-cache-manifest", campaignId],
    queryFn: getMediaCacheManifest,
  });
  const [storage, setStorage] = useState<MediaStorageStatus | null>(null);
  const [progress, setProgress] = useState<MediaCacheProgress | null>(null);
  const [result, setResult] = useState<MediaCacheDownloadResult | null>(null);
  const [busy, setBusy] = useState<"download" | "import" | "clear" | "persist" | null>(null);
  const importInput = useRef<HTMLInputElement>(null);

  const refreshStorage = () => mediaStorageStatus().then(setStorage).catch(() => setStorage(null));
  useEffect(() => { void refreshStorage(); }, []);
  useEffect(() => {
    if (!supported) return;
    void activateMediaCache(userId, campaignId).catch(() => undefined);
  }, [campaignId, supported, userId]);

  const download = async () => {
    if (!manifest.data) return;
    setBusy("download");
    setProgress(null);
    setResult(null);
    try {
      await activateMediaCache(userId, campaignId);
      const completed = await downloadMediaCache(manifest.data, setProgress);
      setResult(completed);
      await refreshStorage();
      if (completed.failed) notify(`${completed.failed} file non sono stati memorizzati. Puoi riprovare.`, "error");
      else notify("Media della campagna disponibili su questo dispositivo.");
    } catch (error) {
      notify((error as Error).message, "error");
    } finally {
      setBusy(null);
    }
  };

  const importPackage = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy("import");
    setProgress(null);
    setResult(null);
    try {
      const imported = await importMediaCachePackage(file, setProgress);
      setResult({
        completed: imported.imported,
        total: imported.imported,
        completedBytes: imported.totalBytes,
        totalBytes: imported.totalBytes,
        downloaded: imported.imported,
        skipped: 0,
        failed: 0,
      });
      await refreshStorage();
      notify(`Pacchetto di ${imported.campaignName} importato e verificato.`);
    } catch (error) {
      notify((error as Error).message, "error");
    } finally {
      setBusy(null);
    }
  };

  const clear = async () => {
    if (!manifest.data) return;
    if (!window.confirm("Svuotare i media locali di questo account e di questa campagna? Potrai scaricarli di nuovo.")) return;
    setBusy("clear");
    try {
      await clearMediaCache(manifest.data.scope);
      setProgress(null);
      setResult(null);
      await refreshStorage();
      notify("Cache media locale svuotata.");
    } catch (error) {
      notify((error as Error).message, "error");
    } finally {
      setBusy(null);
    }
  };

  const persist = async () => {
    setBusy("persist");
    try {
      const granted = await requestPersistentMediaStorage();
      await refreshStorage();
      notify(granted ? "Il browser proteggerà meglio i media locali." : "Il browser non ha concesso lo spazio persistente.", granted ? "success" : "info");
    } catch (error) {
      notify((error as Error).message, "error");
    } finally {
      setBusy(null);
    }
  };

  const percent = progress?.totalBytes
    ? Math.min(100, Math.round(progress.completedBytes / progress.totalBytes * 100))
    : 0;

  return <section className="panel media-cache-panel" data-component-type="panel" data-theme="gold" data-surface="media-cache-settings">
    <header><div><p className="eyebrow">Media sul dispositivo</p><h2>Archivio locale della campagna</h2></div><span>{manifest.data?.campaign?.name || "Nessuna campagna"}</span></header>
    <p>Scarica una volta immagini, miniature, icone integrate, audio, video e tasselli delle mappe. Le visite successive useranno la copia locale finché il file non cambia o scegli di cancellarla.</p>
    {!supported && <p className="setting-inline-warning" role="alert">Questa funzione richiede HTTPS (oppure localhost) e un browser con Service Worker. La normale cache HTTP resta comunque disponibile.</p>}
    {manifest.isError && <p className="setting-inline-warning" role="alert">Impossibile preparare l'elenco dei media: {(manifest.error as Error).message}</p>}
    <div className="media-cache-stats">
      <span><small>Pacchetto campagna</small><strong>{manifest.data ? bytes(manifest.data.totalBytes) : "calcolo…"}</strong><em>{manifest.data?.entries.length ?? 0} file</em></span>
      <span><small>Uso origine nel browser</small><strong>{bytes(storage?.usage ?? null)}</strong><em>Quota {bytes(storage?.quota ?? null)}</em></span>
      <span><small>Protezione dallo sgombero</small><strong>{storage?.persisted === true ? "Attiva" : storage?.persisted === false ? "Non attiva" : "Non disponibile"}</strong><em>Il browser può sempre essere svuotato manualmente</em></span>
    </div>
    {progress && <div className="media-cache-progress" role="status">
      <div><strong>{busy === "download" ? `Download ${percent}%` : busy === "import" ? `Importazione verificata ${percent}%` : "Ultimo aggiornamento"}</strong><span>{progress.completed}/{progress.total} · {bytes(progress.completedBytes)} / {bytes(progress.totalBytes)}</span></div>
      <progress max={Math.max(1, progress.totalBytes)} value={progress.completedBytes} />
      <small>{progress.currentLabel} · nuovi {progress.downloaded}, già presenti {progress.skipped}, errori {progress.failed}</small>
    </div>}
    {result && !result.failed && <p className="media-cache-result">Aggiornamento completato: {result.downloaded} nuovi, {result.skipped} già aggiornati.</p>}
    <div className="media-cache-actions">
      <button type="button" className="button primary" disabled={!supported || !manifest.data || busy !== null} onClick={download}>{busy === "download" ? "Download…" : result ? "Aggiorna tutti i media" : "Scarica tutti i media"}</button>
      <button type="button" className="button secondary" disabled={!supported || busy !== null} onClick={() => importInput.current?.click()}>{busy === "import" ? "Importazione…" : "Importa pacchetto media ZIP"}</button>
      <input ref={importInput} className="media-cache-import-input" type="file" accept=".zip,application/zip" onChange={importPackage} />
      {canExportPackage && <button type="button" className="button secondary" disabled={!manifest.data || busy !== null} onClick={() => window.location.assign("/api/media/cache-package/")}>Esporta pacchetto media ZIP</button>}
      <button type="button" className="button secondary" disabled={!supported || busy !== null || storage?.persisted === true} onClick={persist}>{busy === "persist" ? "Richiesta…" : "Mantieni su questo dispositivo"}</button>
      <button type="button" className="button secondary" disabled={!supported || !manifest.data || busy !== null} onClick={clear}>{busy === "clear" ? "Pulizia…" : "Svuota cache media locale"}</button>
    </div>
    <small>Il ZIP è verificato prima dell'importazione e viene attivato soltanto se completo. La pulizia riguarda soltanto i media ReDjango del tuo account e della campagna selezionata. I contenuti a visibilità limitata non entrano mai nel pacchetto locale.</small>
  </section>;
}
