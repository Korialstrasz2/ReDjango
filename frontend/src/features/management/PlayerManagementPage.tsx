import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { Modal } from "../../components/Modal";
import { command, getData } from "../../lib/api";
import type { ManagedPlayer, PlayerManagementOverview } from "./types";

type PlayerActionData = { management?: PlayerManagementOverview | null };

type ProfileDraft = {
  name: string;
  displayName: string;
  username: string;
  role: string;
  activeCampaignId: string;
  accountActive: boolean;
};

function profileDraft(player: ManagedPlayer): ProfileDraft {
  return {
    name: player.name,
    displayName: player.displayName,
    username: player.username,
    role: player.role,
    activeCampaignId: player.activeCampaignId ? String(player.activeCampaignId) : "",
    accountActive: player.accountActive,
  };
}

function usePlayerMutation(action: string, onDone: (overview: PlayerManagementOverview) => void) {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) => command<PlayerActionData>(action, payload, "management-players"),
    onSuccess: async (response) => {
      const overview = response.data.management;
      if (overview) {
        queryClient.setQueryData(["management-players"], overview);
        onDone(overview);
      } else {
        await queryClient.invalidateQueries({ queryKey: ["management-players"] });
      }
      // The signed-in admin may have just renamed themselves or moved campaign.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["settings"] }),
        queryClient.invalidateQueries({ queryKey: ["personaggi"] }),
      ]);
      notify(response.events[0]?.message || "Giocatore aggiornato.");
    },
    onError: (error: Error) => notify(error.message, "error"),
  });
}

