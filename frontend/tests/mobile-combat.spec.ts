import { expect, test, type Page } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isTabletProject = (name: string) => name.startsWith("tablet-");
const isDesktopProject = (name: string) => name === "authenticated" || name === "desktop-1920";

async function ensureCombatMap(page: Page) {
  await page.goto("/combat");
  await expect(page.locator(".combat-page")).toBeVisible({ timeout: 20_000 });
  if (await page.locator(".combat-stage-layout").count()) return;

  await page.evaluate(async () => {
    const workspaceResponse = await fetch("/api/combat/");
    const workspace = await workspaceResponse.json();
    const mapTypeId = workspace.data?.mapTypes?.[0]?.id;
    if (!mapTypeId) throw new Error("Nessun tipo mappa disponibile per il test.");
    const csrfToken = decodeURIComponent(document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || "");
    const requestId = `e2e-mobile-combat-${Date.now()}`;
    const response = await fetch("/api/combat/actions/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({
        action: "maps.save",
        requestId,
        payload: { name: "Mappa test mobile", mapTypeId, rows: 6, columns: 6 },
      }),
    });
    if (!response.ok) throw new Error(`Creazione mappa fallita: ${response.status}`);
  });
  await page.reload();
  await expect(page.locator(".combat-stage-layout")).toBeVisible({ timeout: 20_000 });
}

