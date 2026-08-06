from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
COMBAT = ROOT / "frontend/src/features/combat/CombatPage.tsx"
ROLES = ROOT / "frontend/tests/mobile-combat-roles.spec.ts"
CONFIRM = ROOT / "frontend/src/components/ConfirmationModal.tsx"
CONFIRM_CSS = ROOT / "frontend/src/components/ConfirmationModal.css"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return source.replace(old, new, 1)


CONFIRM.write_text('''import { type ReactNode } from "react";

import { Modal } from "./Modal";
import "./ConfirmationModal.css";

type Props = {
  title: string;
  message: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmationModal({
  title,
  message,
  confirmLabel,
  cancelLabel = "Annulla",
  busy = false,
  destructive = false,
  onCancel,
  onConfirm,
}: Props) {
  return <Modal
    surface="confirmation"
    title={title}
    onClose={onCancel}
    closeOnBackdrop={false}
    className={`confirmation-modal ${destructive ? "destructive" : ""}`}
    footer={<>
      <button className="button secondary" type="button" data-modal-initial-focus onClick={onCancel}>{cancelLabel}</button>
      <button className={destructive ? "button primary confirmation-danger" : "button primary"} type="button" disabled={busy} onClick={onConfirm}>{confirmLabel}</button>
    </>}
  >
    <div className="confirmation-modal-copy">
      <span className="confirmation-modal-glyph" aria-hidden="true">{destructive ? "!" : "?"}</span>
      <div>{message}</div>
    </div>
  </Modal>;
}
''', encoding="utf-8")

CONFIRM_CSS.write_text('''.confirmation-modal {
  width: min(520px, calc(100vw - 32px));
}

.confirmation-modal-copy {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.confirmation-modal-copy p {
  margin: 0;
  line-height: 1.55;
}

.confirmation-modal-glyph {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  color: var(--accent-strong);
  font-size: 1.4rem;
  font-weight: 800;
}

.confirmation-modal.destructive .confirmation-modal-glyph {
  background: color-mix(in srgb, var(--danger, #b94a48) 16%, transparent);
  color: var(--danger, #d96b68);
}

.confirmation-danger {
  border-color: color-mix(in srgb, var(--danger, #b94a48) 65%, var(--line));
}

@media (max-width: 767px) {
  .confirmation-modal-copy {
    grid-template-columns: 40px minmax(0, 1fr);
    gap: 12px;
  }

  .confirmation-modal-glyph {
    width: 40px;
    height: 40px;
  }
}
''', encoding="utf-8")

source = COMBAT.read_text(encoding="utf-8")
source = replace_once(
    source,
    'import { ImagePickerModal } from "../../components/ImagePickerModal";\nimport { Modal } from "../../components/Modal";',
    'import { ConfirmationModal } from "../../components/ConfirmationModal";\nimport { ImagePickerModal } from "../../components/ImagePickerModal";\nimport { Modal } from "../../components/Modal";',
    "confirmation import",
)

versions_pattern = re.compile(r'function MapVersionsModal\(.*?\n}\n\nfunction CharacterContextModal', re.S)
versions_match = versions_pattern.search(source)
if not versions_match:
    raise RuntimeError("MapVersionsModal block not found")
