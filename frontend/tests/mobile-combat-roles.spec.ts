import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const roleProject = (testInfo: TestInfo) => testInfo.project.name.includes("combat-master") || testInfo.project.name.includes("combat-player");
const isMasterProject = (testInfo: TestInfo) => testInfo.project.name.includes("combat-master");
const isPhoneProject = (testInfo: TestInfo) => testInfo.project.name.startsWith("phone-");

type CombatWorkspaceEnvelope = {
  data: {
    permissions: {
      canManageMaps: boolean;
      canImportCharacters: boolean;
      canControlCharacters: boolean;
      canApplyEnemyEffects: boolean;
    };
    viewerCharacterId: number | null;
    characterCatalog: unknown[];
    templates: unknown[];
    unitCatalog: unknown[];
    effectCatalog: unknown[];
    map: null | {
      id: number;
      mapTypeId: number;
      activeCharacterId: number | null;
      participants: Array<{ id: number; character: { id: number; name: string }; anchor: { q: number; r: number } }>;
      snapshots: unknown[];
      revision?: number;
    };
  };
};

async function workspace(request: APIRequestContext) {
  const response = await request.get("/api/combat/");
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as CombatWorkspaceEnvelope;
}

async function csrfToken(request: APIRequestContext) {
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

async function openCombat(page: Page) {
  await page.goto("/combat");
  await expect(page.locator(".combat-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".combat-stage-layout")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".fatal-error")).toHaveCount(0);
}

async function closeTopModal(page: Page) {
  const modal = page.locator(".modal-backdrop").last();
  await expect(modal).toBeVisible();
  const close = modal.getByRole("button", { name: "Chiudi", exact: true }).first();
  if (await close.count()) await close.click();
  else await page.keyboard.press("Escape");
  await expect(modal).toBeHidden();
}

test("Combat API exposes the real master/player permission boundary", async ({ request }, testInfo) => {
  test.skip(!roleProject(testInfo), "Dedicated Combat role projects only");
  const result = await workspace(request);
  const data = result.data;
  const master = isMasterProject(testInfo);

  expect(data.map).toBeTruthy();
  expect(data.viewerCharacterId).toBeTruthy();
  expect(data.permissions).toEqual({
    canManageMaps: master,
    canImportCharacters: master,
    canControlCharacters: master,
    canApplyEnemyEffects: master,
  });

  if (master) {
    expect(data.characterCatalog.length).toBeGreaterThanOrEqual(2);
    expect(data.map?.revision).toBeTruthy();
    expect(data.map?.participants.length || 0).toBeGreaterThanOrEqual(2);
  } else {
    expect(data.characterCatalog).toEqual([]);
    expect(data.templates).toEqual([]);
    expect(data.unitCatalog).toEqual([]);
    expect(data.effectCatalog).toEqual([]);
    expect(data.map?.snapshots).toEqual([]);
    expect(data.map).not.toHaveProperty("revision");
    expect(data.map?.activeCharacterId).toBe(data.viewerCharacterId);
    expect(data.map?.participants.some((entry) => entry.character.id === data.viewerCharacterId)).toBe(true);

    const token = await csrfToken(request);
    const denied = await request.post("/api/combat/actions/", {
      headers: { "X-CSRFToken": token },
      data: {
        action: "maps.save",
        requestId: `combat-player-denied-${Date.now()}`,
        payload: {
          name: "Tentativo non autorizzato",
          mapTypeId: data.map?.mapTypeId,
          rows: 8,
          columns: 8,
        },
      },
    });
    expect(denied.status()).toBe(403);
    const deniedBody = await denied.json();
    expect(deniedBody.ok).toBe(false);
  }
});

test("Combat UI exposes role-appropriate map, token, and manager controls", async ({ page }, testInfo) => {
  test.skip(!roleProject(testInfo), "Dedicated Combat role projects only");
  await openCombat(page);
  const master = isMasterProject(testInfo);

  if (isPhoneProject(testInfo)) {
    await expect(page.getByRole("tablist", { name: "Pannelli del combattimento" })).toBeVisible();
    await expect(page.locator(".combat-map-stage svg")).toHaveAttribute("data-mobile-combat-touch-ready", "true");
  } else {
    await expect(page.locator(".combat-mobile-navigation")).toHaveCount(0);
    await expect(page.locator(".combat-map-stage svg")).toHaveCSS("min-width", "620px");
  }

  const movableTokens = page.locator(".combat-token.can-move");
  if (master) expect(await movableTokens.count()).toBeGreaterThanOrEqual(2);
  else expect(await movableTokens.count()).toBe(1);

  await expect(page.locator(".combat-new-map-trigger")).toHaveCount(master ? 1 : 0);
  await expect(page.locator(".combat-map-toolbar").getByRole("button", { name: "Personaggi", exact: true })).toHaveCount(master ? 1 : 0);

  await page.locator(".combat-map-manager-trigger").click();
  const manager = page.locator(".combat-map-manager-modal");
  await expect(manager).toBeVisible();
  const editEntries = manager.getByRole("button", { name: /Calibra e modifica|Modifica mappa attiva/ });
  if (master) expect(await editEntries.count()).toBeGreaterThanOrEqual(1);
  else await expect(editEntries).toHaveCount(0);
  await expect(manager.getByRole("button", { name: "Backup e copie", exact: true })).toHaveCount(master ? 1 : 0);
  if (isPhoneProject(testInfo)) await expect(manager).toHaveAttribute("data-responsive-presentation", "fullscreen");
  await closeTopModal(page);

  if (master) {
    await page.locator(".combat-new-map-trigger").click();
    const editor = page.getByRole("dialog", { name: "Nuova mappa di combattimento" });
    await expect(editor).toBeVisible();
    if (isPhoneProject(testInfo)) await expect(editor).toHaveAttribute("data-responsive-presentation", "fullscreen");
    await closeTopModal(page);

    await page.locator(".combat-map-toolbar").getByRole("button", { name: "Personaggi", exact: true }).click();
    const characters = page.locator(".combat-character-manager-modal");
    await expect(characters).toBeVisible();
    if (isPhoneProject(testInfo)) await expect(characters).toHaveAttribute("data-responsive-presentation", "fullscreen");
    await closeTopModal(page);
  }

  const planner = page.locator(".combat-map-toolbar").getByRole("button", { name: /Azioni rapide/ });
  await planner.click();
  const plannerModal = page.locator(".combat-quick-actions-modal");
  await expect(plannerModal).toBeVisible();
  if (isPhoneProject(testInfo)) await expect(plannerModal).toHaveAttribute("data-responsive-presentation", "fullscreen");
  await closeTopModal(page);

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("nested Combat modals keep only the top dialog interactive", async ({ page }, testInfo) => {
  test.skip(!isMasterProject(testInfo), "Master Combat projects only");
  await openCombat(page);

  await page.locator(".combat-map-toolbar").getByRole("button", { name: "Personaggi", exact: true }).click();
  const manager = page.locator(".combat-character-manager-modal");
  await expect(manager).toBeVisible();

  if (!isPhoneProject(testInfo)) {
    await page.locator(".modal-backdrop").last().click({ position: { x: 2, y: 2 } });
    await expect(manager).toBeVisible();
  }

  const importCopy = manager.getByRole("button", { name: "Importa copia", exact: true }).first();
  await expect(importCopy).toBeVisible();
  await importCopy.click();

  const confirmation = page.getByRole("dialog", { name: "Importare una copia?" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toHaveAttribute("data-modal-top", "");
  await expect(manager).toHaveAttribute("aria-hidden", "true");
  await expect(confirmation.getByRole("button", { name: "Chiudi", exact: true })).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await expect(confirmation.getByRole("button", { name: "Sì, crea una copia", exact: true })).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(confirmation).toBeHidden();
  await expect(manager).toBeVisible();
  await expect(manager).toHaveAttribute("data-modal-top", "");
  await expect(importCopy).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(manager).toBeHidden();
});

test("desktop master confirmations preserve planner and backup state", async ({ page, request }, testInfo) => {
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

test("phone player keeps controlled-character resources touch-visible", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone-combat-player", "Phone player project only");
  await openCombat(page);

  const navigation = page.getByRole("tablist", { name: "Pannelli del combattimento" });
  await navigation.getByRole("tab", { name: /Scheda/ }).click();
  const character = page.locator(".combat-selected-character");
  await expect(character).toBeVisible();
  const resources = character.locator(".combat-rail-resource-actions");
  expect(await resources.count()).toBeGreaterThan(0);
  for (let index = 0; index < await resources.count(); index += 1) {
    await expect(resources.nth(index)).toBeVisible();
    const buttons = resources.nth(index).getByRole("button");
    for (let buttonIndex = 0; buttonIndex < await buttons.count(); buttonIndex += 1) {
      expect((await buttons.nth(buttonIndex).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }
});