test("phone Combat is map-first and preserves mounted panel state", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Combat workspace contract");
  await ensureCombatMap(page);

  const navigation = page.getByRole("tablist", { name: "Pannelli del combattimento" });
  await expect(navigation).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-mobile-combat-panel", "map");
  await expect(page.locator(".combat-map-panel")).toBeVisible();
  await expect(page.locator(".combat-map-stage svg")).toHaveAttribute("data-mobile-combat-touch-ready", "true");

  const noteTrigger = page.locator(".mobile-context-note-trigger");
  if (await noteTrigger.count()) {
    const noteBox = await noteTrigger.boundingBox();
    const navigationBox = await navigation.boundingBox();
    expect(noteBox).toBeTruthy();
    expect(navigationBox).toBeTruthy();
    expect(noteBox!.y + noteBox!.height).toBeLessThanOrEqual(navigationBox!.y - 4);
  }

  const characterTab = navigation.getByRole("tab", { name: /Scheda/ });
  if (await characterTab.isEnabled()) {
    await characterTab.click();
    await expect(page.locator("html")).toHaveAttribute("data-mobile-combat-panel", "character");
    const character = page.locator(".combat-selected-character");
    await expect(character).toBeVisible();
    const resourceAction = character.locator(".combat-rail-resource-actions").first();
    if (await resourceAction.count()) {
      await expect(resourceAction).toBeVisible();
      const button = resourceAction.getByRole("button").first();
      expect((await button.boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }

  await navigation.getByRole("tab", { name: /Attivi/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-mobile-combat-panel", "roster");
  await expect(page.locator(".combat-active-strip")).toBeVisible();
  const rosterCard = page.locator(".combat-active-roster > div > button:first-child").first();
  if (await rosterCard.count()) {
    await rosterCard.click();
    const context = page.getByRole("dialog").last();
    await expect(context).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(context).toBeHidden();
  }

  await navigation.getByRole("tab", { name: /Mappa/ }).click();
  await expect(page.locator(".combat-map-panel")).toBeVisible();
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("phone Combat arbitrates real pinch without replacing one-finger token drag", async ({ context, page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Combat gesture contract");
  await ensureCombatMap(page);

  const map = page.locator(".combat-map-stage svg");
  await expect(map).toHaveAttribute("data-mobile-combat-touch-ready", "true");
  const box = await map.boundingBox();
  expect(box).toBeTruthy();
  const x = box!.x + box!.width * .5;
  const y = box!.y + box!.height * .5;
  const session = await context.newCDPSession(page);

  await session.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [
      { x: x - 26, y, radiusX: 2, radiusY: 2, force: 1, id: 1 },
      { x: x + 26, y, radiusX: 2, radiusY: 2, force: 1, id: 2 },
    ],
  });
  await session.send("Input.dispatchTouchEvent", {
    type: "touchMove",
    touchPoints: [
      { x: x - 44, y: y - 4, radiusX: 2, radiusY: 2, force: 1, id: 1 },
      { x: x + 44, y: y + 4, radiusX: 2, radiusY: 2, force: 1, id: 2 },
    ],
  });
  await expect(map).toHaveAttribute("data-mobile-combat-last-gesture", "pinch");
  await session.send("Input.dispatchTouchEvent", { type: "touchCancel", touchPoints: [] });

  const token = page.locator(".combat-token.can-move").first();
  if (!await token.count()) return;
  const tokenBox = await token.boundingBox();
  expect(tokenBox).toBeTruthy();
  const tokenX = tokenBox!.x + tokenBox!.width / 2;
  const tokenY = tokenBox!.y + tokenBox!.height / 2;
  await session.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [{ x: tokenX, y: tokenY, radiusX: 2, radiusY: 2, force: 1, id: 3 }],
  });
  await session.send("Input.dispatchTouchEvent", {
    type: "touchMove",
    touchPoints: [{ x: tokenX + 34, y: tokenY + 24, radiusX: 2, radiusY: 2, force: 1, id: 3 }],
  });
  await expect(page.locator(".combat-token-drag-preview")).toBeVisible();
  await session.send("Input.dispatchTouchEvent", { type: "touchCancel", touchPoints: [] });
});

test("phone Combat attack and hex inspectors use contained state-preserving panels", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Combat inspector contract");
  await ensureCombatMap(page);

  const navigation = page.getByRole("tablist", { name: "Pannelli del combattimento" });
  const attackTab = navigation.getByRole("tab", { name: /Attacco/ });
  await attackTab.click();
  await expect(page.locator("html")).toHaveAttribute("data-mobile-combat-panel", "attack");
  const attackDrawer = page.locator(".combat-attack-drawer");
  await expect(attackDrawer).toHaveClass(/open/);
  await expect(attackDrawer).toBeVisible();

  await navigation.getByRole("tab", { name: /Mappa/ }).click();
  await expect(attackDrawer).toBeHidden();
  await attackTab.click();
  await expect(attackDrawer).toBeVisible();

  // The original toolbar remains authoritative. Closing it while the preserved
  // draft is hidden must return the local workspace to Map rather than leave an
  // empty Attack panel.
  await navigation.getByRole("tab", { name: /Mappa/ }).click();
  await page.locator(".combat-attack-trigger").click();
  await expect(attackDrawer).not.toHaveClass(/open/);
  await expect(page.locator("html")).toHaveAttribute("data-mobile-combat-panel", "map");
  await expect(page.locator(".combat-map-panel")).toBeVisible();

  const hexLauncher = page.locator(".combat-hex-tool-launcher");
  await expect(hexLauncher).toBeVisible();
  await hexLauncher.click();
  const hexTool = page.locator(".combat-hex-tool-window");
  await expect(hexTool).toBeVisible();
  await expect(hexTool).toHaveCSS("position", "fixed");
  const viewport = page.viewportSize()!;
  const toolBox = await hexTool.boundingBox();
  expect(toolBox?.width || 0).toBeGreaterThanOrEqual(viewport.width - 2);
  await hexTool.getByRole("button", { name: "Chiudi strumenti esagono" }).click();
});

test("tablet Combat releases forced map width without phone navigation", async ({ page }, testInfo) => {
  test.skip(!isTabletProject(testInfo.project.name), "Tablet Combat containment contract");
  await ensureCombatMap(page);

  await expect(page.locator(".combat-mobile-navigation")).toHaveCount(0);
  await expect(page.locator(".combat-stage-layout")).toHaveCSS("min-width", "0px");
  await expect(page.locator(".combat-map-stage svg")).toHaveCSS("min-width", "0px");
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("desktop Combat retains the workstation layout and has no mobile runtime", async ({ page }, testInfo) => {
  test.skip(!isDesktopProject(testInfo.project.name), "Protected desktop Combat contract");
  await ensureCombatMap(page);

  await expect(page.locator(".combat-mobile-navigation")).toHaveCount(0);
  await expect(page.locator("html")).not.toHaveAttribute("data-mobile-combat-panel", /.+/);
  await expect(page.locator(".combat-stage-layout")).toHaveCSS("display", "flex");
  const selected = page.locator(".combat-selected-character");
  if (await selected.count()) await expect(selected).toBeVisible();
  await expect(page.locator(".combat-map-stage svg")).toHaveCSS("min-width", "620px");
});
