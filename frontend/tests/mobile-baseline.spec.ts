import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isTabletProject = (name: string) => name.startsWith("tablet-");
const isCompactProject = (name: string) => isPhoneProject(name) || isTabletProject(name);

test("captures the authenticated shell baseline for the configured viewport", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(page.locator(".fatal-error")).toHaveCount(0);

  if (isPhoneProject(testInfo.project.name)) {
    await expect(page.locator(".mobile-app-bar")).toBeVisible();
    await expect(page.locator(".mobile-bottom-navigation")).toBeVisible();
    await expect(page.locator(".side-nav")).toBeHidden();
  } else {
    await expect(page.locator(".side-nav")).toBeVisible();
    await expect(page.locator(".mobile-shell-chrome")).toHaveCount(0);
  }

  const diagnostics = {
    project: testInfo.project.name,
    viewport: page.viewportSize(),
    touchPoints: await page.evaluate(() => navigator.maxTouchPoints),
    coarsePointer: await page.evaluate(() => window.matchMedia("(pointer: coarse)").matches),
    noHover: await page.evaluate(() => window.matchMedia("(hover: none)").matches),
    overflow: await measureDocumentOverflow(page),
  };

  await testInfo.attach("layout-diagnostics.json", {
    body: JSON.stringify(diagnostics, null, 2),
    contentType: "application/json",
  });
});

test("phone login remains usable without viewport overflow or input zoom", async ({ context, page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only login contract");
  await context.clearCookies();
  await page.goto("/");

  await expect(page).toHaveURL(/\/login\/\?next=\//);
  const card = page.locator(".auth-card");
  await expect(card).toBeVisible();
  await expect(page.getByLabel("Nome utente")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();

  const metrics = await page.evaluate(() => {
    const cardElement = document.querySelector<HTMLElement>(".auth-card")!;
    const username = document.querySelector<HTMLInputElement>("input[autocomplete='username']")!;
    const submit = document.querySelector<HTMLButtonElement>(".auth-card form button")!;
    const rect = cardElement.getBoundingClientRect();
    return {
      cardLeft: rect.left,
      cardRight: rect.right,
      viewportWidth: document.documentElement.clientWidth,
      inputFontSize: Number.parseFloat(getComputedStyle(username).fontSize),
      submitHeight: submit.getBoundingClientRect().height,
    };
  });

  expect(metrics.cardLeft).toBeGreaterThanOrEqual(0);
  expect(metrics.cardRight).toBeLessThanOrEqual(metrics.viewportWidth + 1);
  expect(metrics.inputFontSize).toBeGreaterThanOrEqual(16);
  expect(metrics.submitHeight).toBeGreaterThanOrEqual(44);
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact dashboard uses a single readable selection column", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet dashboard contract");
  await page.goto("/");

  const selection = page.locator(".dashboard-character-selection");
  await expect(selection).toBeVisible();
  const columns = await selection.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  expect(columns).toHaveLength(1);
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);

  if (isPhoneProject(testInfo.project.name)) {
    const shortcuts = page.locator(".dashboard-shortcuts .button");
    const shortcutCount = await shortcuts.count();
    for (let index = 0; index < shortcutCount; index += 1) {
      expect((await shortcuts.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }
});

test("phone shell exposes secondary destinations and quick tools", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only shell contract");
  await page.goto("/");

  const bottomNavigation = page.locator(".mobile-bottom-navigation");
  await expect(bottomNavigation.getByRole("link", { name: /Home/ })).toBeVisible();
  await expect(bottomNavigation.getByRole("link", { name: /PG/ })).toBeVisible();
  await expect(bottomNavigation.getByRole("link", { name: /Abilità/ })).toBeVisible();
  await expect(bottomNavigation.getByRole("link", { name: /Combattimento/ })).toBeVisible();

  await bottomNavigation.getByRole("button", { name: /Altro/ }).click();
  const navigationDialog = page.getByRole("dialog", { name: "Navigazione" });
  await expect(navigationDialog).toBeVisible();
  await expect(navigationDialog.getByRole("link", { name: /Impostazioni/ })).toBeVisible();
  await expect(navigationDialog.getByText("Gestione da schermo più grande")).toBeVisible();
  await navigationDialog.getByRole("button", { name: "Chiudi" }).click();

  await page.locator(".mobile-app-tools").click();
  const toolsDialog = page.getByRole("dialog", { name: "Strumenti rapidi" });
  await expect(toolsDialog.getByRole("button", { name: /Diario/ })).toBeVisible();
  await expect(toolsDialog.getByRole("button", { name: /Dadi/ })).toBeVisible();
  await expect(toolsDialog.getByRole("button", { name: /Audio/ })).toBeVisible();
});

test("phone context notes use a visible trigger and autosaving editor sheet", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only context notes contract");
  await page.goto("/competencies");

  const trigger = page.getByRole("button", { name: "Note della pagina: Competenze" });
  await expect(trigger).toBeVisible();
  const triggerBox = await trigger.boundingBox();
  const navigationBox = await page.locator(".mobile-bottom-navigation").boundingBox();
  expect(triggerBox?.y || 0).toBeLessThan(navigationBox?.y || Number.POSITIVE_INFINITY);

  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Note Competenze" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Note Competenze")).toBeVisible();
  await expect(dialog.getByText(/Salvataggio automatico|Salvato|Da salvare/)).toBeVisible();
  await dialog.getByRole("button", { name: "Chiudi" }).click();
  await expect(dialog).toHaveCount(0);
});

test("phone Lore exposes readable tabs, cards, details, and timeline", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Lore contract");
  await page.goto("/lore");

  const tabs = page.getByRole("tablist", { name: "Sezioni del lore" });
  await expect(tabs.getByRole("tab")).toHaveCount(3);
  await expect(page.locator(".lore-faction-grid")).toBeVisible();
  const factionColumns = await page.locator(".lore-faction-grid").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  expect(factionColumns).toHaveLength(1);
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);

  await tabs.getByRole("tab", { name: "Personaggi" }).click();
  const firstNpc = page.locator(".lore-npc-tile").first();
  await expect(firstNpc).toBeVisible();
  await firstNpc.click();
  const npcDialog = page.getByRole("dialog").filter({ has: page.locator(".lore-npc-detail") });
  await expect(npcDialog).toBeVisible();
  const dialogBox = await npcDialog.boundingBox();
  expect(dialogBox?.height || 0).toBeGreaterThanOrEqual((page.viewportSize()?.height || 0) - 2);
  await npcDialog.getByRole("button", { name: "Chiudi" }).click();

  await tabs.getByRole("tab", { name: "Timeline" }).click();
  const timeline = page.getByRole("tabpanel", { name: "Timeline" });
  await expect(timeline.getByRole("searchbox", { name: "Cerca nella cronologia" })).toBeVisible();
  await expect(timeline.locator(".lore-history-events button").first()).toBeVisible();
  await expect(timeline.locator(".lore-timeline-inspector")).toBeVisible();
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("phone management URLs preserve the address and show the intentional limitation", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only management guard");
  await page.goto("/tools");

  await expect(page).toHaveURL(/\/tools$/);
  const limitation = page.locator(".mobile-unsupported-management");
  await expect(limitation).toBeVisible();
  await expect(limitation.getByRole("heading", { name: "Gestione richiede un tablet o un computer" })).toBeVisible();
  await expect(limitation.getByRole("button", { name: "Indietro" })).toBeVisible();
  await expect(limitation.getByRole("link", { name: "Torna alla Home" })).toBeVisible();
  await expect(page.locator(".workspace-content")).toBeHidden();
});
