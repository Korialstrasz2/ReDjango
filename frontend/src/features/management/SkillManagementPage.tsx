import { type FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { useApp } from "../../App";
import { ImagePickerModal } from "../../components/ImagePickerModal";
import { Modal } from "../../components/Modal";
import { command, getData } from "../../lib/api";
import type { SkillFamily } from "../../lib/types";
import { SkillEditor } from "../skills/SkillEditor";
import type { UnifiedSkill } from "../skills/types";
import type {
  ManagedSkillFamily,
  ManagedSkillGroup,
  ManagedSkillRow,
  SkillManagementOverview,
} from "./types";

type WorkspaceMode = "overview" | "catalog" | "structure";
type ManagementActionData = { management?: Record<string, unknown>; skill?: UnifiedSkill | null };

const SKILL_PAGE_SIZE = 100;

// The reorder action renumbers whichever list it receives, so moving one entry
// means sending the whole sequence in its new order.
function moveWithin(identifiers: number[], index: number, direction: -1 | 1): number[] {
  const target = index + direction;
  if (target < 0 || target >= identifiers.length) return identifiers;
  const next = [...identifiers];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

const TIER_LABELS: Record<string, string> = { base: "Base", apprentice: "Apprendista", master: "Maestro" };

function Metric({ label, value, tone = "default" }: { label: string; value: number; tone?: string }) {
  return <article data-theme={tone}><small>{label}</small><strong>{value}</strong></article>;
}

function GroupEditor({ group, saving, onClose, onSave }: {
  group: ManagedSkillGroup | null;
  saving: boolean;
  onClose: () => void;
  onSave: (values: Record<string, unknown>) => void;
}) {
  const [name, setName] = useState(group?.name || "");
  const [slug, setSlug] = useState(group?.slug || "");
  const [order, setOrder] = useState(String(group?.order ?? 0));
  const [notes, setNotes] = useState(group?.notes || "");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSave({ name, slug, order, notes });
  };
  return <Modal surface="tools" title={group ? `Modifica ${group.name}` : "Nuovo gruppo di famiglie"} onClose={onClose} footer={null}>
    <form className="stacked-form" onSubmit={submit} data-component-type="form" data-theme="default">
      <label>Nome<input value={name} maxLength={80} required autoFocus onChange={(event) => setName(event.target.value)} /></label>
      <label>Slug stabile<input value={slug} maxLength={100} placeholder="Generato dal nome" onChange={(event) => setSlug(event.target.value)} /></label>
      <label>Ordine<input type="number" min="0" value={order} onChange={(event) => setOrder(event.target.value)} /></label>
      <label>Note<textarea rows={5} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
      <div className="skill-management-form-actions"><button type="button" className="button secondary" onClick={onClose}>Annulla</button><button className="button primary" disabled={saving || !name.trim()}>Salva gruppo</button></div>
    </form>
  </Modal>;
}

function FamilyEditor({ family, groups, saving, onClose, onSave }: {
  family: ManagedSkillFamily | null;
  groups: ManagedSkillGroup[];
  saving: boolean;
  onClose: () => void;
  onSave: (values: Record<string, unknown>) => void;
}) {
  const { media } = useApp();
  const activeGroups = groups.filter((group) => !group.archived);
  const [name, setName] = useState(family?.name || "");
  const [groupId, setGroupId] = useState(String(family?.groupId || activeGroups[0]?.id || ""));
  const [order, setOrder] = useState(String(family?.order ?? 0));
  const [notes, setNotes] = useState(family?.notes || "");
  const [additionalNotes, setAdditionalNotes] = useState(family?.additionalNotes || "");
  const [isClass, setIsClass] = useState(Boolean(family?.isClass));
  const [isReligion, setIsReligion] = useState(Boolean(family?.isReligion));
  const [isPerk, setIsPerk] = useState(Boolean(family?.isPerk));
  const [imageId, setImageId] = useState<number | null>(family?.imageId || null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const image = media.find((asset) => asset.id === imageId) || null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSave({ name, groupId, order, notes, additionalNotes, isClass, isReligion, isPerk, imageId });
  };
  return <><Modal surface="tools" title={family ? `Modifica ${family.name}` : "Nuova famiglia"} onClose={onClose} wide footer={null}>
    <form className="skill-family-management-form" onSubmit={submit} data-component-type="form" data-theme="parchment">
      <div className="management-form-grid">
        <label>Nome<input value={name} maxLength={160} required autoFocus onChange={(event) => setName(event.target.value)} /></label>
        <label>Gruppo<select value={groupId} required onChange={(event) => setGroupId(event.target.value)}>{activeGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label>
        <label>Ordine<input type="number" min="0" value={order} onChange={(event) => setOrder(event.target.value)} /></label>
        <label className="wide">Descrizione breve<textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
        <label className="wide">Note aggiuntive<textarea rows={4} value={additionalNotes} onChange={(event) => setAdditionalNotes(event.target.value)} /></label>
      </div>
      <div className="skill-family-flags"><label><input type="checkbox" checked={isClass} onChange={(event) => setIsClass(event.target.checked)} /> Famiglia di classe</label><label><input type="checkbox" checked={isReligion} onChange={(event) => setIsReligion(event.target.checked)} /> Religione</label><label><input type="checkbox" checked={isPerk} onChange={(event) => setIsPerk(event.target.checked)} /> Perk</label></div>
      <button type="button" className="skill-family-art-picker" onClick={() => setPickerOpen(true)}>{image ? <><img src={image.thumbnailUrl || image.url} alt="" /><span><strong>{image.title}</strong><small>Cambia immagine</small></span></> : <span><strong>Nessuna immagine</strong><small>Scegli dall'archivio</small></span>}</button>
      <div className="skill-management-form-actions"><button type="button" className="button secondary" onClick={onClose}>Annulla</button><button className="button primary" disabled={saving || !name.trim() || !groupId}>Salva famiglia</button></div>
    </form>
  </Modal>{pickerOpen && <ImagePickerModal selectedId={imageId} usageType="skill_family" defaultGroup="Famiglie abilità" defaultTitle={name || "Nuova famiglia"} onSelect={(asset) => setImageId(asset?.id || null)} onClose={() => setPickerOpen(false)} />}</>;
}

function SkillInspector({ skill, loading, onEdit, onState }: {
  skill: ManagedSkillRow | null;
  loading: boolean;
  onEdit: () => void;
  onState: () => void;
}) {
  if (!skill) return <div className="management-empty-state"><strong>Nessuna skill selezionata</strong><p>Scegli una riga dal catalogo.</p></div>;
  return <section className="panel skill-management-inspector" data-component-type="inspector" data-theme={skill.magic ? "arcane" : "parchment"}>
    <header><div><p className="eyebrow">#{skill.number} · {skill.groupName}</p><h2>{skill.name}</h2><p>{skill.familyName}</p></div><span className={`skill-management-state ${skill.archived ? "archived" : "active"}`}>{skill.archived ? "Archiviata" : "Attiva"}</span></header>
    <div className="skill-management-inspector-metrics"><span><small>Costo base</small><strong>{skill.baseXpCost} PE</strong></span><span><small>Passivi</small><strong>{skill.passiveCount}</strong></span><span><small>Azioni</small><strong>{skill.actionCount}</strong></span><span><small>Prerequisiti</small><strong>{skill.prerequisiteCount}</strong></span><span><small>Posseduta da</small><strong>{skill.ownerCount}</strong></span></div>
    {skill.ownerCount > 0 && <p className="form-warning">{skill.ownerCount} {skill.ownerCount === 1 ? "personaggio ha" : "personaggi hanno"} già acquistato questa skill: cambiare costo, tipo di PE o prerequisiti riscrive ciò per cui hanno pagato.</p>}
    <dl><div><dt>Tipo PE</dt><dd>{skill.xpTypeLabel}</dd></div><div><dt>Tipo</dt><dd>{skill.magic ? `Incantesimo · ${TIER_LABELS[skill.spellTier || ""] || skill.spellTier}` : "Abilità"}</dd></div><div><dt>Provenienza</dt><dd>{skill.sourceProject ? `Elder #${skill.sourceId}` : "ReDjango"}</dd></div></dl>
    <footer><button className="button secondary" disabled={loading} onClick={onState}>{skill.archived ? "Ripristina" : "Archivia"}</button><button className="button primary" disabled={loading} onClick={onEdit}>Modifica completa</button></footer>
  </section>;
}

export function SkillManagementPage() {
  const { notify } = useApp();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<WorkspaceMode>("overview");
  const [query, setQuery] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [familyFilter, setFamilyFilter] = useState("");
  const [stateFilter, setStateFilter] = useState<"active" | "archived" | "all">("active");
  const [kindFilter, setKindFilter] = useState<"all" | "skill" | "spell">("all");
  const [selectedSkillId, setSelectedSkillId] = useState<number | null>(null);
  const [skillEditor, setSkillEditor] = useState<"create" | "edit" | null>(null);
  const [groupEditor, setGroupEditor] = useState<ManagedSkillGroup | null | undefined>(undefined);
  const [familyEditor, setFamilyEditor] = useState<ManagedSkillFamily | null | undefined>(undefined);
  const [selectedStructureGroup, setSelectedStructureGroup] = useState<number | null>(null);
  const [showArchivedStructure, setShowArchivedStructure] = useState(false);
  const [queryInput, setQueryInput] = useState("");
  const [offset, setOffset] = useState(0);

  // The catalogue is over 1500 rows: filtering happens in the database and the
  // page only ever holds one page of results.
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(queryInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [queryInput]);
  useEffect(() => setOffset(0), [query, groupFilter, familyFilter, stateFilter, kindFilter]);
  const skillParameters = new URLSearchParams({
    query,
    group_id: groupFilter || "0",
    family_id: familyFilter || "0",
    state: stateFilter === "all" ? "" : stateFilter,
    kind: kindFilter === "all" ? "" : kindFilter,
    offset: String(offset),
    limit: String(SKILL_PAGE_SIZE),
  });
  const overviewQuery = useQuery({
    queryKey: ["management-skills", skillParameters.toString()],
    queryFn: () => getData<SkillManagementOverview>(`/api/v1/management/skills?${skillParameters}`),
    placeholderData: (previous) => previous,
  });
  const overview = overviewQuery.data;
  const skillDetailQuery = useQuery({
    queryKey: ["management-skill-detail", selectedSkillId],
    queryFn: () => getData<{ skill: UnifiedSkill }>(`/api/v1/management/skills/${selectedSkillId}`),
    enabled: Boolean(selectedSkillId),
  });
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["management-skills"] });
    await queryClient.invalidateQueries({ queryKey: ["management-skill-detail"] });
    await queryClient.invalidateQueries({ queryKey: ["skills"] });
  };
  const managementMutation = useMutation({
    mutationFn: ({ action, payload }: { action: string; payload: Record<string, unknown>; success: string }) => command<ManagementActionData>(action, payload, "management-skills"),
    onSuccess: async (_, variables) => { await invalidate(); notify(variables.success); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const skillMutation = useMutation({
    mutationFn: ({ action, skillId, values }: { action: string; skillId?: number; values?: Record<string, unknown> }) => command<ManagementActionData>(action, { skillId, values: values || {} }, "management-skills"),
    onSuccess: async () => { setSkillEditor(null); await invalidate(); notify("Catalogo skill aggiornato."); },
    onError: (error: Error) => notify(error.message, "error"),
  });
  const filteredSkills = overview?.skills || [];
  useEffect(() => {
    if (mode !== "catalog") return;
    if (!filteredSkills.some((skill) => skill.id === selectedSkillId)) setSelectedSkillId(filteredSkills[0]?.id || null);
  }, [filteredSkills, mode, selectedSkillId]);
  const selectedSkill = filteredSkills.find((skill) => skill.id === selectedSkillId) || null;
  const visibleFamilies = (overview?.families || []).filter((family) => !groupFilter || family.groupId === Number(groupFilter));

  const activeGroups = overview?.groups.filter((group) => !group.archived) || [];
  useEffect(() => {
    if (selectedStructureGroup == null && activeGroups[0]) setSelectedStructureGroup(activeGroups[0].id);
  }, [activeGroups, selectedStructureGroup]);
  const structureGroups = overview?.groups.filter((group) => showArchivedStructure || !group.archived) || [];
  const structureFamilies = overview?.families.filter((family) => family.groupId === selectedStructureGroup && (showArchivedStructure || !family.archived)) || [];
  const selectedGroup = overview?.groups.find((group) => group.id === selectedStructureGroup) || null;
  const suggestedNumber = Math.max(0, ...(overview?.skillOptions.map((skill) => skill.number) || [0])) + 1;
  const reorder = (kind: "groups" | "families", identifiers: number[]) => managementMutation.mutate({
    action: "management.skills.structure.reorder",
    payload: { [kind]: identifiers },
    success: "Ordine aggiornato.",
  });

  const saveGroup = (values: Record<string, unknown>) => managementMutation.mutate({ action: "management.skills.group.save", payload: { groupId: groupEditor?.id, values }, success: "Gruppo salvato." }, { onSuccess: () => setGroupEditor(undefined) });
  const saveFamily = (values: Record<string, unknown>) => managementMutation.mutate({ action: "management.skills.family.save", payload: { familyId: familyEditor?.id, values }, success: "Famiglia salvata." }, { onSuccess: () => setFamilyEditor(undefined) });
  const saveSkill = (values: Record<string, unknown>) => skillMutation.mutate({ action: skillEditor === "edit" ? "skills.update" : "skills.create", skillId: skillEditor === "edit" ? selectedSkillId || undefined : undefined, values });

  return <div className="page management-page skill-management-page">
    <header className="page-header"><div><p className="eyebrow">Gestione del gioco</p><h1>Gestione Skill</h1><p>Catalogo, struttura e migrazione Elder in un'unica postazione.</p></div><div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link><button className="button primary" onClick={() => setSkillEditor("create")}>Crea skill</button></div></header>
    <nav className="management-mode-tabs skill-management-tabs" role="tablist" aria-label="Aree Gestione Skill">
      {(["overview", "catalog", "structure"] as WorkspaceMode[]).map((entry) => <button key={entry} role="tab" aria-selected={mode === entry} className={mode === entry ? "active" : ""} onClick={() => setMode(entry)}>{entry === "overview" ? "Panoramica" : entry === "catalog" ? "Catalogo completo" : "Gruppi e famiglie"}</button>)}
    </nav>
    {overviewQuery.isLoading && <section className="panel"><p>Preparazione del catalogo completo…</p></section>}
    {overviewQuery.error && <section className="panel danger-panel"><p>{(overviewQuery.error as Error).message}</p></section>}

    {overview && <section className="skill-management-metrics" data-component-type="grid" data-theme="default"><Metric label="Skill attive" value={overview.metrics.activeSkills} /><Metric label="Incantesimi" value={overview.metrics.spells} tone="arcane" /><Metric label="Famiglie" value={overview.metrics.families} /><Metric label="Gruppi" value={overview.metrics.groups} /><Metric label="Archiviate" value={overview.metrics.archivedSkills} /></section>}

    {overview && mode === "overview" && <div className="skill-management-overview">
      <section className="panel skill-structure-atlas" data-component-type="panel" data-theme="default"><header><div><p className="eyebrow">Atlante della struttura</p><h2>Tutto il catalogo a colpo d'occhio</h2></div><button className="button secondary" onClick={() => setMode("structure")}>Gestisci struttura</button></header><div className="skill-group-overview-grid">{overview.groups.filter((group) => !group.archived).map((group) => <article key={group.id} data-component-type="card" data-theme="parchment"><header><span>{group.familyCount}</span><div><small>Gruppo</small><h3>{group.name}</h3></div><strong>{group.skillCount} skill</strong></header><div>{overview.families.filter((family) => !family.archived && family.groupId === group.id).map((family) => <button key={family.id} onClick={() => { setGroupFilter(String(group.id)); setFamilyFilter(String(family.id)); setMode("catalog"); }}><span>{family.name}</span><b>{family.activeSkillCount}{family.spellCount ? ` · ${family.spellCount} ✦` : ""}</b></button>)}</div></article>)}</div></section>

    </div>}

    {overview && mode === "catalog" && <>
      <section className="panel management-filterbar skill-management-filters" data-component-type="toolbar" data-theme="default"><label>Cerca<input type="search" value={query} placeholder="Nome, numero, famiglia, slug…" onChange={(event) => setQuery(event.target.value)} /></label><label>Gruppo<select value={groupFilter} onChange={(event) => { setGroupFilter(event.target.value); setFamilyFilter(""); }}><option value="">Tutti</option>{activeGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><label>Famiglia<select value={familyFilter} onChange={(event) => setFamilyFilter(event.target.value)}><option value="">Tutte</option>{visibleFamilies.filter((family) => !family.archived).map((family) => <option key={family.id} value={family.id}>{family.name}</option>)}</select></label><label>Stato<select value={stateFilter} onChange={(event) => setStateFilter(event.target.value as typeof stateFilter)}><option value="active">Attive</option><option value="archived">Archiviate</option><option value="all">Tutte</option></select></label><label>Tipo<select value={kindFilter} onChange={(event) => setKindFilter(event.target.value as typeof kindFilter)}><option value="all">Skill e magie</option><option value="skill">Solo skill</option><option value="spell">Solo magie</option></select></label><strong>{overview.total}</strong></section>
      <div className="skill-management-catalog-layout"><section className="panel skill-management-table" data-component-type="table" data-theme="default"><div className="skill-management-table-head"><span>#</span><span>Skill</span><span>Struttura</span><span>PE</span><span>Contenuto</span></div><div className="skill-management-table-body">{filteredSkills.map((skill) => <button key={skill.id} className={selectedSkillId === skill.id ? "active" : ""} data-state={skill.archived ? "archived" : "active"} onClick={() => setSelectedSkillId(skill.id)}><span>{skill.number}</span><span><strong>{skill.name}</strong><small>{skill.magic ? `✦ ${TIER_LABELS[skill.spellTier || ""] || "Magia"}` : skill.slug}</small></span><span><strong>{skill.familyName}</strong><small>{skill.groupName}</small></span><span>{skill.baseXpCost} <small>{skill.xpTypeLabel}</small></span><span>{skill.passiveCount} P · {skill.actionCount} A</span></button>)}</div>{!filteredSkills.length && <div className="management-empty-state"><strong>Nessuna skill trovata</strong><p>Cambia filtri o ricerca.</p></div>}<footer className="managed-item-pager"><button type="button" className="button secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - SKILL_PAGE_SIZE))}>← Precedenti</button><span>{Math.floor(offset / SKILL_PAGE_SIZE) + 1} / {Math.max(1, Math.ceil(overview.total / SKILL_PAGE_SIZE))} · {overview.total} skill</span><button type="button" className="button secondary small" disabled={!overview.hasMore} onClick={() => setOffset(offset + SKILL_PAGE_SIZE)}>Successivi →</button></footer></section><SkillInspector skill={selectedSkill} loading={skillDetailQuery.isFetching || managementMutation.isPending} onEdit={() => setSkillEditor("edit")} onState={() => selectedSkill && managementMutation.mutate({ action: "management.skills.skill.state", payload: { skillId: selectedSkill.id, archived: !selectedSkill.archived }, success: selectedSkill.archived ? "Skill ripristinata." : "Skill archiviata." })} /></div>
    </>}

    {overview && mode === "structure" && <div className="skill-management-structure">
      <section className="panel skill-group-manager" data-component-type="panel" data-theme="dark"><header><div><p className="eyebrow">Livello 1</p><h2>Gruppi di famiglie</h2></div><button className="button primary small" onClick={() => setGroupEditor(null)}>Nuovo gruppo</button></header><label className="inline-check"><input type="checkbox" checked={showArchivedStructure} onChange={(event) => setShowArchivedStructure(event.target.checked)} /> Mostra archiviati</label><div>{structureGroups.map((group, index) => <div key={group.id} className="skill-structure-row">
        <button className={selectedStructureGroup === group.id ? "active" : ""} data-state={group.archived ? "archived" : "active"} onClick={() => setSelectedStructureGroup(group.id)}><span><strong>{group.name}</strong><small>{group.familyCount} famiglie · {group.skillCount} skill</small></span><b>{group.order}</b></button>
        <span className="shop-structure-move">
          <button type="button" aria-label={`Sposta ${group.name} prima`} disabled={index === 0 || managementMutation.isPending} onClick={() => reorder("groups", moveWithin(structureGroups.map((entry) => entry.id), index, -1))}>↑</button>
          <button type="button" aria-label={`Sposta ${group.name} dopo`} disabled={index === structureGroups.length - 1 || managementMutation.isPending} onClick={() => reorder("groups", moveWithin(structureGroups.map((entry) => entry.id), index, 1))}>↓</button>
        </span>
      </div>)}</div></section>
      <section className="panel skill-family-manager" data-component-type="panel" data-theme="parchment"><header><div><p className="eyebrow">Livello 2</p><h2>{selectedGroup?.name || "Famiglie"}</h2><p>{selectedGroup?.notes || "Organizza le famiglie e il loro contenuto."}</p></div><div className="button-row">{selectedGroup && <button className="button secondary small" onClick={() => setGroupEditor(selectedGroup)}>Modifica gruppo</button>}{selectedGroup && <button className="button secondary small" onClick={() => managementMutation.mutate({ action: "management.skills.group.state", payload: { groupId: selectedGroup.id, archived: !selectedGroup.archived }, success: selectedGroup.archived ? "Gruppo ripristinato." : "Gruppo archiviato." })}>{selectedGroup.archived ? "Ripristina" : "Archivia"}</button>}<button className="button primary small" disabled={!selectedGroup || selectedGroup.archived} onClick={() => setFamilyEditor(null)}>Nuova famiglia</button></div></header><div className="skill-family-management-grid">{structureFamilies.map((family, familyIndex) => <article key={family.id} data-component-type="card" data-theme={family.spellCount ? "arcane" : "parchment"} data-state={family.archived ? "archived" : "active"}>{family.imageUrl ? <img src={family.imageUrl} alt="" /> : <span className="skill-family-placeholder">✧</span>}<div><small>Ordine {family.order} · {family.group}</small><h3>{family.name}</h3><p>{family.notes || "Nessuna descrizione."}</p><dl><span><dt>Attive</dt><dd>{family.activeSkillCount}</dd></span><span><dt>Magie</dt><dd>{family.spellCount}</dd></span><span><dt>Archiviate</dt><dd>{family.archivedSkillCount}</dd></span></dl></div><footer><button disabled={familyIndex === 0 || managementMutation.isPending} onClick={() => reorder("families", moveWithin(structureFamilies.map((entry) => entry.id), familyIndex, -1))}>↑</button><button disabled={familyIndex === structureFamilies.length - 1 || managementMutation.isPending} onClick={() => reorder("families", moveWithin(structureFamilies.map((entry) => entry.id), familyIndex, 1))}>↓</button><button onClick={() => { setGroupFilter(String(family.groupId)); setFamilyFilter(String(family.id)); setMode("catalog"); }}>Apri catalogo</button><button onClick={() => setFamilyEditor(family)}>Modifica</button><button className="danger" onClick={() => managementMutation.mutate({ action: "management.skills.family.state", payload: { familyId: family.id, archived: !family.archived }, success: family.archived ? "Famiglia ripristinata." : "Famiglia archiviata." })}>{family.archived ? "Ripristina" : "Archivia"}</button></footer></article>)}</div>{!structureFamilies.length && <div className="management-empty-state"><strong>Nessuna famiglia in questo gruppo</strong><p>Creane una per iniziare a organizzare le skill.</p></div>}</section>
    </div>}

    {skillEditor && overview && <Modal surface="tools" title={skillEditor === "edit" ? `Modifica ${selectedSkill?.name || "skill"}` : "Crea skill"} onClose={() => setSkillEditor(null)} wide>{skillEditor === "edit" && skillDetailQuery.isLoading ? <p>Caricamento editor…</p> : <SkillEditor skill={skillEditor === "edit" ? skillDetailQuery.data?.skill || null : null} suggestedNumber={suggestedNumber} families={overview.families.filter((family) => !family.archived) as unknown as SkillFamily[]} skillOptions={overview.skillOptions} effectConfiguration={overview.effectConfiguration} saving={skillMutation.isPending} onSave={saveSkill} onCancel={() => setSkillEditor(null)} />}</Modal>}
    {groupEditor !== undefined && <GroupEditor group={groupEditor} saving={managementMutation.isPending} onClose={() => setGroupEditor(undefined)} onSave={saveGroup} />}
    {familyEditor !== undefined && overview && <FamilyEditor family={familyEditor} groups={overview.groups} saving={managementMutation.isPending} onClose={() => setFamilyEditor(undefined)} onSave={saveFamily} />}
  </div>;
}
