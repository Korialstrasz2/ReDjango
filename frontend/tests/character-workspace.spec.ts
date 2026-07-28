import { expect, test } from "@playwright/test";

test("la scheda personaggio completa funziona dal bundle di produzione", async ({ page, request }) => {
  const charactersResponse = await request.get("/api/personaggi/");
  expect(charactersResponse.ok()).toBeTruthy();
  const characters = await charactersResponse.json();
  const characterId = characters.data.giocatore.activePersonaggioId;

  await page.goto(`/character/${characterId}`);
  await expect(page.locator(".side-nav .campaign-selector")).toHaveCount(0);
  const sidebarPortrait = page.locator(".brand-block > img");
  await expect(sidebarPortrait).toBeVisible();
  const sidebarPortraitBox = await sidebarPortrait.boundingBox();
  expect(sidebarPortraitBox?.width).toBeGreaterThan(100);
  expect(sidebarPortraitBox?.height).toBeGreaterThan(100);
  await expect(page.locator(".character-hud h1")).toHaveText(characters.data.activePersonaggio.name);
  await expect(page.locator(".resource-card")).toHaveCount(4);
  await expect(page.locator(".quick-stat-control")).toHaveCount(2);
  await expect(page.locator('.quick-stat-control[data-stat-key="stanchezza"]')).toContainText("Stanchezza");
  await expect(page.locator('.quick-stat-control[data-stat-key="modificatore_generale"]')).toContainText("Modificatore generale");
  await expect(page.getByRole("heading", { name: "Equipaggiamento e inventario" })).toBeVisible();
  await expect(page.locator('.character-figure .character-slot[data-slot-id^="equipment:"]')).toHaveCount(35);
  await expect(page.locator(".figure-slot-rail")).toHaveCount(2);
  await expect(page.locator('[data-figure-region="utility"]')).toHaveCount(2);
  await expect(page.locator(".figure-slot .slot-move-button, .figure-slot .slot-item small, .figure-slot .slot-item > span")).toHaveCount(0);
  await expect(page.locator('[data-equipment-view="figure"]')).toBeVisible();
  const figureWidth = await page.locator(".figure-equipment").evaluate((element) => element.getBoundingClientRect().width);
  const equipmentWidth = await page.locator(".equipment-column").evaluate((element) => element.getBoundingClientRect().width);
  expect(figureWidth / equipmentWidth).toBeCloseTo(0.8, 1);
  await expect(page.locator(".character-figure-art img")).toHaveCSS("object-fit", "contain");
  await expect(page.getByText("Zaino", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("Faretra", { exact: false }).first()).toBeVisible();
  await expect(page.locator(".container-tabs button").first()).toContainText(/\(\d+ magici\)/);
  const initialSheet = await (await request.get(`/api/v1/characters/${characterId}/sheet`)).json();
  const magicalSlotCount = initialSheet.data.character.inventory.magicalSlots;
  const activeBackpackSlots = page.locator('.container-grid .character-slot:not(.locked)');
  await expect(page.locator('.container-grid .character-slot:not(.locked)[data-magical="true"]')).toHaveCount(magicalSlotCount);
  for (let index = 0; index < magicalSlotCount; index += 1) {
    await expect(activeBackpackSlots.nth(index)).toHaveAttribute("data-magical", "true");
  }
  const magicalColors = await activeBackpackSlots.first().evaluate((slot) => {
    const probe = document.createElement("span");
    probe.style.color = "var(--resource-mana)";
    document.body.appendChild(probe);
    const mana = getComputedStyle(probe).color;
    probe.remove();
    return { border: getComputedStyle(slot).borderTopColor, mana };
  });
  expect(magicalColors.border).toBe(magicalColors.mana);
  await expect(page.getByText("Il loro contenuto non pesa.", { exact: true })).toHaveCount(0);
  const itemsPosition = await page.locator(".items-workspace").evaluate((element) => element.getBoundingClientRect().top);
  const overviewPosition = await page.locator(".overview-effects-grid").evaluate((element) => element.getBoundingClientRect().top);
  expect(overviewPosition).toBeGreaterThan(itemsPosition);

  const firstFigureSlot = page.locator(".figure-slot-rail-left .figure-slot").first();
  const secondFigureSlot = page.locator(".figure-slot-rail-left .figure-slot").nth(1);
  const figureBox = (await page.locator(".character-figure").boundingBox())!;
  const compactBox = (await firstFigureSlot.boundingBox())!;
  expect(compactBox.width).toBeLessThanOrEqual(figureBox.width * .27);
  await expect(firstFigureSlot).toHaveCSS("opacity", "0.7");
  const compactHeight = (await firstFigureSlot.boundingBox())!.height;
  await firstFigureSlot.hover();
  await expect(firstFigureSlot).toHaveCSS("opacity", "1");
  await expect.poll(async () => (await firstFigureSlot.boundingBox())!.height).toBeGreaterThan(compactHeight + 10);
  await expect.poll(async () => (await firstFigureSlot.boundingBox())!.width).toBeGreaterThan(compactBox.width * 1.45);
  const expandedBox = (await firstFigureSlot.boundingBox())!;
  const followingBox = (await secondFigureSlot.boundingBox())!;
  expect(followingBox.y).toBeGreaterThanOrEqual(expandedBox.y + expandedBox.height - 1);
  await page.mouse.move(1, 1);
  await expect.poll(async () => (await firstFigureSlot.boundingBox())!.height).toBeLessThanOrEqual(compactHeight + 1);
  await expect(firstFigureSlot).toHaveCSS("opacity", "0.7");

  const utilitySlotBox = (await page.locator('[data-figure-slot="sacco_1"]').boundingBox())!;
  expect(utilitySlotBox.y).toBeGreaterThan(figureBox.y + figureBox.height * .65);

  const weightSummary = page.locator(".weight-summary");
  await weightSummary.hover();
  await expect(page.locator(".weight-tooltip")).toBeVisible();
  await expect(page.locator(".weight-tooltip")).toContainText(String((await (await request.get(`/api/v1/characters/${characterId}/sheet`)).json()).data.character.encumbrance.total));
  await page.getByRole("tab", { name: "Altri valori" }).click();
  await expect(page.locator('[data-value-group="load_capacity"]')).toBeVisible();
  await expect(page.locator('[data-stat-key="malus_carico"]')).toBeVisible();
  await expect(page.locator('[data-stat-key="sifone_di_mana"]')).toBeVisible();
  await page.getByRole("tab", { name: "Principali" }).click();

  const firstCharacteristic = page.locator('[data-stat-key="forza"]');
  await expect(firstCharacteristic.locator(":scope > strong")).toHaveText(/^-?\d+(?:\.\d+)? \(-?\d+\)$/);
  await firstCharacteristic.hover();
  await expect(firstCharacteristic.locator(".calculation-tooltip")).toBeVisible();
  await expect(firstCharacteristic.locator(".calculation-tooltip")).toContainText("Base");
  await expect(firstCharacteristic.locator(".calculation-tooltip")).toContainText("Oggetti");
  await expect(firstCharacteristic.locator(".calculation-tooltip")).toContainText("Effetti");

  const delayedResourceTooltip = page.locator('.resource-card[data-resource="pf"] > .calculation-tooltip');
  await page.locator('.resource-card[data-resource="pf"]').hover();
  await page.waitForTimeout(1000);
  await expect(delayedResourceTooltip).toBeHidden();
  await page.waitForTimeout(2200);
  await expect(delayedResourceTooltip).toBeVisible();

  const occupiedFigureSlot = page.locator(".figure-slot:has(.slot-item)").first();
  await occupiedFigureSlot.click();
  await expect(page.locator(".item-detail")).toBeVisible();

  const occupiedContainerSlot = page.locator(".container-grid .character-slot:has(.slot-item)").first();
  await occupiedContainerSlot.hover();
  await occupiedContainerSlot.getByRole("button", { name: "Sposta" }).click();
  const compatibleFigureSlots = page.locator(".character-figure .figure-slot.valid");
  expect(await compatibleFigureSlots.count()).toBeGreaterThanOrEqual(4);
  await expect.poll(async () => (await compatibleFigureSlots.first().boundingBox())!.height).toBeGreaterThan(compactHeight + 10);
  await page.locator(".interaction-banner").getByRole("button", { name: "Annulla" }).click();

  const firstResource = page.locator(".resource-card").first();
  const progress = firstResource.getByRole("progressbar");
  const label = await progress.getAttribute("aria-label") || "Punti ferita";
  const originalResource = Number(await progress.getAttribute("aria-valuenow"));
  await firstResource.hover();
  await firstResource.getByRole("button", { name: `Riduci ${label} di 1`, exact: true }).click();
  await expect(progress).toHaveAttribute("aria-valuenow", String(originalResource - 1));
  const unsavedSheet = await (await request.get(`/api/v1/characters/${characterId}/sheet`)).json();
  const resourceKey = await firstResource.getAttribute("data-resource");
  const unsavedResource = unsavedSheet.data.character.resources.find((resource: { key: string }) => resource.key === resourceKey);
  expect(unsavedResource.current).toBe(originalResource);
  await expect(firstResource.getByRole("button", { name: `Porta ${label} al massimo`, exact: true })).toBeVisible();
  await firstResource.getByRole("button", { name: `Salva ${label}`, exact: true }).click();
  await expect(page.locator(".toast")).toContainText(`Fatto! ${label} salvati`);
  await firstResource.hover();
  await firstResource.getByRole("button", { name: `Aumenta ${label} di 1`, exact: true }).click();
  await firstResource.getByRole("button", { name: `Salva ${label}`, exact: true }).click();
  await expect(progress).toHaveAttribute("aria-valuenow", String(originalResource));

  const fatigue = page.locator('.quick-stat-control[data-stat-key="stanchezza"]');
  const originalFatigue = Number(await fatigue.locator(":scope > strong").textContent());
  await fatigue.hover();
  await fatigue.getByRole("button", { name: "Aumenta Stanchezza di 1" }).click();
  await expect(fatigue.locator(":scope > strong")).toHaveText(String(originalFatigue + 1));
  await fatigue.hover();
  await fatigue.getByRole("button", { name: "Riduci Stanchezza di 1" }).click();
  await expect(fatigue.locator(":scope > strong")).toHaveText(String(originalFatigue));

  const hudButtons = await page.locator(".hud-actions .button").allTextContents();
  expect(hudButtons).toEqual(["Riposa", "Modifica"]);

  const portrait = page.locator(".character-figure img");
  await portrait.scrollIntoViewIfNeeded();
  await expect(portrait).toBeVisible();
  await expect.poll(() => portrait.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);
  await page.getByRole("tab", { name: "Griglia" }).click();
  await expect(page.getByRole("tab", { name: "Griglia" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-equipment-view="grid"]')).toBeVisible();
  await expect(page.locator('.character-slot[data-slot-id^="equipment:"]')).toHaveCount(35);
  await page.getByRole("tab", { name: "Sagoma" }).click();
  await expect(page.locator('[data-equipment-view="figure"]')).toBeVisible();

  await page.getByRole("button", { name: "Riposa" }).click();
  await expect(page.getByRole("dialog", { name: "Riposa" })).toBeVisible();
  await page.getByRole("button", { name: "Annulla" }).click();

  await page.getByRole("button", { name: "Crea oggetto" }).click();
  const editor = page.getByRole("dialog", { name: "Crea oggetto" });
  await expect(editor).toBeVisible();
  await expect(editor.getByRole("group", { name: "Identità" })).toBeVisible();
  await expect(editor.getByRole("group", { name: "Classificazione" })).toBeVisible();
  await expect(editor.getByRole("group", { name: "Economia, peso e loot" })).toBeVisible();
  await expect(editor.getByRole("group", { name: "Effetti", exact: true })).toBeVisible();
  await expect(editor.getByRole("group", { name: "Profili strutturati" })).toBeVisible();
  await expect(editor.getByRole("group", { name: "Media e note" })).toBeVisible();
  await editor.getByRole("button", { name: "Chiudi" }).click();

  await page.reload();
  await expect(page.locator(".character-hud h1")).toBeVisible();
});

test("la ricerca oggetti completa il nome e i comandi dello slot equipaggiano e si chiudono", async ({ page, request }) => {
  // I comandi dello slot restano raggiungibili a lungo, quindi l'attesa finale è deliberata.
  test.setTimeout(75000);
  const characters = await (await request.get("/api/personaggi/")).json();
  const characterId = characters.data.giocatore.activePersonaggioId;
  const sheet = await (await request.get(`/api/v1/characters/${characterId}/sheet`)).json();
  const emptySlot = sheet.data.character.inventory.slots.find((slot: { isLocked: boolean; item: unknown }) => !slot.isLocked && !slot.item);
  expect(emptySlot).toBeTruthy();
  const catalog = await (await request.get("/api/v1/items?query=Pozione&limit=20")).json();
  const item = catalog.data.items[0];
  expect(item).toBeTruthy();

  await page.goto(`/character/${characterId}`);
  const search = page.getByLabel("Ricerca Oggetto");
  await search.fill(item.name);
  const suggestion = page.getByRole("option", { name: item.name, exact: false }).first();
  await expect(suggestion).toBeVisible();
  await suggestion.click();
  await expect(page.locator(".selected-item-hint")).toContainText(item.name);
  await page.getByRole("button", { name: "Svuota" }).click();
  await expect(search).toHaveValue("");
  await expect(page.locator(".selected-item-hint")).toHaveCount(0);
  await search.fill(item.name);
  await page.getByRole("option", { name: item.name, exact: false }).first().click();

  const slot = page.locator(`[data-slot-id="${emptySlot.id}"]`);
  await slot.click();
  const actions = slot.locator(".slot-inline-actions");
  await expect(actions).toBeVisible();
  const slotContentBox = await slot.locator(".slot-empty, .slot-item").boundingBox();
  const actionsBox = await actions.boundingBox();
  expect(slotContentBox).not.toBeNull();
  expect(actionsBox).not.toBeNull();
  expect(actionsBox!.y).toBeGreaterThanOrEqual(slotContentBox!.y + slotContentBox!.height - 1);
  await expect(actions.getByRole("button", { name: `Equipaggia ${item.name}`, exact: false })).toBeEnabled();
  await actions.getByRole("button", { name: `Equipaggia ${item.name}`, exact: false }).click();
  const assignedSlot = page.locator(".container-grid .character-slot").filter({ has: page.getByText(item.name, { exact: true }) });
  await expect(assignedSlot).toHaveCount(1);
  const orderedWeights = await page.locator(".container-grid .character-slot:not(.locked) .slot-item > span").allTextContents();
  const numericWeights = orderedWeights.map((value) => Number.parseFloat(value));
  expect(numericWeights).toEqual([...numericWeights].sort((left, right) => right - left));

  const assignedSlotLabel = await assignedSlot.locator("header span").textContent();
  await assignedSlot.click();
  await assignedSlot.getByRole("button", { name: `Svuota ${assignedSlotLabel}`, exact: true }).click();
  await expect(page.locator(".container-grid .character-slot").filter({ has: page.getByText(item.name, { exact: true }) })).toHaveCount(0);

  await slot.click();
  await expect(slot.locator(".slot-inline-actions")).toBeVisible();
  await page.locator(".items-workspace .panel-header").click();
  await expect(slot.locator(".slot-inline-actions")).toBeHidden();

  await slot.click();
  await expect(slot.locator(".slot-inline-actions")).toBeVisible();
  await slot.hover();
  await page.mouse.move(1, 1);
  await expect(slot.locator(".slot-inline-actions")).toBeHidden({ timeout: 15000 });
});

type SheetSlot = { id: string; slot: string; isLocked: boolean; isExtraSlot: boolean; item: unknown };

test("il menu contestuale dello slot cerca, filtra senza perdere il fuoco e riempie lo spazio", async ({ page, request }) => {
  const characters = await (await request.get("/api/personaggi/")).json();
  const characterId = characters.data.giocatore.activePersonaggioId;
  const sheet = await (await request.get(`/api/v1/characters/${characterId}/sheet`)).json();
  const emptySlot = sheet.data.character.inventory.slots.find((entry: SheetSlot) => !entry.isLocked && !entry.item);
  expect(emptySlot).toBeTruthy();

  await page.goto(`/character/${characterId}`);
  await page.locator(`[data-slot-id="${emptySlot.id}"]`).click({ button: "right" });

  const picker = page.locator(".slot-item-picker");
  await expect(picker).toBeVisible();
  const search = picker.getByRole("textbox");
  await expect(search).toBeFocused();

  const filter = picker.locator(".slot-item-picker-filter > button").first();
  await filter.click();
  await expect(search).toBeFocused();
  const options = picker.locator(".slot-item-picker-options button");
  await expect(options.first()).toBeVisible();
  await options.first().click();
  await expect(search).toBeFocused();
  await expect(picker.locator(".slot-item-picker-filter > button.active")).toHaveCount(1);

  await picker.getByRole("button", { name: "Azzera filtri" }).click();
  await expect(search).toBeFocused();
  await expect(picker.locator(".slot-item-picker-filter > button.active")).toHaveCount(0);

  const results = picker.locator(".slot-item-picker-results button");
  await expect(results.first()).toBeVisible();
  const chosen = await results.first().locator(".slot-item-picker-name").innerText();
  await results.first().click();

  await expect(picker).toHaveCount(0);
  await expect(page.locator(".container-grid .character-slot").filter({ hasText: chosen })).toHaveCount(1);
});

test("Equipaggia sceglie da solo il primo slot libero compatibile", async ({ page, request }) => {
  const characters = await (await request.get("/api/personaggi/")).json();
  const characterId = characters.data.giocatore.activePersonaggioId;
  const sheet = await (await request.get(`/api/v1/characters/${characterId}/sheet`)).json();
  const freeSlots: SheetSlot[] = sheet.data.character.equipment.slots
    .filter((entry: SheetSlot) => !entry.isExtraSlot && !entry.isLocked && !entry.item);

  let item: { name: string; compatibleEquipmentSlots: string[] } | null = null;
  for (const candidate of freeSlots) {
    const found = await (await request.get(`/api/v1/items?group=equipment&slot=${candidate.slot}&limit=1`)).json();
    if (found.data.items.length > 0) { item = found.data.items[0]; break; }
  }
  expect(item).toBeTruthy();
  // La stessa regola del client: vince il primo slot nominato, libero e compatibile.
  const expected = freeSlots.find((entry) => item!.compatibleEquipmentSlots.includes(entry.slot));
  expect(expected).toBeTruthy();

  await page.goto(`/character/${characterId}`);
  await page.getByLabel("Ricerca Oggetto").fill(item!.name);
  await page.getByRole("option", { name: item!.name, exact: false }).first().click();
  await page.locator(".selected-item-hint").getByRole("button", { name: "Equipaggia" }).click();

  await expect(page.locator(`[data-slot-id="${expected!.id}"]`)).toContainText(item!.name);
});

test("gli effetti personali si configurano nella scheda e aggiornano subito il PG", async ({ page, request }) => {
  const characters = await (await request.get("/api/personaggi/")).json();
  const characterId = characters.data.giocatore.activePersonaggioId;
  const effectName = `Verifica effetto UI ${Date.now()}`;

  await page.goto(`/character/${characterId}`);
  await expect(page.locator(".items-workspace")).toBeVisible();
  await page.getByRole("button", { name: "Crea un nuovo effetto" }).click();
  await expect(page.getByRole("region", { name: "Gestione effetti" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Torna a equipaggiamento e inventario" })).toBeVisible();
  await expect(page.locator(".items-workspace")).toBeHidden();

  const editor = page.locator(".effect-editor");
  await editor.getByLabel("Nome", { exact: true }).fill(effectName);
  await expect(editor.getByLabel("Tipo", { exact: true })).toHaveCount(0);
  await editor.getByLabel("Origine", { exact: true }).fill("Test Playwright");
  await expect(editor.getByText("Temporaneo", { exact: true })).toBeVisible();
  await expect(editor.getByText("Temporaneo (t)", { exact: true })).toHaveCount(0);
  await expect(editor.getByText("È solo un contrassegno: non avvia alcun conteggio.", { exact: true })).toHaveCount(0);
  const headerFieldBottoms = await editor.locator(".effect-fields-grid > label").evaluateAll((labels) => labels.slice(0, 3).map((label) => Math.round(label.getBoundingClientRect().bottom)));
  expect(new Set(headerFieldBottoms).size).toBe(1);
  await editor.getByLabel("Descrizione", { exact: true }).fill("Verifica del configuratore effetti.");
  await editor.getByRole("checkbox").check();
  await editor.getByLabel("Campo", { exact: true }).fill("Forza");
  await expect(editor.getByLabel("Operazione", { exact: true })).toHaveValue("add");
  await editor.getByLabel("Valore o formula", { exact: true }).fill("floor(personaggio.livello / 2) + 1");
  await editor.getByLabel("Condizione, facoltativa", { exact: true }).fill("personaggio.livello >= 1");
  const runeAsset = editor.locator('img[src*="Runa%20arcana.webp"]');
  await expect(runeAsset).toBeVisible();
  await expect.poll(() => runeAsset.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(128);
  await editor.getByLabel("Cerca un'icona", { exact: true }).fill("mana");
  const manaIcon = editor.getByRole("radio", { name: "Mana", exact: true });
  await expect(manaIcon).toHaveCount(1);
  await expect(editor.locator(".effect-icon-picker-grid").getByText("Mana", { exact: true })).toHaveCount(0);
  await expect(manaIcon.locator("xpath=following-sibling::span")).toHaveAttribute("title", "Mana");
  await editor.getByText("Mini guida alle operazioni", { exact: true }).click();
  await expect(editor.getByRole("heading", { name: "Imposta forte", exact: true })).toBeVisible();
  await editor.getByText("Guida rapida alle formule", { exact: true }).click();
  await expect(editor.getByText("max(1, ceil(final.mana / 10))", { exact: true })).toBeVisible();
  await editor.getByRole("button", { name: "Crea effetto" }).click();

  await expect(page.getByRole("heading", { name: effectName })).toBeVisible();
  const effectIcon = page.getByRole("button", { name: `Apri effetto ${effectName}` });
  await expect(effectIcon).toBeVisible();
  await expect(effectIcon).toHaveClass(/temporary/);
  await expect(page.getByText("(t) Temporaneo", { exact: true })).toBeVisible();
  await expect(page.locator(".effect-operation-summary")).toContainText("floor(personaggio.livello / 2) + 1");

  await page.getByRole("button", { name: "Modifica il valore o la formula della modifica 1" }).click();
  await expect(editor.getByLabel("Valore o formula", { exact: true })).toBeFocused();
  await editor.getByRole("button", { name: "Annulla" }).click();
  await page.getByRole("button", { name: "Modifica il campo della modifica 1" }).click();
  await expect(editor.getByLabel("Campo", { exact: true })).toBeFocused();
  await editor.getByRole("button", { name: "Annulla" }).click();

  await page.getByRole("button", { name: "Torna a equipaggiamento e inventario" }).click();
  await expect(page.locator(".items-workspace")).toBeVisible();
  await effectIcon.click();
  await expect(page.getByRole("heading", { name: effectName })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Rimuovi", exact: true }).click();
  await expect(effectIcon).toHaveCount(0);
});

test("il layout desktop resta utilizzabile a 1280x720", async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const characters = await (await request.get("/api/personaggi/")).json();
  await page.goto(`/character/${characters.data.giocatore.activePersonaggioId}`);
  await expect(page.locator(".side-nav")).toBeVisible();
  await expect(page.locator(".character-hud")).toBeVisible();
  await expect(page.locator(".items-workspace")).toBeVisible();

  const identity = await page.locator(".character-identity").boundingBox();
  const resources = await page.locator(".resource-grid").boundingBox();
  expect(identity).not.toBeNull();
  expect(resources).not.toBeNull();
  expect(resources!.y).toBeGreaterThanOrEqual(identity!.y + identity!.height);

  const widths = await page.locator(".resource-card").evaluateAll((cards) => cards.map((card) => card.getBoundingClientRect().width));
  expect(Math.max(...widths) - Math.min(...widths)).toBeLessThanOrEqual(1);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
