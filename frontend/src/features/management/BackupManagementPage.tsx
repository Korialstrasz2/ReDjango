import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { command, getData } from "../../lib/api";
import type {
  BackupCharacterDetail,
  BackupConfiguration,
  BackupInspection,
  BackupManagementData,
  ManagedBackup,
} from "./types";


type BackupActionData = { management?: BackupManagementData | null };

const DEFAULT_CONFIGURATION: BackupConfiguration = {
  enabled: true,
  onStartup: true,
  intervalMinutes: 30,
  retentionCount: 12,
};


function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}


function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Data non disponibile" : date.toLocaleString("it");
}


function backupKindLabel(backup: ManagedBackup): string {
  return backup.kind === "manual" ? "Manuale" : "Automatico";
}


function Storage({ overview }: { overview: BackupManagementData }) {
  return <div className="backup-storage-summary">
    <div><span>Copie gestite</span><strong>{overview.storage.count}</strong></div>
    <div><span>Spazio occupato</span><strong>{formatBytes(overview.storage.usedBytes)}</strong></div>
    <div><span>Limite configurato</span><strong>{overview.configuration.retentionCount}</strong></div>
    <p>{overview.storage.content}</p>
  </div>;
}


function BackupCharacterDetails({ character }: { character: BackupCharacterDetail }) {
  return <div className="backup-character-details">
    <header>
      <div>
        <p className="eyebrow">Personaggio nel backup</p>
        <h3>{character.name}</h3>
        <small>{character.type || "Tipo non indicato"} · livello {character.level} · {character.coins} monete</small>
      </div>
      {character.damage > 0 && <span className="backup-damage">{character.damage} danni</span>}
    </header>
    <div className="backup-values-grid">
      {character.coreValues.map((value) => <div key={value.key}><span>{value.label}</span><strong>{value.value}</strong></div>)}
    </div>
    <section className="backup-inventory-section">
      <h4>Zaino</h4>
      {character.backpack.length
        ? <ul>{character.backpack.map((entry) => <li key={`${entry.slot}-${entry.name}`}><b>{entry.slot}</b><span>{entry.name}</span></li>)}</ul>
        : <p>Nessun oggetto nello zaino al momento del backup.</p>}
    </section>
    {character.containers.map((container) => <section className="backup-inventory-section" key={container.name}>
      <h4>{container.name} <small>{container.entries.length}/{container.capacity} spazi</small></h4>
      {container.entries.length
        ? <ul>{container.entries.map((entry) => <li key={`${entry.slot}-${entry.name}`}><b>{entry.slot}</b><span>{entry.name}</span><em>×{entry.quantity}</em></li>)}</ul>
        : <p>Vuoto al momento del backup.</p>}
    </section>)}
  </div>;
}


function BackupInspector({
  inspection,
  busy,
  onSelectCharacter,
}: {
  inspection: BackupInspection | null;
  busy: boolean;
  onSelectCharacter: (characterId: number) => void;
}) {
  if (!inspection) {
    return <section className="panel backup-inspector-empty" data-component-type="panel" data-theme="muted">
      <p className="eyebrow">Consulta protetta</p>
      <h2>Apri un backup</h2>
      <p>Seleziona una copia dall'elenco per vedere i personaggi salvati, i loro valori e il contenuto degli zaini.</p>
    </section>;
  }

  const selectedId = inspection.selectedCharacter?.id ?? null;
  return <section className="panel backup-inspector" data-component-type="panel" data-theme="parchment">
    <header className="section-toolbar">
      <div><p className="eyebrow">Consulta in sola lettura</p><h2>{inspection.characterCount} personaggi</h2></div>
      {busy && <small>Caricamento…</small>}
    </header>
    <div className="backup-inspector-layout">
      <aside className="backup-character-list">
        {inspection.characters.map((character) => <button type="button" key={character.id} className={character.id === selectedId ? "active" : ""} disabled={busy} onClick={() => onSelectCharacter(character.id)}>
          <strong>{character.name}</strong>
          <small>{character.type || "Personaggio"} · livello {character.level}</small>
          <span>{character.coreValues.slice(0, 4).map((value) => `${value.label}: ${value.value}`).join(" · ")}</span>
        </button>)}
      </aside>
      <div className="backup-character-pane">
        {inspection.selectedCharacter
          ? <BackupCharacterDetails character={inspection.selectedCharacter} />
          : <p className="muted-copy">Scegli un personaggio per aprire valori e inventario salvati.</p>}
      </div>
    </div>
  </section>;
}