versions_replacement = '''function MapVersionsModal({ map, busy, onClose, onCreate, onRestore, onDuplicate }: {
  map: CombatMap; busy: boolean; onClose: () => void;
  onCreate: (label: string) => void; onRestore: (snapshotId: number) => void; onDuplicate: (name: string) => void;
}) {
  const [label, setLabel] = useState("");
  const [duplicateName, setDuplicateName] = useState(`${map.name} (copia)`);
  const [restoreSnapshot, setRestoreSnapshot] = useState<CombatMap["snapshots"][number] | null>(null);
  const confirmRestore = () => {
    if (!restoreSnapshot) return;
    const snapshotId = restoreSnapshot.id;
    setRestoreSnapshot(null);
    onRestore(snapshotId);
  };
  return <>
    <Modal surface="combat-map-backups" title="Backup e copie della mappa" onClose={onClose} wide footer={<button className="button secondary" onClick={onClose}>Chiudi</button>}>
      <div className="combat-version-layout" data-component-type="panel" data-theme="combat">
        <section><h3>Crea backup</h3><p>Salva griglia, nebbia, personaggi, sagome e modificatori.</p><label>Etichetta<input value={label} onChange={(event) => setLabel(event.target.value)} placeholder={`Revisione ${map.revision}`} /></label><button className="button primary" disabled={busy} onClick={() => { onCreate(label || `Revisione ${map.revision}`); setLabel(""); }}>Crea backup</button></section>
        <section><h3>Duplica mappa</h3><p>La copia è indipendente e parte dalla revisione 1.</p><label>Nome<input value={duplicateName} onChange={(event) => setDuplicateName(event.target.value)} /></label><button className="button primary" disabled={busy || !duplicateName.trim()} onClick={() => onDuplicate(duplicateName.trim())}>Duplica</button></section>
        <section className="combat-snapshot-list"><h3>Versioni disponibili</h3>{map.snapshots.length ? map.snapshots.map((snapshot) => <article key={snapshot.id}><div><strong>{snapshot.label}</strong><small>rev. {snapshot.revision} · {new Date(snapshot.createdAt).toLocaleString("it")} · {snapshot.createdBy}</small></div><button className="button secondary small" disabled={busy} onClick={() => setRestoreSnapshot(snapshot)}>Ripristina</button></article>) : <p>Nessun backup disponibile.</p>}</section>
      </div>
    </Modal>
    {restoreSnapshot && <ConfirmationModal
      title="Ripristinare il backup?"
      message={<p><strong>{restoreSnapshot.label}</strong> sostituirà lo stato corrente della mappa. Prima del ripristino verrà creato automaticamente un backup dello stato attuale.</p>}
      confirmLabel="Ripristina backup"
      busy={busy}
      destructive
      onCancel={() => setRestoreSnapshot(null)}
      onConfirm={confirmRestore}
    />}
  </>;
}

function CharacterContextModal'''
source = source[:versions_match.start()] + versions_replacement + source[versions_match.end():]

source = replace_once(
    source,
    'function QuickActionsPanel({ map, paths, busy, notify, onCreate, onCommit, onDelete, onClearQueue, onSaveActionSettings }: {',
    'type QuickActionConfirmation =\n  | { kind: "duplicate"; name: string; payload: Record<string, unknown> }\n  | { kind: "clear"; count: number; actionIds: number[] };\n\nfunction QuickActionsPanel({ map, paths, busy, notify, onCreate, onCommit, onDelete, onClearQueue, onSaveActionSettings }: {',
    "quick confirmation type",
)
source = replace_once(
    source,
    '  const [tagsExpanded, setTagsExpanded] = useState(false);',
    '  const [tagsExpanded, setTagsExpanded] = useState(false);\n  const [confirmation, setConfirmation] = useState<QuickActionConfirmation | null>(null);',
    "quick confirmation state",
)
old_actions = '''  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const alreadyQueued = pendingActions.some((entry) => entry.actionType === actionType
      && entry.name.trim().toLocaleLowerCase("it") === name.trim().toLocaleLowerCase("it"));
    if (alreadyQueued && !confirm(`“${name}” è già in coda e non è ancora stata pagata. Aggiungerla una seconda volta?`)) return;
    const effectNote = selectedKey === "movement" ? "" : `Effetto ${spellIntensity}${selectedOption?.spell?.effectUnit ? ` ${selectedOption.spell.effectUnit}` : ""} · Mana richiesto ${requiredMana}`;
    const powerNote = actionType === "cast" ? `Potere usato ${powerUsed} · Potere gratis ${freePower}` : "";
    onCreate({ characterId, actionType, name, description: [description, effectNote, powerNote].filter(Boolean).join(" · "), costs: resolvedCosts, sourceSkillId, path: actionType === "movement" ? paths?.fastest.path || [] : [] });
  };
  const clearQueue = () => {
    if (!pendingActions.length) return;
    if (!confirm(`Svuotare la coda? ${pendingActions.length} azioni non pagate verranno rimosse. Le azioni già pagate restano nello storico.`)) return;
    onClearQueue(pendingActions.map((entry) => entry.id));
  };'''
