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
  SkillReviewDetail,
  SkillReviewSummary,
} from "./types";

type WorkspaceMode = "overview" | "catalog" | "structure" | "review";
type ManagementActionData = { management?: Record<string, unknown>; skill?: UnifiedSkill | null };

const TIER_LABELS: Record<string, string> = { base: "Base", apprentice: "Apprendista", master: "Maestro" };
const REVIEW_STATUS: Record<string, string> = { open: "Da rivedere", imported: "Importata", ignored: "Ignorata" };

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
  return <Modal title={group ? `Modifica ${group.name}` : "Nuovo gruppo di famiglie"} onClose={onClose} footer={null}>
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
  return <><Modal title={family ? `Modifica ${family.name}` : "Nuova famiglia"} onClose={onClose} wide footer={null}>
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

function reviewTemplate(review: SkillReviewDetail): UnifiedSkill {
  const values = review.workingValues || {};
  const spell = values.spell && typeof values.spell === "object" ? values.spell as Record<string, unknown> : null;
  const baseXpCost = Number(values.baseXpCost || 0);
  return {
    id: review.liveSkillId || -review.id,
    slug: String(values.slug || ""),
    number: Number(values.number || review.sourceId),
    name: String(values.name || review.name),
    description: String(values.description || ""),
    familyId: Number(values.familyId || 0),
    familyName: "",
    familyGroup: "",
    familyOrder: Number(values.familyOrder || 0),
    magic: Boolean(values.magic && spell),
    baseXpCost,
    xpCost: baseXpCost,
    pricing: { baseCost: baseXpCost, calculatedCost: baseXpCost, calculatedBeforeOwnedSkillDiscount: baseXpCost, levelSurcharge: 0, spentXpInCategory: 0, surchargeDiscountPercent: 0, ownedSkillDiscount: 0, ownedSkillDiscountSources: [] },
    xpType: String(values.xpType || "all"),
    xpTypeLabel: String(values.xpType || "all"),
    rulesCost: String(values.rulesCost || ""),
    requirementsText: String(values.requirementsText || ""),
    spell: spell ? {
      id: 0,
      tier: String(spell.tier || "base"),
      tierLabel: TIER_LABELS[String(spell.tier || "base")] || String(spell.tier || "base"),
      range: String(spell.range || ""),
      effectUnit: String(spell.effectUnit || "Effetto"),
      baseMana: Number(spell.baseMana || 0),
      effectPerMana: Number(spell.effectPerMana || 1),
      minimumMana: Number(spell.minimumMana || 0),
      rounding: String(spell.rounding || "none"),
      roundingLabel: String(spell.rounding || "none"),
      legacyFormula: String(spell.legacyFormula || ""),
      costNotes: String(spell.costNotes || ""),
      formula: "",
      combatConfiguration: (spell.combatConfiguration || {}) as Record<string, unknown>,
    } : null,
    profileTags: (values.profileTags || {}) as Record<string, unknown>,
    profileNotes: String(values.profileNotes || ""),
    passiveEffects: Array.isArray(values.passiveEffects) ? values.passiveEffects as UnifiedSkill["passiveEffects"] : [],
    activeReminders: Array.isArray(values.activeReminders) ? values.activeReminders as UnifiedSkill["activeReminders"] : [],
    icon: String(values.icon || "runa"),
    notes: String(values.notes || ""),
    metadata: (values.metadata || {}) as Record<string, unknown>,
    archived: false,
    unlock: {
      owned: false,
      canUnlock: false,
      blockedReasons: [],
      prerequisiteIds: Array.isArray(values.prerequisiteIds) ? values.prerequisiteIds.map(Number) : [],
      missingPrerequisiteIds: [], prerequisitesBypassed: false, allowedXpPools: [], acceptedPassiveIds: [], spentXp: {}, note: "", unlockedAt: null,
    },
  };
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
    <div className="skill-management-inspector-metrics"><span><small>Costo base</small><strong>{skill.baseXpCost} PE</strong></span><span><small>Passivi</small><strong>{skill.passiveCount}</strong></span><span><small>Azioni</small><strong>{skill.actionCount}</strong></span><span><small>Prerequisiti</small><strong>{skill.prerequisiteCount}</strong></span></div>
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
  const [reviewQuery, setReviewQuery] = useState("");
  const [reviewStatus, setReviewStatus] = useState("open");
  const [reviewSeverity, setReviewSeverity] = useState("all");
  const [selectedReviewId, setSelectedReviewId] = useState<number | null>(null);
  const [reviewEditorOpen, setReviewEditorOpen] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");

  const overviewQuery = useQuery({ queryKey: ["management-skills"], queryFn: () => getData<SkillManagementOverview>("/api/v1/management/skills") });
  const overview = overviewQuery.data;
  const skillDetailQuery = useQuery({
    queryKey: ["management-skill-detail", selectedSkillId],
    queryFn: () => getData<{ skill: UnifiedSkill }>(`/api/v1/management/skills/${selectedSkillId}`),
    enabled: Boolean(selectedSkillId),
  });
  const reviewDetailQuery = useQuery({
    queryKey: ["management-skill-review", selectedReviewId],
    queryFn: () => getData<{ review: SkillReviewDetail }>(`/api/v1/management/skill-reviews/${selectedReviewId}`),
    enabled: Boolean(selectedReviewId),
  });
  const reviewDetail = reviewDetailQuery.data?.review || null;
  useEffect(() => { if (reviewDetail) setReviewNotes(reviewDetail.resolutionNotes || ""); }, [reviewDetail]);

  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["management-skills"] });
    await queryClient.invalidateQueries({ queryKey: ["management-skill-detail"] });
    await queryClient.invalidateQueries({ queryKey: ["management-skill-review"] });
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
  const reviewSaveMutation = useMutation({
    mutationFn: (values: Record<string, unknown>) => command<ManagementActionData>("management.skills.review.save", { reviewId: selectedReviewId, values, notes: reviewNotes }, "management-skills"),
    onSuccess: async () => { setReviewEditorOpen(false); await invalidate(); notify("Correzione Elder salvata. Ora puoi importarla."); },
    onError: (error: Error) => notify(error.message, "error"),
  });

  const normalized = query.trim().toLocaleLowerCase("it");
  const filteredSkills = useMemo(() => (overview?.skills || []).filter((skill) => {
    const matchesText = !normalized || `${skill.name} ${skill.slug} ${skill.number} ${skill.familyName} ${skill.groupName}`.toLocaleLowerCase("it").includes(normalized);
    return matchesText
      && (!groupFilter || skill.groupId === Number(groupFilter))
      && (!familyFilter || skill.familyId === Number(familyFilter))
      && (stateFilter === "all" || (stateFilter === "archived" ? skill.archived : !skill.archived))
      && (kindFilter === "all" || (kindFilter === "spell" ? skill.magic : !skill.magic));
  }), [overview?.skills, normalized, groupFilter, familyFilter, stateFilter, kindFilter]);
  useEffect(() => {
    if (mode !== "catalog") return;
    if (!filteredSkills.some((skill) => skill.id === selectedSkillId)) setSelectedSkillId(filteredSkills[0]?.id || null);
  }, [filteredSkills, mode, selectedSkillId]);
  const selectedSkill = filteredSkills.find((skill) => skill.id === selectedSkillId) || null;
  const visibleFamilies = (overview?.families || []).filter((family) => !groupFilter || family.groupId === Number(groupFilter));

  const filteredReviews = useMemo(() => (overview?.reviews || []).filter((review) => {
    const needle = reviewQuery.trim().toLocaleLowerCase("it");
    return (!needle || `${review.name} ${review.sourceId} ${review.blockerLabels.join(" ")} ${review.warningLabels.join(" ")}`.toLocaleLowerCase("it").includes(needle))
      && (reviewStatus === "all" || review.status === reviewStatus)
      && (reviewSeverity === "all" || review.severity === reviewSeverity);
  }), [overview?.reviews, reviewQuery, reviewStatus, reviewSeverity]);
  useEffect(() => {
    if (mode !== "review") return;
    if (!filteredReviews.some((review) => review.id === selectedReviewId)) setSelectedReviewId(filteredReviews[0]?.id || null);
  }, [filteredReviews, mode, selectedReviewId]);

  const activeGroups = overview?.groups.filter((group) => !group.archived) || [];
  useEffect(() => {
    if (selectedStructureGroup == null && activeGroups[0]) setSelectedStructureGroup(activeGroups[0].id);
  }, [activeGroups, selectedStructureGroup]);
  const structureGroups = overview?.groups.filter((group) => showArchivedStructure || !group.archived) || [];
  const structureFamilies = overview?.families.filter((family) => family.groupId === selectedStructureGroup && (showArchivedStructure || !family.archived)) || [];
  const selectedGroup = overview?.groups.find((group) => group.id === selectedStructureGroup) || null;
  const suggestedNumber = Math.max(0, ...(overview?.skills.map((skill) => skill.number) || [0])) + 1;

  const saveGroup = (values: Record<string, unknown>) => managementMutation.mutate({ action: "management.skills.group.save", payload: { groupId: groupEditor?.id, values }, success: "Gruppo salvato." }, { onSuccess: () => setGroupEditor(undefined) });
  const saveFamily = (values: Record<string, unknown>) => managementMutation.mutate({ action: "management.skills.family.save", payload: { familyId: familyEditor?.id, values }, success: "Famiglia salvata." }, { onSuccess: () => setFamilyEditor(undefined) });
  const saveSkill = (values: Record<string, unknown>) => skillMutation.mutate({ action: skillEditor === "edit" ? "skills.update" : "skills.create", skillId: skillEditor === "edit" ? selectedSkillId || undefined : undefined, values });

  return <div className="page management-page skill-management-page">
    <header className="page-header"><div><p className="eyebrow">Gestione del gioco</p><h1>Gestione Skill</h1><p>Catalogo, struttura e migrazione Elder in un'unica postazione.</p></div><div className="button-row"><Link className="button secondary" to="/tools">Tutti gli strumenti</Link><button className="button primary" onClick={() => setSkillEditor("create")}>Crea skill</button></div></header>
    <nav className="management-mode-tabs skill-management-tabs" role="tablist" aria-label="Aree Gestione Skill">
      {(["overview", "catalog", "structure", "review"] as WorkspaceMode[]).map((entry) => <button key={entry} role="tab" aria-selected={mode === entry} className={mode === entry ? "active" : ""} onClick={() => setMode(entry)}>{entry === "overview" ? "Panoramica" : entry === "catalog" ? "Catalogo completo" : entry === "structure" ? "Gruppi e famiglie" : "Revisione Elder"}{entry === "review" && <span>{overview?.metrics.openReviews || 0}</span>}</button>)}
    </nav>
    {overviewQuery.isLoading && <section className="panel"><p>Preparazione del catalogo completo…</p></section>}
    {overviewQuery.error && <section className="panel danger-panel"><p>{(overviewQuery.error as Error).message}</p></section>}

    {overview && <section className="skill-management-metrics" data-component-type="grid" data-theme="default"><Metric label="Skill attive" value={overview.metrics.activeSkills} /><Metric label="Incantesimi" value={overview.metrics.spells} tone="arcane" /><Metric label="Famiglie" value={overview.metrics.families} /><Metric label="Gruppi" value={overview.metrics.groups} /><Metric label="Da rivedere" value={overview.metrics.openReviews} tone={overview.metrics.blockedReviews ? "danger" : "default"} /><Metric label="Archiviate" value={overview.metrics.archivedSkills} /></section>}

    {overview && mode === "overview" && <div className="skill-management-overview">
      <section className="panel skill-structure-atlas" data-component-type="panel" data-theme="default"><header><div><p className="eyebrow">Atlante della struttura</p><h2>Tutto il catalogo a colpo d'occhio</h2></div><button className="button secondary" onClick={() => setMode("structure")}>Gestisci struttura</button></header><div className="skill-group-overview-grid">{overview.groups.filter((group) => !group.archived).map((group) => <article key={group.id} data-component-type="card" data-theme="parchment"><header><span>{group.familyCount}</span><div><small>Gruppo</small><h3>{group.name}</h3></div><strong>{group.skillCount} skill</strong></header><div>{overview.families.filter((family) => !family.archived && family.groupId === group.id).map((family) => <button key={family.id} onClick={() => { setGroupFilter(String(group.id)); setFamilyFilter(String(family.id)); setMode("catalog"); }}><span>{family.name}</span><b>{family.activeSkillCount}{family.spellCount ? ` · ${family.spellCount} ✦` : ""}</b></button>)}</div></article>)}</div></section>
      <aside className="panel skill-review-callout" data-component-type="panel" data-theme={overview.metrics.blockedReviews ? "danger" : "success"}><div><span aria-hidden="true">⌁</span><p className="eyebrow">Migrazione controllata</p><h2>{overview.metrics.openReviews ? `${overview.metrics.openReviews} record Elder richiedono attenzione` : "Coda Elder sotto controllo"}</h2><p>Le skill ambigue non entrano nel gioco finché non vengono corrette e importate da questa postazione. Anche gli avvisi sulle skill già copiate restano consultabili.</p></div><button className="button primary" onClick={() => setMode("review")}>Apri revisione Elder</button></aside>
    </div>}

    {overview && mode === "catalog" && <>
      <section className="panel management-filterbar skill-management-filters" data-component-type="toolbar" data-theme="default"><label>Cerca<input type="search" value={query} placeholder="Nome, numero, famiglia, slug…" onChange={(event) => setQuery(event.target.value)} /></label><label>Gruppo<select value={groupFilter} onChange={(event) => { setGroupFilter(event.target.value); setFamilyFilter(""); }}><option value="">Tutti</option>{activeGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label><label>Famiglia<select value={familyFilter} onChange={(event) => setFamilyFilter(event.target.value)}><option value="">Tutte</option>{visibleFamilies.filter((family) => !family.archived).map((family) => <option key={family.id} value={family.id}>{family.name}</option>)}</select></label><label>Stato<select value={stateFilter} onChange={(event) => setStateFilter(event.target.value as typeof stateFilter)}><option value="active">Attive</option><option value="archived">Archiviate</option><option value="all">Tutte</option></select></label><label>Tipo<select value={kindFilter} onChange={(event) => setKindFilter(event.target.value as typeof kindFilter)}><option value="all">Skill e magie</option><option value="skill">Solo skill</option><option value="spell">Solo magie</option></select></label><strong>{filteredSkills.length}</strong></section>
      <div className="skill-management-catalog-layout"><section className="panel skill-management-table" data-component-type="table" data-theme="default"><div className="skill-management-table-head"><span>#</span><span>Skill</span><span>Struttura</span><span>PE</span><span>Contenuto</span></div><div className="skill-management-table-body">{filteredSkills.map((skill) => <button key={skill.id} className={selectedSkillId === skill.id ? "active" : ""} data-state={skill.archived ? "archived" : "active"} onClick={() => setSelectedSkillId(skill.id)}><span>{skill.number}</span><span><strong>{skill.name}</strong><small>{skill.magic ? `✦ ${TIER_LABELS[skill.spellTier || ""] || "Magia"}` : skill.slug}</small></span><span><strong>{skill.familyName}</strong><small>{skill.groupName}</small></span><span>{skill.baseXpCost} <small>{skill.xpTypeLabel}</small></span><span>{skill.passiveCount} P · {skill.actionCount} A</span></button>)}</div>{!filteredSkills.length && <div className="management-empty-state"><strong>Nessuna skill trovata</strong><p>Cambia filtri o ricerca.</p></div>}</section><SkillInspector skill={selectedSkill} loading={skillDetailQuery.isFetching || managementMutation.isPending} onEdit={() => setSkillEditor("edit")} onState={() => selectedSkill && managementMutation.mutate({ action: "management.skills.skill.state", payload: { skillId: selectedSkill.id, archived: !selectedSkill.archived }, success: selectedSkill.archived ? "Skill ripristinata." : "Skill archiviata." })} /></div>
    </>}

    {overview && mode === "structure" && <div className="skill-management-structure">
      <section className="panel skill-group-manager" data-component-type="panel" data-theme="dark"><header><div><p className="eyebrow">Livello 1</p><h2>Gruppi di famiglie</h2></div><button className="button primary small" onClick={() => setGroupEditor(null)}>Nuovo gruppo</button></header><label className="inline-check"><input type="checkbox" checked={showArchivedStructure} onChange={(event) => setShowArchivedStructure(event.target.checked)} /> Mostra archiviati</label><div>{structureGroups.map((group) => <button key={group.id} className={selectedStructureGroup === group.id ? "active" : ""} data-state={group.archived ? "archived" : "active"} onClick={() => setSelectedStructureGroup(group.id)}><span><strong>{group.name}</strong><small>{group.familyCount} famiglie · {group.skillCount} skill</small></span><b>{group.order}</b></button>)}</div></section>
      <section className="panel skill-family-manager" data-component-type="panel" data-theme="parchment"><header><div><p className="eyebrow">Livello 2</p><h2>{selectedGroup?.name || "Famiglie"}</h2><p>{selectedGroup?.notes || "Organizza le famiglie e il loro contenuto."}</p></div><div className="button-row">{selectedGroup && <button className="button secondary small" onClick={() => setGroupEditor(selectedGroup)}>Modifica gruppo</button>}{selectedGroup && <button className="button secondary small" onClick={() => managementMutation.mutate({ action: "management.skills.group.state", payload: { groupId: selectedGroup.id, archived: !selectedGroup.archived }, success: selectedGroup.archived ? "Gruppo ripristinato." : "Gruppo archiviato." })}>{selectedGroup.archived ? "Ripristina" : "Archivia"}</button>}<button className="button primary small" disabled={!selectedGroup || selectedGroup.archived} onClick={() => setFamilyEditor(null)}>Nuova famiglia</button></div></header><div className="skill-family-management-grid">{structureFamilies.map((family) => <article key={family.id} data-component-type="card" data-theme={family.spellCount ? "arcane" : "parchment"} data-state={family.archived ? "archived" : "active"}>{family.imageUrl ? <img src={family.imageUrl} alt="" /> : <span className="skill-family-placeholder">✧</span>}<div><small>Ordine {family.order} · {family.group}</small><h3>{family.name}</h3><p>{family.notes || "Nessuna descrizione."}</p><dl><span><dt>Attive</dt><dd>{family.activeSkillCount}</dd></span><span><dt>Magie</dt><dd>{family.spellCount}</dd></span><span><dt>Archiviate</dt><dd>{family.archivedSkillCount}</dd></span></dl></div><footer><button onClick={() => { setGroupFilter(String(family.groupId)); setFamilyFilter(String(family.id)); setMode("catalog"); }}>Apri catalogo</button><button onClick={() => setFamilyEditor(family)}>Modifica</button><button className="danger" onClick={() => managementMutation.mutate({ action: "management.skills.family.state", payload: { familyId: family.id, archived: !family.archived }, success: family.archived ? "Famiglia ripristinata." : "Famiglia archiviata." })}>{family.archived ? "Ripristina" : "Archivia"}</button></footer></article>)}</div>{!structureFamilies.length && <div className="management-empty-state"><strong>Nessuna famiglia in questo gruppo</strong><p>Creane una per iniziare a organizzare le skill.</p></div>}</section>
    </div>}

    {overview && mode === "review" && <>
      <section className="panel skill-review-toolbar" data-component-type="toolbar" data-theme="default"><div><p className="eyebrow">Sorgente controllata</p><h2>Revisione the_elder_django</h2><p>Correggi le proposte che non erano abbastanza sicure da importare; le modifiche successive a una sorgente già copiata riaprono automaticamente il controllo.</p></div><button className="button secondary" disabled={managementMutation.isPending} onClick={() => managementMutation.mutate({ action: "management.skills.review.sync", payload: {}, success: "Coda Elder sincronizzata." })}>{managementMutation.isPending ? "Analisi in corso…" : "Aggiorna dalla sorgente Elder"}</button></section>
      <section className="panel management-filterbar skill-review-filters"><label>Cerca<input type="search" value={reviewQuery} placeholder="Nome, ID Elder, problema…" onChange={(event) => setReviewQuery(event.target.value)} /></label><label>Stato<select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}><option value="open">Da rivedere</option><option value="imported">Importate</option><option value="ignored">Ignorate</option><option value="all">Tutte</option></select></label><label>Tipo<select value={reviewSeverity} onChange={(event) => setReviewSeverity(event.target.value)}><option value="all">Blocchi e avvisi</option><option value="blocked">Bloccanti</option><option value="warning">Avvisi</option></select></label><strong>{filteredReviews.length}</strong></section>
      <div className="skill-review-layout"><aside className="panel skill-review-list" data-component-type="list" data-theme="dark">{filteredReviews.map((review) => <button key={review.id} className={selectedReviewId === review.id ? "active" : ""} data-severity={review.severity} data-state={review.status} onClick={() => setSelectedReviewId(review.id)}><span><strong>{review.name}</strong><small>Elder #{review.sourceId} · {REVIEW_STATUS[review.status]}</small></span><b>{review.severity === "blocked" ? review.blockers.length : review.warnings.length}</b></button>)}{!filteredReviews.length && <div className="management-empty-state"><strong>Nessun record</strong><p>Aggiorna la sorgente o cambia i filtri.</p></div>}</aside><section className="panel skill-review-inspector" data-component-type="inspector" data-theme={reviewDetail?.severity === "blocked" ? "danger" : "gold"}>{reviewDetailQuery.isLoading && <p>Caricamento della sorgente…</p>}{reviewDetail && <><header><div><p className="eyebrow">Elder #{reviewDetail.sourceId} · {reviewDetail.severity === "blocked" ? "Bloccante" : "Avviso"}</p><h2>{reviewDetail.name}</h2><p>{reviewDetail.liveSkillId ? `Collegata alla skill live #${reviewDetail.liveSkillId}` : "Non ancora presente nel catalogo live"}</p></div><span data-state={reviewDetail.status}>{REVIEW_STATUS[reviewDetail.status]}</span></header><section className="skill-review-issues">{reviewDetail.blockerLabels.map((label, index) => <article key={`b-${index}`} data-theme="danger"><strong>Da risolvere</strong><p>{label}</p><code>{reviewDetail.blockers[index]}</code></article>)}{reviewDetail.warningLabels.map((label, index) => <article key={`w-${index}`} data-theme="gold"><strong>Controllo consigliato</strong><p>{label}</p><code>{reviewDetail.warnings[index]}</code></article>)}</section><div className="skill-review-comparison"><article><small>Sorgente Elder</small><dl><div><dt>Famiglia</dt><dd>{String(reviewDetail.source.source_family_name || "—")}</dd></div><div><dt>Costo PE</dt><dd>{String(reviewDetail.source.costo_pe ?? "—")}</dd></div><div><dt>Costo regola</dt><dd>{String(reviewDetail.source.costo || "—")}</dd></div><div><dt>Formula</dt><dd>{String(reviewDetail.source.formula_effetto || "—")}</dd></div><div><dt>Requisiti</dt><dd>{String(reviewDetail.source.requisiti || "—")}</dd></div></dl><p>{String(reviewDetail.source.descrizione || "Nessuna descrizione Elder.")}</p></article><article><small>Correzione ReDjango</small><dl><div><dt>Famiglia</dt><dd>{overview.families.find((family) => family.id === Number(reviewDetail.workingValues.familyId))?.name || "Da scegliere"}</dd></div><div><dt>Costo PE base</dt><dd>{String(reviewDetail.workingValues.baseXpCost ?? "—")}</dd></div><div><dt>Tipo</dt><dd>{reviewDetail.workingValues.magic ? "Incantesimo separato" : "Skill"}</dd></div><div><dt>Passivi</dt><dd>{Array.isArray(reviewDetail.workingValues.passiveEffects) ? reviewDetail.workingValues.passiveEffects.length : 0}</dd></div><div><dt>Azioni</dt><dd>{Array.isArray(reviewDetail.workingValues.activeReminders) ? reviewDetail.workingValues.activeReminders.length : 0}</dd></div></dl><p>{String(reviewDetail.workingValues.description || "Nessuna descrizione proposta.")}</p></article></div><label className="skill-review-notes">Note della revisione<textarea rows={3} value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} placeholder="Annota la decisione presa o ciò che resta da controllare…" /></label><footer><div>{reviewDetail.status === "ignored" ? <button className="button secondary" onClick={() => managementMutation.mutate({ action: "management.skills.review.status", payload: { reviewId: reviewDetail.id, status: "open" }, success: "Revisione riaperta." })}>Riapri</button> : <button className="button secondary" onClick={() => managementMutation.mutate({ action: "management.skills.review.status", payload: { reviewId: reviewDetail.id, status: "ignored" }, success: "Revisione ignorata." })}>Ignora</button>}</div><div><button className="button secondary" onClick={() => setReviewEditorOpen(true)}>Correggi proposta</button><button className="button primary" disabled={managementMutation.isPending || reviewDetail.status === "imported"} onClick={() => managementMutation.mutate({ action: "management.skills.review.import", payload: { reviewId: reviewDetail.id }, success: "Correzione importata nel catalogo." })}>{reviewDetail.liveSkillId ? "Applica alla skill live" : "Importa nel gioco"}</button></div></footer></>}</section></div>
    </>}

    {skillEditor && overview && <Modal title={skillEditor === "edit" ? `Modifica ${selectedSkill?.name || "skill"}` : "Crea skill"} onClose={() => setSkillEditor(null)} wide>{skillEditor === "edit" && skillDetailQuery.isLoading ? <p>Caricamento editor…</p> : <SkillEditor skill={skillEditor === "edit" ? skillDetailQuery.data?.skill || null : null} suggestedNumber={suggestedNumber} families={overview.families.filter((family) => !family.archived) as unknown as SkillFamily[]} skillOptions={overview.skillOptions} effectConfiguration={overview.effectConfiguration} saving={skillMutation.isPending} onSave={saveSkill} onCancel={() => setSkillEditor(null)} />}</Modal>}
    {groupEditor !== undefined && <GroupEditor group={groupEditor} saving={managementMutation.isPending} onClose={() => setGroupEditor(undefined)} onSave={saveGroup} />}
    {familyEditor !== undefined && overview && <FamilyEditor family={familyEditor} groups={overview.groups} saving={managementMutation.isPending} onClose={() => setFamilyEditor(undefined)} onSave={saveFamily} />}
    {reviewEditorOpen && reviewDetail && overview && <Modal title={`Correggi ${reviewDetail.name}`} onClose={() => setReviewEditorOpen(false)} wide><SkillEditor skill={null} templateSkill={reviewTemplate(reviewDetail)} families={overview.families.filter((family) => !family.archived) as unknown as SkillFamily[]} skillOptions={overview.skillOptions} effectConfiguration={overview.effectConfiguration} saving={reviewSaveMutation.isPending} onSave={(values) => reviewSaveMutation.mutate(values)} onCancel={() => setReviewEditorOpen(false)} submitLabel="Salva correzione" allowTemplateIdentity /></Modal>}
  </div>;
}