function NewPlayerForm({ overview, onCreated }: { overview: PlayerManagementOverview; onCreated: (playerId: number | null) => void }) {
  const [values, setValues] = useState({ name: "", displayName: "", username: "", password: "", role: "user", activeCampaignId: "" });
  const createMutation = usePlayerMutation("management.players.create", (updated) => onCreated(updated.savedPlayerId));
  const update = (key: keyof typeof values, value: string) => setValues((current) => ({ ...current, [key]: value }));
  return <form className="player-create-form" onSubmit={(event) => {
    event.preventDefault();
    createMutation.mutate({ values: { ...values, username: values.username.trim() || values.name.trim() } });
  }}>
    <div className="management-form-grid">
      <label><span>Nome giocatore</span><input value={values.name} maxLength={120} required onChange={(event) => update("name", event.target.value)} /></label>
      <label><span>Alias mostrato</span><input value={values.displayName} maxLength={120} placeholder="Come il nome" onChange={(event) => update("displayName", event.target.value)} /></label>
      <label><span>Nome utente</span><input value={values.username} maxLength={150} placeholder="Come il nome" autoComplete="off" onChange={(event) => update("username", event.target.value)} /></label>
      <label><span>Password</span><input type="password" value={values.password} required autoComplete="new-password" onChange={(event) => update("password", event.target.value)} /></label>
      <label><span>Livello di accesso</span><select value={values.role} onChange={(event) => update("role", event.target.value)}>{overview.roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select></label>
      <label><span>Campagna attiva</span><select value={values.activeCampaignId} onChange={(event) => update("activeCampaignId", event.target.value)}>{overview.campaigns.map((campaign) => <option key={campaign.value} value={campaign.value}>{campaign.label}</option>)}</select></label>
    </div>
    {overview.passwordHelp.length > 0 && <ul className="player-password-help">{overview.passwordHelp.map((rule) => <li key={rule}>{rule}</li>)}</ul>}
    <div className="button-row">
      <button className="button primary" disabled={createMutation.isPending || !values.name.trim() || !values.password}>{createMutation.isPending ? "Creazione…" : "Crea giocatore"}</button>
    </div>
  </form>;
}

function PasswordForm({ player, overview }: { player: ManagedPlayer; overview: PlayerManagementOverview }) {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const passwordMutation = usePlayerMutation("management.players.setPassword", () => { setPassword(""); setRepeat(""); });
  const mismatch = Boolean(repeat) && password !== repeat;
  return <form className="player-password-form" onSubmit={(event) => {
    event.preventDefault();
    passwordMutation.mutate({ playerId: player.id, password });
  }}>
    <div className="section-toolbar"><div><p className="eyebrow">Credenziali</p><h3>Cambia password</h3></div></div>
    {player.hasAccount
      ? <>
        <p className="muted-copy">La password viene sostituita senza mai essere mostrata: comunicala tu a {player.displayName}. Le sessioni già aperte restano valide.</p>
        <div className="management-form-grid">
          <label><span>Nuova password</span><input type="password" value={password} autoComplete="new-password" onChange={(event) => setPassword(event.target.value)} /></label>
          <label><span>Ripeti password</span><input type="password" value={repeat} autoComplete="new-password" aria-invalid={mismatch || undefined} onChange={(event) => setRepeat(event.target.value)} /></label>
        </div>
        {mismatch && <p className="form-error" role="alert">Le due password non coincidono.</p>}
        {overview.passwordHelp.length > 0 && <ul className="player-password-help">{overview.passwordHelp.map((rule) => <li key={rule}>{rule}</li>)}</ul>}
        <div className="button-row"><button className="button primary" disabled={passwordMutation.isPending || !password || mismatch}>{passwordMutation.isPending ? "Salvataggio…" : "Imposta password"}</button></div>
      </>
      : <div className="management-empty-state"><strong>Nessun account di accesso</strong><p>Questo profilo non è collegato a un account: assegnagli un nome utente e una password dalla scheda Profilo.</p></div>}
  </form>;
}

function CharacterAssignment({ player, overview }: { player: ManagedPlayer; overview: PlayerManagementOverview }) {
  const [selected, setSelected] = useState<number[]>(() => player.characters.map((character) => character.id));
  const [query, setQuery] = useState("");
  const [onlyPlayable, setOnlyPlayable] = useState(true);
  useEffect(() => setSelected(player.characters.map((character) => character.id)), [player]);
  const assignMutation = usePlayerMutation("management.players.assignCharacters", () => undefined);
  const normalized = query.trim().toLocaleLowerCase("it");
  const visible = overview.characters.filter((character) => {
    const matches = !normalized || `${character.name} ${character.campaignName} ${character.type}`.toLocaleLowerCase("it").includes(normalized);
    // A character already assigned stays visible even when the filters exclude it,
    // otherwise saving would silently drop it from the roster.
    return selected.includes(character.id) || (matches && (!onlyPlayable || character.type === "giocabile"));
  });
  const toggle = (characterId: number, checked: boolean) => setSelected((current) => (
    checked ? [...current, characterId] : current.filter((entry) => entry !== characterId)
  ));
  const dirty = selected.length !== player.characters.length
    || selected.some((characterId) => !player.characters.some((character) => character.id === characterId));

  return <section className="player-assignment" aria-label={`Personaggi di ${player.displayName}`}>
    <div className="section-toolbar">
      <div><p className="eyebrow">Compagnia</p><h3>Personaggi assegnati</h3></div>
      <span className="player-assignment-count">{selected.length} selezionati</span>
    </div>
    <p className="muted-copy">{player.roleLabel === "Giocatore" ? "Nella Sala principale questo giocatore vede soltanto i personaggi spuntati qui." : "Master e amministratori vedono tutti i personaggi della campagna: qui definisci comunque la loro compagnia personale."}</p>
    {player.pendingRequests.length > 0 && <div className="player-pending-requests">
      <strong>Richieste in attesa</strong>
      <ul>{player.pendingRequests.map((request) => <li key={request.characterId}>
        <button type="button" onClick={() => toggle(request.characterId, !selected.includes(request.characterId))}>{request.characterName}</button>
        {request.message && <small>{request.message}</small>}
      </li>)}</ul>
      <small>Spuntare un personaggio richiesto e salvare approva la richiesta.</small>
    </div>}
    <div className="player-assignment-filters">
      <label><span>Cerca</span><input type="search" value={query} placeholder="Nome, campagna o tipo…" onChange={(event) => setQuery(event.target.value)} /></label>
      <label className="inline-check"><input type="checkbox" checked={onlyPlayable} onChange={(event) => setOnlyPlayable(event.target.checked)} /> Solo personaggi giocabili</label>
    </div>
    <div className="player-character-picker">
      {visible.map((character) => {
        const others = character.assignedTo.filter((name) => name !== player.displayName);
        return <label key={character.id} data-selected={selected.includes(character.id) || undefined}>
          <input type="checkbox" checked={selected.includes(character.id)} onChange={(event) => toggle(character.id, event.target.checked)} />
          <span>
            <strong>{character.name}</strong>
            <small>{character.type} · livello {character.level} · {character.campaignName || "senza campagna"}</small>
            {others.length > 0 && <em>Anche di {others.join(", ")}</em>}
          </span>
        </label>;
      })}
      {!visible.length && <p className="muted-copy">Nessun personaggio corrisponde al filtro.</p>}
    </div>
    {player.missingCharacterIds.length > 0 && <p className="form-error" role="alert">Assegnazioni verso personaggi eliminati o archiviati: {player.missingCharacterIds.join(", ")}. Salva per rimuoverle.</p>}
    <div className="button-row">
      <button className="button primary" type="button" disabled={assignMutation.isPending || (!dirty && !player.missingCharacterIds.length)} onClick={() => assignMutation.mutate({ playerId: player.id, characterIds: selected })}>{assignMutation.isPending ? "Salvataggio…" : "Salva assegnazioni"}</button>
      <button className="button secondary" type="button" disabled={!dirty} onClick={() => setSelected(player.characters.map((character) => character.id))}>Annulla modifiche</button>
    </div>
  </section>;
}

function PlayerEditor({ player, overview }: { player: ManagedPlayer; overview: PlayerManagementOverview }) {
  const [section, setSection] = useState<"profile" | "password" | "characters">("profile");
  const [draft, setDraft] = useState<ProfileDraft>(() => profileDraft(player));
  const [newAccountPassword, setNewAccountPassword] = useState("");
  useEffect(() => { setDraft(profileDraft(player)); setNewAccountPassword(""); }, [player]);
  const saveMutation = usePlayerMutation("management.players.update", () => undefined);
  const isSelf = overview.currentPlayerId === player.id;

  return <section className="panel management-editor" data-component-type="panel" data-theme="default">
    <header className="management-editor-header">
      <div>
        <p className="eyebrow">#{player.id} · {player.roleLabel}{isSelf ? " · sei tu" : ""}</p>
        <h2>{player.displayName}</h2>
        <p>{player.hasAccount ? `Accesso: ${player.username}${player.accountActive ? "" : " · disattivato"}` : "Nessun account di accesso"} · {player.activeCampaignName || "nessuna campagna"}</p>
      </div>
      <div className="button-row">{player.activeCharacterId && <Link className="button secondary" to={`/character/${player.activeCharacterId}`}>Apri {player.activeCharacterName}</Link>}</div>
    </header>
    <nav className="management-record-tabs" aria-label="Dati del giocatore">
      <button className={section === "profile" ? "active" : ""} onClick={() => setSection("profile")}>Profilo</button>
      <button className={section === "password" ? "active" : ""} onClick={() => setSection("password")}>Password</button>
      <button className={section === "characters" ? "active" : ""} onClick={() => setSection("characters")}>Personaggi · {player.characters.length}</button>
    </nav>

    {section === "profile" && <form className="profile-editor-groups" onSubmit={(event) => {
      event.preventDefault();
      saveMutation.mutate({
        playerId: player.id,
        values: {
          name: draft.name,
          displayName: draft.displayName,
          role: draft.role,
          activeCampaignId: draft.activeCampaignId,
          username: draft.username,
          accountActive: draft.accountActive,
          ...(player.hasAccount ? {} : { password: newAccountPassword }),
        },
      });
    }}>
      <fieldset><legend>Identità</legend><div className="management-form-grid">
        <label><span>Nome giocatore</span><input value={draft.name} maxLength={120} required onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
        <label><span>Alias mostrato</span><input value={draft.displayName} maxLength={120} onChange={(event) => setDraft({ ...draft, displayName: event.target.value })} /></label>
        <label><span>Campagna attiva</span><select value={draft.activeCampaignId} onChange={(event) => setDraft({ ...draft, activeCampaignId: event.target.value })}>{overview.campaigns.map((campaign) => <option key={campaign.value} value={campaign.value}>{campaign.label}</option>)}</select></label>
      </div></fieldset>
      <fieldset><legend>Accesso</legend><div className="management-form-grid">
        <label><span>Nome utente</span><input value={draft.username} maxLength={150} autoComplete="off" onChange={(event) => setDraft({ ...draft, username: event.target.value })} /></label>
        <label><span>Livello di accesso</span><select value={draft.role} disabled={isSelf} onChange={(event) => setDraft({ ...draft, role: event.target.value })}>{overview.roles.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select></label>
        {player.hasAccount
          ? <label><span>Accesso attivo</span><input type="checkbox" checked={draft.accountActive} disabled={isSelf} onChange={(event) => setDraft({ ...draft, accountActive: event.target.checked })} /></label>
          : <label><span>Password iniziale</span><input type="password" value={newAccountPassword} autoComplete="new-password" onChange={(event) => setNewAccountPassword(event.target.value)} /></label>}
      </div>
      {isSelf && <p className="muted-copy">Il tuo livello di accesso e il tuo stato si cambiano da Impostazioni → Profilo, così non puoi chiuderti fuori.</p>}
      {player.canUseDjangoAdmin && <p className="muted-copy">Questo account è staff o superuser di Django: quei permessi si modificano solo dall'Amministrazione Django.</p>}
      </fieldset>
      <div className="button-row"><button className="button primary" disabled={saveMutation.isPending}>{saveMutation.isPending ? "Salvataggio…" : "Salva profilo"}</button></div>
    </form>}
    {section === "password" && <div className="profile-editor-groups"><PasswordForm player={player} overview={overview} /></div>}
    {section === "characters" && <div className="profile-editor-groups"><CharacterAssignment key={player.id} player={player} overview={overview} /></div>}
  </section>;
}

export function PlayerManagementPage() {
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const overviewQuery = useQuery({
    queryKey: ["management-players"],
    queryFn: () => getData<PlayerManagementOverview>("/api/v1/management/players"),
  });
  const overview = overviewQuery.data;
  useEffect(() => {
    if (!overview?.players.length) return;
    if (!selectedId || !overview.players.some((player) => player.id === selectedId)) {
      setSelectedId(overview.currentPlayerId && overview.players.some((player) => player.id === overview.currentPlayerId)
        ? overview.currentPlayerId
        : overview.players[0].id);
    }
  }, [overview, selectedId]);
  const normalized = query.trim().toLocaleLowerCase("it");
  const players = useMemo(() => (overview?.players || []).filter((player) => {
    const matches = !normalized || `${player.name} ${player.displayName} ${player.username}`.toLocaleLowerCase("it").includes(normalized);
    return matches && (!roleFilter || player.role === roleFilter);
  }), [overview, normalized, roleFilter]);
  const selected = overview?.players.find((player) => player.id === selectedId);

  return <div className="page management-page">
    <header className="page-header">
      <div><p className="eyebrow">Gestione del gioco</p><h1>Giocatori e accessi</h1></div>
      <div className="button-row"><button className="button primary" type="button" onClick={() => setShowCreate(true)}>Nuovo giocatore</button><Link className="button secondary" to="/tools">Tutti gli strumenti</Link></div>
    </header>
    <section className="panel management-filterbar" data-component-type="toolbar" data-theme="default">
      <label>Cerca<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nome, alias o nome utente…" /></label>
      <label>Livello di accesso<select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}><option value="">Tutti</option>{(overview?.roles || []).map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select></label>
      <strong>{players.length} giocatori</strong>
    </section>
    {overviewQuery.isLoading && <section className="panel"><p>Caricamento giocatori…</p></section>}
    {overviewQuery.error && <section className="panel danger-panel"><p>{(overviewQuery.error as Error).message}</p></section>}
    {overview && <div className="character-management-layout">
      <aside className="panel managed-character-list">
        <header><strong>{players.length} giocatori</strong><small>Seleziona un profilo da gestire</small></header>
        {players.map((player) => <button key={player.id} className={selectedId === player.id ? "active" : ""} onClick={() => setSelectedId(player.id)}>
          <span><strong>{player.displayName}</strong><small>{player.roleLabel} · {player.characters.length} personaggi{player.hasAccount ? "" : " · senza accesso"}</small></span>
          {player.pendingRequests.length > 0 && <b title="Richieste in attesa">{player.pendingRequests.length}</b>}
        </button>)}
        {!players.length && <p className="muted-copy">Nessun giocatore corrisponde al filtro.</p>}
      </aside>
      <div>{selected
        ? <PlayerEditor key={selected.id} player={selected} overview={overview} />
        : <div className="management-empty-state"><strong>Nessun giocatore selezionato</strong><p>Crea il primo giocatore per assegnargli un personaggio.</p></div>}</div>
    </div>}
    {showCreate && overview && <Modal surface="tools" title="Nuovo giocatore" onClose={() => setShowCreate(false)} wide>
      <NewPlayerForm overview={overview} onCreated={(playerId) => { setShowCreate(false); if (playerId) setSelectedId(playerId); }} />
    </Modal>}
  </div>;
}