new_actions = '''  const plannedActionPayload = () => {
    const effectNote = selectedKey === "movement" ? "" : `Effetto ${spellIntensity}${selectedOption?.spell?.effectUnit ? ` ${selectedOption.spell.effectUnit}` : ""} · Mana richiesto ${requiredMana}`;
    const powerNote = actionType === "cast" ? `Potere usato ${powerUsed} · Potere gratis ${freePower}` : "";
    return { characterId, actionType, name, description: [description, effectNote, powerNote].filter(Boolean).join(" · "), costs: resolvedCosts, sourceSkillId, path: actionType === "movement" ? paths?.fastest.path || [] : [] };
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = plannedActionPayload();
    const alreadyQueued = pendingActions.some((entry) => entry.actionType === actionType
      && entry.name.trim().toLocaleLowerCase("it") === name.trim().toLocaleLowerCase("it"));
    if (alreadyQueued) {
      setConfirmation({ kind: "duplicate", name, payload });
      return;
    }
    onCreate(payload);
  };
  const clearQueue = () => {
    if (!pendingActions.length) return;
    setConfirmation({ kind: "clear", count: pendingActions.length, actionIds: pendingActions.map((entry) => entry.id) });
  };
  const confirmPendingAction = () => {
    if (!confirmation) return;
    if (confirmation.kind === "duplicate") onCreate(confirmation.payload);
    else onClearQueue(confirmation.actionIds);
    setConfirmation(null);
  };'''