export function BackupManagementPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<BackupConfiguration>(DEFAULT_CONFIGURATION);
  const [label, setLabel] = useState("");
  const [selectedBackupId, setSelectedBackupId] = useState<string | null>(null);
  const [characterQuery, setCharacterQuery] = useState("");
  const overviewQuery = useQuery({
    queryKey: ["management-backups"],
    queryFn: () => getData<BackupManagementData>("/api/v1/management/backups"),
  });
  const overview = overviewQuery.data;

  useEffect(() => {
    if (overview?.configuration) setDraft(overview.configuration);
  }, [overview?.configuration]);

  const updateOverview = (next: BackupManagementData | null | undefined) => {
    if (next) queryClient.setQueryData(["management-backups"], next);
  };
  const saveMutation = useMutation({
    mutationFn: () => command<BackupActionData>("management.backups.saveSettings", { configuration: draft }, "management-backups"),
    onSuccess: (response) => {
      updateOverview(response.data.management);
      notify(response.events[0]?.message || "Configurazione backup salvata.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const createMutation = useMutation({
    mutationFn: () => command<BackupActionData>("management.backups.create", { label: label.trim() }, "management-backups"),
    onSuccess: (response) => {
      const next = response.data.management;
      updateOverview(next);
      setLabel("");
      setSelectedBackupId(next?.createdBackupId || null);
      notify(response.events[0]?.message || "Backup creato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const inspectMutation = useMutation({
    mutationFn: (payload: { backupId: string; characterId?: number }) => command<BackupActionData>("management.backups.inspect", payload, "management-backups"),
    onSuccess: (response, payload) => {
      updateOverview(response.data.management);
      setSelectedBackupId(payload.backupId);
      notify(response.events[0]?.message || "Backup aperto in sola lettura.", "info");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const deleteMutation = useMutation({
    mutationFn: (backupId: string) => command<BackupActionData>("management.backups.delete", { backupId }, "management-backups"),
    onSuccess: (response, backupId) => {
      updateOverview(response.data.management);
      if (selectedBackupId === backupId) setSelectedBackupId(null);
      notify(response.events[0]?.message || "Backup eliminato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const normalizedCharacterQuery = characterQuery.trim().toLocaleLowerCase("it");
  const inspection = overview?.inspection || null;
  const visibleCharacters = useMemo(() => {
    if (!inspection) return [];
    return inspection.characters.filter((character) => !normalizedCharacterQuery || `${character.name} ${character.type}`.toLocaleLowerCase("it").includes(normalizedCharacterQuery));
  }, [inspection, normalizedCharacterQuery]);
  const displayedInspection = inspection && visibleCharacters.length !== inspection.characters.length
    ? { ...inspection, characters: visibleCharacters }
    : inspection;

  return <div className="page backup-management-page" data-component-type="view" data-theme="parchment">
    <header className="page-header">
      <div>
        <p className="eyebrow">Amministrazione</p>
        <h1>Gestione Backup</h1>
        <p>Configura copie automatiche del database, crea snapshot manuali e controlla in sicurezza i dati di una sessione precedente.</p>
      </div>
      <div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link></div>
    </header>

    {overviewQuery.isLoading && <section className="panel"><p>Caricamento dei backup…</p></section>}
    {overviewQuery.error && <section className="panel danger-panel"><p>{(overviewQuery.error as Error).message}</p></section>}
    {overview && <>
      <section className="panel backup-configuration" data-component-type="panel" data-theme="default">
        <header className="section-toolbar"><div><p className="eyebrow">Pianificazione del server</p><h2>Backup automatici</h2></div></header>
        <form onSubmit={(event) => { event.preventDefault(); saveMutation.mutate(); }}>
          <div className="backup-config-grid">
            <label className="backup-toggle"><input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft((current) => ({ ...current, enabled: event.target.checked }))} /><span><strong>Attiva backup automatici</strong><small>Il server crea copie senza interrompere la sessione.</small></span></label>
            <label className="backup-toggle"><input type="checkbox" checked={draft.onStartup} disabled={!draft.enabled} onChange={(event) => setDraft((current) => ({ ...current, onStartup: event.target.checked }))} /><span><strong>Copia all'avvio</strong><small>Salva lo stato subito quando ReDjango si avvia.</small></span></label>
            <label><span>Ogni quanti minuti</span><input type="number" min="5" max="120" step="1" value={draft.intervalMinutes} disabled={!draft.enabled} onChange={(event) => setDraft((current) => ({ ...current, intervalMinutes: Number(event.target.value) }))} /><small>Da 5 a 120 minuti di attività del server.</small></label>
            <label><span>Copie da conservare</span><input type="number" min="1" max="100" step="1" value={draft.retentionCount} onChange={(event) => setDraft((current) => ({ ...current, retentionCount: Number(event.target.value) }))} /><small>Le copie gestite più vecchie vengono rimosse.</small></label>
          </div>
          <div className="button-row"><button className="button primary" disabled={saveMutation.isPending}>{saveMutation.isPending ? "Salvataggio…" : "Salva pianificazione"}</button></div>
        </form>
        <Storage overview={overview} />
      </section>

      <section className="panel backup-manual-create" data-component-type="panel" data-theme="gold">
        <div><p className="eyebrow">Snapshot immediata</p><h2>Crea una copia ora</h2><p>Utile prima di importazioni, modifiche estese o una sessione importante.</p></div>
        <form onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }}>
          <label><span>Etichetta facoltativa</span><input maxLength={120} value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Es. Prima del combattimento finale" /></label>
          <button className="button primary" disabled={createMutation.isPending}>{createMutation.isPending ? "Creazione…" : "Crea backup"}</button>
        </form>
      </section>

      <div className="backup-workspace">
        <section className="panel backup-list" data-component-type="list" data-theme="default">
          <header className="section-toolbar"><div><p className="eyebrow">Copie disponibili</p><h2>Archivio backup</h2></div><strong>{overview.backups.length}</strong></header>
          {overview.backups.length ? <div className="backup-list-entries">{overview.backups.map((backup) => <article key={backup.id} className={selectedBackupId === backup.id ? "active" : ""}>
            <button className="backup-select" disabled={inspectMutation.isPending} onClick={() => inspectMutation.mutate({ backupId: backup.id })}>
              <span><strong>{backup.label || backupKindLabel(backup)}</strong><small>{backupKindLabel(backup)} · {formatDate(backup.createdAt)} · {backup.createdBy}</small></span>
              <em>{formatBytes(backup.sizeBytes)}</em>
            </button>
            <button className="button danger small" type="button" disabled={deleteMutation.isPending} onClick={() => {
              if (confirm(`Eliminare il backup del ${formatDate(backup.createdAt)}? Questa operazione non può essere annullata.`)) deleteMutation.mutate(backup.id);
            }}>Elimina</button>
          </article>)}</div> : <div className="management-empty-state"><strong>Nessun backup gestito</strong><p>Crea la prima copia manuale oppure attendi il prossimo intervallo automatico.</p></div>}
        </section>
        <div className="backup-inspector-column">
          {inspection && <label className="backup-character-search"><span>Cerca nel backup aperto</span><input type="search" value={characterQuery} onChange={(event) => setCharacterQuery(event.target.value)} placeholder="Nome o tipo personaggio…" /></label>}
          <BackupInspector inspection={displayedInspection} busy={inspectMutation.isPending} onSelectCharacter={(characterId) => {
            if (inspection) inspectMutation.mutate({ backupId: inspection.backupId, characterId });
          }} />
        </div>
      </div>
    </>}
  </div>;
}
