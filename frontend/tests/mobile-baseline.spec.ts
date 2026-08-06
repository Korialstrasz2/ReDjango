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

test("phone Lore keeps empty and populated route states readable", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Lore contract");
  await page.goto("/lore");

  const tabs = page.getByRole("tablist", { name: "Sezioni del lore" });
  await expect(tabs.getByRole("tab")).toHaveCount(3);
  const factionSection = page.getByRole("tabpanel", { name: "Fazioni" });
  await expect(factionSection).toBeVisible();
  const factionCards = factionSection.locator(".lore-faction-card");
  if (await factionCards.count()) {
    const factionColumns = await factionSection.locator(".lore-faction-grid").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
    expect(factionColumns).toHaveLength(1);
    expect((await factionCards.first().boundingBox())?.width || 0).toBeLessThanOrEqual((page.viewportSize()?.width || 0) + 1);
  } else {
    await expect(factionSection.locator(".lore-empty")).toBeVisible();
  }
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);

  await tabs.getByRole("tab", { name: "Personaggi" }).click();
  const characterSection = page.getByRole("tabpanel", { name: "Personaggi" });
  const npcTiles = characterSection.locator(".lore-npc-tile");
  if (await npcTiles.count()) {
    await npcTiles.first().click();
    const npcDialog = page.getByRole("dialog").filter({ has: page.locator(".lore-npc-detail") });
    await expect(npcDialog).toBeVisible();
    const dialogBox = await npcDialog.boundingBox();
    expect(dialogBox?.height || 0).toBeGreaterThanOrEqual((page.viewportSize()?.height || 0) - 2);
    await npcDialog.getByRole("button", { name: "Chiudi" }).click();
  } else {
    await expect(characterSection.locator(".lore-empty")).toBeVisible();
  }

  await tabs.getByRole("tab", { name: "Timeline" }).click();
  const timeline = page.getByRole("tabpanel", { name: "Timeline" });
  await expect(timeline.getByRole("searchbox", { name: "Cerca nella cronologia" })).toBeVisible();
  const timelineEvents = timeline.locator(".lore-history-events button");
  if (await timelineEvents.count()) {
    await expect(timelineEvents.first()).toBeVisible();
    await expect(timeline.locator(".lore-timeline-inspector")).toBeVisible();
  } else {
    await expect(timeline.locator(".lore-empty")).toBeVisible();
  }
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Guides keep the index and reader usable", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Guides contract");
  await page.goto("/guides");

  const layout = page.locator(".guide-layout");
  const index = page.locator(".guide-index");
  const reader = page.locator(".guide-reader");
  await expect(layout).toBeVisible();
  await expect(index.locator("button").first()).toBeVisible();
  await expect(reader).toBeVisible();

  const columns = await layout.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  if ((page.viewportSize()?.width || 0) <= 900) expect(columns).toHaveLength(1);
  else expect(columns.length).toBeGreaterThanOrEqual(2);
  expect((await index.locator("button").first().boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);

  const variableReference = reader.locator(".variable-reference");
  if (await variableReference.count()) {
    const variableColumns = await variableReference.first().evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
    if (isPhoneProject(testInfo.project.name)) expect(variableColumns).toHaveLength(1);
  }
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Media prioritizes browsing and keeps actions touchable", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Media contract");
  await page.goto("/media");

  const layout = page.locator(".media-library-layout");
  const browser = page.locator(".media-browser");
  const upload = page.locator(".media-upload-panel");
  await expect(layout).toBeVisible();
  await expect(browser).toBeVisible();
  await expect(upload).toBeVisible();

  const columns = await layout.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  if ((page.viewportSize()?.width || 0) <= 900) {
    expect(columns).toHaveLength(1);
    const browserBox = await browser.boundingBox();
    const uploadBox = await upload.boundingBox();
    expect(browserBox?.y || 0).toBeLessThan(uploadBox?.y || Number.POSITIVE_INFINITY);
  }

  if (isPhoneProject(testInfo.project.name)) {
    const search = page.locator(".media-browser-toolbar input[type='search']");
    await expect(search).toBeVisible();
    expect(await search.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(16);
  }

  const cards = page.locator(".media-asset-card");
  if (await cards.count()) {
    await cards.first().locator(".media-asset-open").click();
    const dialog = page.locator(".media-preview-modal");
    await expect(dialog).toBeVisible();
    if (isPhoneProject(testInfo.project.name)) await expect(dialog).toHaveAttribute("data-responsive-presentation", "fullscreen");
    await dialog.getByRole("button", { name: "Chiudi" }).click();
  } else {
    await expect(page.getByText("Nessuna immagine trovata")).toBeVisible();
  }
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Settings expose scrollable tabs and full-width controls", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Settings contract");
  await page.goto("/settings");

  const tabs = page.getByRole("tablist", { name: "Sezioni delle impostazioni" });
  await expect(tabs).toBeVisible();
  await expect(tabs.getByRole("tab", { name: "Profilo" })).toBeVisible();
  await expect(page.locator(".player-settings-panel")).toBeVisible();

  const appearanceTab = tabs.getByRole("tab", { name: "Aspetto" });
  if (await appearanceTab.count()) {
    await appearanceTab.click();
    const settingRow = page.locator(".setting-row").first();
    await expect(settingRow).toBeVisible();
    if (isPhoneProject(testInfo.project.name)) {
      const columns = await settingRow.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
      expect(columns).toHaveLength(1);
      const control = settingRow.locator("input:not([type='checkbox']), select").first();
      if (await control.count()) expect(await control.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(16);
    }
  }
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Market collapses navigation, catalogue, and purchase flow safely", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Market contract");
  await page.goto("/market");

  const layout = page.locator(".market-layout");
  await expect(layout).toBeVisible();
  await expect(page.locator(".market-world-nav")).toBeVisible();
  await expect(page.locator(".market-catalog")).toBeVisible();
  await expect(page.locator(".market-purchase-sidebar")).toBeVisible();

  const columns = await layout.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  if ((page.viewportSize()?.width || 0) <= 900) expect(columns).toHaveLength(1);
  expect((await page.locator(".market-nav-heading").first().boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);

  const stockCards = page.locator(".market-item-card");
  if (await stockCards.count()) {
    await stockCards.first().click();
    const itemDialog = page.locator(".market-item-modal");
    await expect(itemDialog).toBeVisible();
    if (isPhoneProject(testInfo.project.name)) await expect(itemDialog).toHaveAttribute("data-responsive-presentation", "fullscreen");
    await itemDialog.getByRole("button", { name: "Chiudi" }).click();
  } else {
    await expect(page.locator(".market-empty").first()).toBeVisible();
  }
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
  await expect(page.locator(".workspace-content")).toBeVisible();
  await expect(page.locator(".management-page")).toHaveCount(0);
  await expect(page.locator(".management-launcher")).toHaveCount(0);
});