source = replace_once(source, old_actions, new_actions, "quick action handlers")
source = replace_once(source, '  return <div className="combat-quick-actions">', '  return <>\n    <div className="combat-quick-actions">', "quick return start")
old_tail = '''    <aside className="combat-quick-side"><section className="combat-quick-notes"><header><strong>Note</strong><span>Salvataggio automatico</span></header>{characterId && <NoteSectionEditor characterId={characterId} section="combat" notify={notify} rows={6} compact minimal />}</section><section className="combat-quick-queue"><header><strong>Coda azioni</strong><span>{pendingActions.length} da pagare</span><button type="button" className="combat-quick-queue-reset" disabled={busy || !pendingActions.length} onClick={clearQueue} title="Rimuove tutte le azioni non ancora pagate">Svuota</button></header><div className="planned-action-list">{actions.map((action) => <article key={action.id} className={action.committedAt ? "committed" : ""}>
      <span className={`action-glyph ${action.actionType}`}>{({ movement: "↝", attack: "⚔", cast: "✦", power: "◆", other: "•" } as Record<string, string>)[action.actionType]}</span>
      <div><strong>{action.name}</strong><small>{Object.entries(action.costs).filter(([, value]) => value).map(([key, value]) => `${value} ${key.toUpperCase()}`).join(" · ") || "Nessun costo"}{action.path.length ? ` · ${action.path.length - 1} esagoni` : ""}</small>{action.description && <p>{action.description}</p>}</div>
      {action.committedAt ? <span className="paid">Pagata</span> : <div><button disabled={busy} onClick={() => onCommit(action.id)}>Paga</button><button disabled={busy} onClick={() => onDelete(action.id)}>×</button></div>}
    </article>)}</div>{!actions.length && <p className="combat-quick-empty">La coda è vuota. Scegli Movimento o una delle azioni sbloccate.</p>}<p className="planner-note">Solo “Paga” scala le risorse. La coda non impone un ordine di turno.</p></section></aside>
  </div>;
}'''
new_tail = '''    <aside className="combat-quick-side"><section className="combat-quick-notes"><header><strong>Note</strong><span>Salvataggio automatico</span></header>{characterId && <NoteSectionEditor characterId={characterId} section="combat" notify={notify} rows={6} compact minimal />}</section><section className="combat-quick-queue"><header><strong>Coda azioni</strong><span>{pendingActions.length} da pagare</span><button type="button" className="combat-quick-queue-reset" disabled={busy || !pendingActions.length} onClick={clearQueue} title="Rimuove tutte le azioni non ancora pagate">Svuota</button></header><div className="planned-action-list">{actions.map((action) => <article key={action.id} className={action.committedAt ? "committed" : ""}>
      <span className={`action-glyph ${action.actionType}`}>{({ movement: "↝", attack: "⚔", cast: "✦", power: "◆", other: "•" } as Record<string, string>)[action.actionType]}</span>
      <div><strong>{action.name}</strong><small>{Object.entries(action.costs).filter(([, value]) => value).map(([key, value]) => `${value} ${key.toUpperCase()}`).join(" · ") || "Nessun costo"}{action.path.length ? ` · ${action.path.length - 1} esagoni` : ""}</small>{action.description && <p>{action.description}</p>}</div>
      {action.committedAt ? <span className="paid">Pagata</span> : <div><button disabled={busy} onClick={() => onCommit(action.id)}>Paga</button><button disabled={busy} onClick={() => onDelete(action.id)}>×</button></div>}
    </article>)}</div>{!actions.length && <p className="combat-quick-empty">La coda è vuota. Scegli Movimento o una delle azioni sbloccate.</p>}<p className="planner-note">Solo “Paga” scala le risorse. La coda non impone un ordine di turno.</p></section></aside>
    </div>
    {confirmation && <ConfirmationModal
      title={confirmation.kind === "duplicate" ? "Aggiungere un duplicato?" : "Svuotare la coda?"}
      message={confirmation.kind === "duplicate"
        ? <p><strong>{confirmation.name}</strong> è già presente nella coda e non è ancora stata pagata. Vuoi aggiungerla una seconda volta?</p>
        : <p>{confirmation.count} azioni non pagate verranno rimosse. Le azioni già pagate resteranno nello storico.</p>}
      confirmLabel={confirmation.kind === "duplicate" ? "Aggiungi comunque" : "Rimuovi azioni"}
      busy={busy}
      destructive={confirmation.kind === "clear"}
      onCancel={() => setConfirmation(null)}
      onConfirm={confirmPendingAction}
    />}
  </>;
}'''
source = replace_once(source, old_tail, new_tail, "quick confirmation render")
if "confirm(" in source:
    raise RuntimeError("native confirm remains in CombatPage.tsx")
COMBAT.write_text(source, encoding="utf-8")

