import { expect, test, type Page } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isTabletProject = (name: string) => name.startsWith("tablet-");
const isCompactProject = (name: string) => isPhoneProject(name) || isTabletProject(name);

async function openActiveCharacter(page: Page) {
  await page.goto("/");
  await expect(page.locator(".dashboard-page")).toBeVisible({ timeout: 20_000 });
  const characterLink = page.locator('a[href^="/character/"]').first();
  await expect(characterLink).toBeVisible();
  const href = await characterLink.getAttribute("href");
  expect(href).toBeTruthy();
  await page.goto(href!);
  await expect(page.locator(".character-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".fatal-error")).toHaveCount(0);
}

test("compact Character keeps identity and resource mutations touch-accessible", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Character contract");
  await openActiveCharacter(page);

  await expect(page.locator(".character-hud")).toBeVisible();
  await expect(page.locator(".character-identity h1")).toBeVisible();
  const resources = page.locator(".resource-card");
  expect(await resources.count()).toBeGreaterThan(0);

  if (isPhoneProject(testInfo.project.name)) {
    await expect(page.locator(".character-hud")).toHaveCSS("position", "relative");
    const actionButtons = page.locator(".resource-actions button");
    expect(await actionButtons.count()).toBeGreaterThan(0);
    for (let index = 0; index < await actionButtons.count(); index += 1) {
      const box = await actionButtons.nth(index).boundingBox();
      expect(box?.height || 0).toBeGreaterThanOrEqual(44);
    }
    const quickButtons = page.locator(".quick-stat-control > button");
    for (let index = 0; index < await quickButtons.count(); index += 1) {
      expect((await quickButtons.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Character preserves equipment, containers, tap actions, and slot picker", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Character contract");
  await openActiveCharacter(page);

  const equipmentTabs = page.getByRole("tablist", { name: "Vista equipaggiamento" });
  await expect(equipmentTabs).toBeVisible();
  await equipmentTabs.getByRole("tab", { name: "Griglia" }).click();
  const equipmentGrid = page.locator('.equipment-grid[data-equipment-view="grid"]');
  await expect(equipmentGrid).toBeVisible();
  expect(await equipmentGrid.locator(".character-slot").count()).toBeGreaterThan(0);

  const selectableSlot = equipmentGrid.locator(".character-slot:not(.locked):not(.system-managed)").first();
  await expect(selectableSlot).toBeVisible();
  await selectableSlot.click();
  await expect(selectableSlot).toHaveClass(/selected/);

  const chooseButton = selectableSlot.getByRole("button", { name: /Scegli un oggetto/ });
  await expect(chooseButton).toBeVisible();
  if (isPhoneProject(testInfo.project.name)) {
    expect((await chooseButton.boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
  }
  await chooseButton.click();

  const picker = page.getByRole("dialog", { name: /Scegli un oggetto per/ });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("textbox", { name: /Cerca un oggetto per/ })).toBeVisible();
  if (isPhoneProject(testInfo.project.name)) {
    const box = await picker.boundingBox();
    const viewport = page.viewportSize()!;
    expect(box?.width || 0).toBeGreaterThanOrEqual(viewport.width - 40);
    expect(box?.height || 0).toBeGreaterThanOrEqual(viewport.height - 40);
  }
  await picker.getByRole("button", { name: "Chiudi il menu" }).click();

  const containerTabs = page.locator(".container-tabs");
  await expect(containerTabs).toBeVisible();
  expect(await containerTabs.getByRole("button").count()).toBeGreaterThanOrEqual(4);
  await containerTabs.getByRole("button", { name: /Zaino/ }).click();
  await expect(page.locator(".container-grid")).toBeVisible();
  await expect(page.getByLabel("Ricerca Oggetto")).toBeVisible();

  if (isPhoneProject(testInfo.project.name)) {
    const slots = page.locator(".container-grid .character-slot:not(.locked)");
    if (await slots.count()) expect((await slots.first().boundingBox())?.height || 0).toBeGreaterThanOrEqual(96);
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Character opens effects and preserves both value pages", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Character contract");
  await openActiveCharacter(page);

  const rail = page.locator(".effect-rail");
  await expect(rail).toBeVisible();
  await rail.click();

  const effects = page.getByRole("region", { name: "Gestione effetti" });
  await expect(effects).toBeVisible();
  await expect(effects.locator(".effects-directory")).toBeVisible();
  await expect(effects.locator(".effect-detail-area")).toBeVisible();
  if (isPhoneProject(testInfo.project.name)) {
    const columns = await effects.locator(".effects-workspace-body").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
    expect(columns).toHaveLength(1);
  }
  await effects.getByRole("button", { name: "Chiudi effetti" }).click();
  await expect(rail).toBeVisible();

  const valueTabs = page.getByRole("tablist", { name: "Pagine dei valori" });
  await expect(valueTabs.getByRole("tab", { name: "Principali" })).toBeVisible();
  await valueTabs.getByRole("tab", { name: "Altri valori" }).click();
  await expect(page.locator("#character-values-advanced")).toBeVisible();
  await valueTabs.getByRole("tab", { name: "Principali" }).click();
  await expect(page.locator("#character-values-primary")).toBeVisible();

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("phone Character modals use mobile presentations without saving", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Character modal contract");
  await openActiveCharacter(page);

  await page.locator(".character-hud").getByRole("button", { name: "Modifica" }).click();
  const overview = page.getByRole("dialog", { name: "Modifica panoramica" });
  await expect(overview).toBeVisible();
  await expect(overview).toHaveAttribute("data-responsive-presentation", "sheet");
  await overview.getByRole("button", { name: "Chiudi" }).click();

  const createItem = page.getByRole("button", { name: "Crea oggetto" });
  if (await createItem.count()) {
    await createItem.click();
    const editor = page.getByRole("dialog", { name: "Crea oggetto" });
    await expect(editor).toBeVisible();
    await expect(editor).toHaveAttribute("data-responsive-presentation", "fullscreen");
    await expect(editor.getByRole("tablist", { name: "Sezioni dell'oggetto" })).toBeVisible();
    const box = await editor.boundingBox();
    expect(box?.height || 0).toBeGreaterThanOrEqual((page.viewportSize()?.height || 0) - 2);
    await editor.getByRole("button", { name: "Chiudi" }).click();
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("phone Character activates item drag from a real touch sequence", async ({ context, page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only touch drag contract");
  await openActiveCharacter(page);

  await page.getByRole("tablist", { name: "Vista equipaggiamento" }).getByRole("tab", { name: "Griglia" }).click();
  const draggable = page.locator('.equipment-grid .character-slot:has(.slot-item):not(.locked):not(.system-managed)').first();
  if (!await draggable.count()) test.skip(true, "Seeded character has no draggable equipped item");
  await expect(draggable).toBeVisible();
  await expect(draggable).toHaveCSS("touch-action", "none");

  const box = await draggable.boundingBox();
  expect(box).toBeTruthy();
  const x = box!.x + Math.min(24, box!.width / 2);
  const y = box!.y + Math.min(24, box!.height / 2);
  const session = await context.newCDPSession(page);
  await session.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [{ x, y, radiusX: 2, radiusY: 2, force: 1, id: 1 }],
  });
  await session.send("Input.dispatchTouchEvent", {
    type: "touchMove",
    touchPoints: [{ x: x + 28, y: y + 18, radiusX: 2, radiusY: 2, force: 1, id: 1 }],
  });

  await expect(page.locator(".drag-cursor")).toBeVisible();
  await expect(page.locator(".drag-overlay")).toBeVisible();

  await session.send("Input.dispatchTouchEvent", { type: "touchCancel", touchPoints: [] });
  await expect(page.locator(".drag-cursor")).toHaveCount(0);
});

test("desktop Character retains the sticky HUD and multi-column workspace", async ({ page }, testInfo) => {
  test.skip(isCompactProject(testInfo.project.name), "Desktop preservation contract");
  await openActiveCharacter(page);

  await expect(page.locator(".character-hud")).toHaveCSS("position", "sticky");
  const columns = await page.locator(".items-columns").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  expect(columns.length).toBeGreaterThanOrEqual(2);
  await expect(page.locator(".effect-rail")).toHaveCSS("flex-direction", "column");
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});