roles = ROLES.read_text(encoding="utf-8")
roles = replace_once(
    roles,
    '''async function csrfToken(request: APIRequestContext) {
  await request.get("/api/auth/session/");
  return (await request.storageState()).cookies.find((cookie) => cookie.name === "csrftoken")?.value || "";
}
''',
    '''async function csrfToken(request: APIRequestContext) {
  await request.get("/api/auth/session/");
  return (await request.storageState()).cookies.find((cookie) => cookie.name === "csrftoken")?.value || "";
}

async function postCombatAction(request: APIRequestContext, action: string, payload: Record<string, unknown>) {
  const token = await csrfToken(request);
  const response = await request.post("/api/combat/actions/", {
    headers: { "X-CSRFToken": token },
    data: { action, requestId: `combat-modal-${action}-${Date.now()}-${Math.random()}`, payload },
  });
  expect(response.ok()).toBeTruthy();
  return response;
}
''',
    "combat action helper",
)
workflow_test = r'''test("desktop master confirmations preserve planner and backup state", async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-combat-master", "Desktop master confirmation workflow only");
  const initial = await workspace(request);
  const map = initial.data.map;
  expect(map).toBeTruthy();
  const characterId = map?.activeCharacterId || map?.participants[0]?.character.id || 0;
  const snapshotLabel = `Conferma modale ${Date.now()}`;

  await postCombatAction(request, "maps.createSnapshot", { mapId: map?.id, label: snapshotLabel });
  await postCombatAction(request, "combat.planAction", {
    mapId: map?.id,
    characterId,
    actionType: "movement",
    name: "Movimento",
    description: "Azione preparata dal test modale",
    costs: { pf: 0, mana: 0, energia: 0, potere: 0, pa: 0, stanchezza: 0 },
    path: [],
  });

  await openCombat(page);
  await page.locator(".combat-map-toolbar").getByRole("button", { name: /Azioni rapide/ }).click();
  const planner = page.locator(".combat-quick-actions-modal");
  await expect(planner).toBeVisible();
  const pending = planner.locator(".planned-action-list article:not(.committed)");
  const initialCount = await pending.count();
  expect(initialCount).toBeGreaterThanOrEqual(1);

  await planner.getByRole("button", { name: "Aggiungi Movimento", exact: true }).click();
  let duplicate = page.getByRole("dialog", { name: "Aggiungere un duplicato?" });
  await expect(duplicate).toBeVisible();
  await expect(planner).toHaveAttribute("aria-hidden", "true");
  await duplicate.getByRole("button", { name: "Annulla", exact: true }).click();
  await expect(duplicate).toBeHidden();
  await expect(pending).toHaveCount(initialCount);

  await planner.getByRole("button", { name: "Aggiungi Movimento", exact: true }).click();
  duplicate = page.getByRole("dialog", { name: "Aggiungere un duplicato?" });
  await duplicate.getByRole("button", { name: "Aggiungi comunque", exact: true }).click();
  await expect(pending).toHaveCount(initialCount + 1, { timeout: 20_000 });

  await planner.getByRole("button", { name: "Svuota", exact: true }).click();
  let clear = page.getByRole("dialog", { name: "Svuotare la coda?" });
  await expect(clear).toBeVisible();
  await clear.getByRole("button", { name: "Annulla", exact: true }).click();
  await expect(pending).toHaveCount(initialCount + 1);

  await planner.getByRole("button", { name: "Svuota", exact: true }).click();
  clear = page.getByRole("dialog", { name: "Svuotare la coda?" });
  await clear.getByRole("button", { name: "Rimuovi azioni", exact: true }).click();
  await expect(pending).toHaveCount(0, { timeout: 20_000 });
  await planner.getByRole("button", { name: "Chiudi", exact: true }).last().click();

  await page.locator(".combat-map-manager-trigger").click();
  const manager = page.locator(".combat-map-manager-modal");
  await manager.getByRole("button", { name: "Backup e copie", exact: true }).click();
  const versions = page.getByRole("dialog", { name: "Backup e copie della mappa" });
  await expect(versions).toBeVisible();
  const snapshot = versions.locator(".combat-snapshot-list article").filter({ hasText: snapshotLabel });
  await expect(snapshot).toBeVisible();

  await snapshot.getByRole("button", { name: "Ripristina", exact: true }).click();
  let restore = page.getByRole("dialog", { name: "Ripristinare il backup?" });
  await expect(restore).toBeVisible();
  await restore.getByRole("button", { name: "Annulla", exact: true }).click();
  await expect(restore).toBeHidden();
  await expect(snapshot).toBeVisible();

  await snapshot.getByRole("button", { name: "Ripristina", exact: true }).click();
  restore = page.getByRole("dialog", { name: "Ripristinare il backup?" });
  const restoreResponse = page.waitForResponse((response) => {
    if (!response.url().includes("/api/combat/actions/")) return false;
    try { return response.request().postDataJSON()?.action === "maps.restoreSnapshot"; }
    catch { return false; }
  });
  await restore.getByRole("button", { name: "Ripristina backup", exact: true }).click();
  expect((await restoreResponse).ok()).toBeTruthy();
  await expect(restore).toBeHidden();
});

'''
roles = replace_once(
    roles,
    'test("phone player keeps controlled-character resources touch-visible", async ({ page }, testInfo) => {',
    workflow_test + 'test("phone player keeps controlled-character resources touch-visible", async ({ page }, testInfo) => {',
    "confirmation workflow test",
)
ROLES.write_text(roles, encoding="utf-8")

print("Combat confirmation modals and regressions applied successfully.")
