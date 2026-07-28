import { expect, test } from "@playwright/test";

test("Diario e Dadi sono strumenti rapidi persistenti e usabili", async ({ page, request }) => {
  const characters = await (await request.get("/api/personaggi/")).json();
  const characterId = characters.data.giocatore.activePersonaggioId;
  const activeCharacter = characters.data.personaggi.find((character: { id: number }) => character.id === characterId);
  await page.goto(`/character/${characterId}`);

  const diceButton = page.getByRole("button", { name: /^Dadi/ });
  const journalButton = page.getByRole("button", { name: /^Diario/ });
  await expect(page.locator(".quick-tools-bar")).toBeVisible();
  await expect(page.locator(".side-nav").getByRole("button", { name: /^(Diario|Dadi)/ })).toHaveCount(0);
  await expect(page.locator(".brand-block strong")).toHaveText(activeCharacter.name.split(/\s+/)[0]);
  await expect(page.locator(".user-chip")).toHaveCount(0);
  await expect(diceButton).toBeVisible();
  await expect(journalButton).toBeVisible();

  await diceButton.click();
  const diceDrawer = page.getByRole("dialog", { name: "Dadi" });
  await expect(diceDrawer).toBeVisible();
  await expect(diceDrawer.locator(".dice-grid .dice-visual")).toHaveCount(7);
  await expect(diceDrawer.locator(".dice-grid .dice-geometry")).toHaveCount(7);
  await diceDrawer.getByRole("button", { name: "Tira d20" }).click();
  await expect(diceDrawer.locator(".dice-equation strong")).toHaveText(/^\d+$/);
  await expect(diceDrawer.locator(".dice-history li")).toHaveCount(1);
  await diceDrawer.getByRole("tab", { name: "Tiri del gruppo" }).click();
  await expect(diceDrawer.locator(".group-dice-history-list > li").first()).toContainText(activeCharacter.name);
  await expect(diceDrawer.locator(".group-dice-history-list > li").first()).toContainText(characters.data.giocatore.displayName);
  await diceDrawer.getByRole("tab", { name: "Tiro", exact: true }).click();
  await diceDrawer.getByRole("button", { name: "Chiudi Dadi" }).click();

  const contextNoteButton = page.getByRole("button", { name: "Note della pagina: Zaino" });
  const contextNote = page.getByRole("complementary", { name: `Note Zaino di ${activeCharacter.name}` });
  await expect(contextNote).toBeHidden();
  await contextNoteButton.hover();
  await expect(contextNote).toBeVisible();
  await expect(contextNote).toHaveCSS("opacity", "1");
  const pageNotes = contextNote.getByLabel("Note Zaino");
  const originalNotes = await pageNotes.inputValue();
  const sharedText = `Corde, torce e sigilli ${Date.now()}`;
  await pageNotes.fill(sharedText);
  await pageNotes.blur();
  await expect(contextNote.locator(".note-save-status")).toHaveText("Salvato");
  await contextNoteButton.click();
  await expect(contextNoteButton).toHaveAttribute("aria-pressed", "true");
  await page.mouse.move(760, 110);
  await expect(contextNote).toBeVisible();

  await journalButton.click();
  const journalDrawer = page.getByRole("dialog", { name: "Diario" });
  await expect(journalDrawer).toBeVisible();
  await journalDrawer.getByRole("button", { name: "Zaino" }).click();
  const diaryNotes = journalDrawer.getByLabel("Note Zaino");
  await expect(diaryNotes).toHaveValue(sharedText);
  await diaryNotes.fill(originalNotes);
  await diaryNotes.blur();
  await expect(journalDrawer.locator(".note-save-status")).toHaveText("Salvato");
  await expect(pageNotes).toHaveValue(originalNotes);
});

test("la barra rapida mostra la campagna e ricorda il meteo ogni sei ore", async ({ page, request }) => {
  const bootstrap = await (await request.get("/api/bootstrap/")).json();
  const campaign = bootstrap.data.campaigns.find((entry: { id: number }) => entry.id === bootstrap.data.activeCampaignId);
  await page.goto("/");

  const status = page.getByRole("group", { name: "Informazioni della campagna" });
  const reminder = page.getByRole("dialog", { name: "Tempo atmosferico" });
  const entryValue = (label: string) => status.locator(".campaign-status-entry", { hasText: label }).locator(".campaign-status-value");
  const hourValue = entryValue("Ora:");

  await expect(status).toContainText(campaign.name);
  await expect(entryValue("Giorno:")).toHaveText(String(campaign.daysSinceStart));
  await expect(status.locator(".campaign-status-weather")).toHaveText(campaign.weatherLabel || "Sconosciuto");

  // The clock is restored press by press, so the run leaves the campaign as it found it.
  const startingHour = Number((await hourValue.innerText()).replace("—", "")) || 0;
  const stepsToReminder = (6 - (startingHour % 6)) % 6 || 6;
  const stepHour = async (direction: "Ora successiva" | "Ora precedente", expected: number) => {
    await status.getByRole("button", { name: direction }).click();
    await expect(hourValue).toHaveText(String(expected));
    const later = reminder.getByRole("button", { name: "Più tardi" });
    if (await later.count()) await later.click();
  };

  for (let step = 1; step < stepsToReminder; step += 1) {
    await stepHour("Ora successiva", (startingHour + step) % 24);
  }
  await status.getByRole("button", { name: "Ora successiva" }).click();
  await expect(hourValue).toHaveText(String((startingHour + stepsToReminder) % 24));
  await expect(reminder).toBeVisible();
  await expect(reminder).toContainText("ricorda di tirare il tempo atmosferico");
  await reminder.getByRole("button", { name: "Più tardi" }).click();
  await expect(reminder).toHaveCount(0);

  for (let step = stepsToReminder - 1; step >= 0; step -= 1) {
    await stepHour("Ora precedente", (startingHour + step) % 24);
  }
});

test("la pagina Combattimento espone le sue note in anteprima e le può fissare", async ({ page, request }) => {
  const characters = await (await request.get("/api/personaggi/")).json();
  const characterId = characters.data.giocatore.activePersonaggioId;
  const activeCharacter = characters.data.personaggi.find((character: { id: number }) => character.id === characterId);
  const notes = await (await request.get(`/api/v1/characters/${characterId}/notes`)).json();

  await page.goto("/combat");
  await expect(page.getByRole("button", { name: /Mappa attiva/ })).toBeVisible();

  const trigger = page.getByRole("button", { name: "Note della pagina: Combattimento" });
  const flyout = page.getByRole("complementary", { name: `Note Combattimento di ${activeCharacter.name}` });
  await expect(flyout).toBeHidden();
  await trigger.hover();
  await expect(flyout).toBeVisible();
  await expect(flyout).toHaveCSS("opacity", "1");
  await expect(flyout.getByLabel("Note Combattimento")).toHaveValue(notes.data.sections.combat);

  await page.mouse.move(760, 110);
  await expect(flyout).toBeHidden();
  await expect(page.locator(".context-note-flyout")).toHaveCSS("opacity", "0");

  await trigger.click();
  await page.mouse.move(760, 110);
  await expect(trigger).toHaveAttribute("aria-pressed", "true");
  await expect(flyout).toBeVisible();
});

test("i drawer restano nel viewport desktop a 1280px", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto("/");
  await page.getByRole("button", { name: /^Diario/ }).click();
  const drawer = page.getByRole("dialog", { name: "Diario" });
  await drawer.evaluate((element) => Promise.all(element.getAnimations().map((animation) => animation.finished)));
  const box = await drawer.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(1280);
  expect(box!.height).toBeLessThanOrEqual(720);
  expect(box!.x + box!.width / 2).toBeCloseTo(640, 0);
  expect(box!.y + box!.height / 2).toBeCloseTo(360, 0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);

  const journalHeader = drawer.locator(".tool-drawer-header");
  const journalHeaderBox = await journalHeader.boundingBox();
  expect(journalHeaderBox).not.toBeNull();
  await page.mouse.move(journalHeaderBox!.x + 110, journalHeaderBox!.y + 30);
  await page.mouse.down();
  await page.mouse.move(journalHeaderBox!.x + 180, journalHeaderBox!.y + 50, { steps: 5 });
  await page.mouse.up();
  const movedJournalBox = await drawer.boundingBox();
  expect(movedJournalBox!.x).toBeGreaterThan(box!.x + 55);

  const journalRightResizeHandle = drawer.locator('[data-resize-edge="right"]');
  const journalResizeHandleBox = await journalRightResizeHandle.boundingBox();
  expect(journalResizeHandleBox).not.toBeNull();
  await page.mouse.move(journalResizeHandleBox!.x + journalResizeHandleBox!.width / 2, journalResizeHandleBox!.y + journalResizeHandleBox!.height / 2);
  await page.mouse.down();
  await page.mouse.move(journalResizeHandleBox!.x + 70, journalResizeHandleBox!.y + journalResizeHandleBox!.height / 2, { steps: 5 });
  await page.mouse.up();
  const resizedJournalBox = await drawer.boundingBox();
  expect(resizedJournalBox!.width).toBeGreaterThan(movedJournalBox!.width + 50);
  await page.getByRole("button", { name: "Chiudi Diario" }).click();

  await page.getByRole("button", { name: /^Dadi/ }).click();
  const diceDrawer = page.getByRole("dialog", { name: "Dadi" });
  await diceDrawer.evaluate((element) => Promise.all(element.getAnimations().map((animation) => animation.finished)));
  const diceBox = await diceDrawer.boundingBox();
  expect(diceBox).not.toBeNull();
  expect(diceBox!.width).toBeLessThanOrEqual(551);
  expect(diceBox!.height).toBeLessThanOrEqual(650);
  expect(diceBox!.x + diceBox!.width / 2).toBeCloseTo(640, 0);
  expect(diceBox!.y + diceBox!.height / 2).toBeCloseTo(360, 0);
  const scrollbarWidth = await diceDrawer.locator(".tool-drawer-body").evaluate((element) => getComputedStyle(element).getPropertyValue("scrollbar-width"));
  expect(scrollbarWidth).toBe("none");
  const header = diceDrawer.locator(".tool-drawer-header");
  const headerBox = await header.boundingBox();
  expect(headerBox).not.toBeNull();
  await page.mouse.move(headerBox!.x + 90, headerBox!.y + 30);
  await page.mouse.down();
  await page.mouse.move(headerBox!.x - 30, headerBox!.y + 70, { steps: 5 });
  await page.mouse.up();
  const movedDiceBox = await diceDrawer.boundingBox();
  expect(movedDiceBox!.x).toBeLessThan(diceBox!.x - 80);

  const leftResizeHandle = diceDrawer.locator('[data-resize-edge="left"]');
  const resizeHandleBox = await leftResizeHandle.boundingBox();
  expect(resizeHandleBox).not.toBeNull();
  await page.mouse.move(resizeHandleBox!.x + resizeHandleBox!.width / 2, resizeHandleBox!.y + resizeHandleBox!.height / 2);
  await page.mouse.down();
  await page.mouse.move(resizeHandleBox!.x - 80, resizeHandleBox!.y + resizeHandleBox!.height / 2, { steps: 5 });
  await page.mouse.up();
  const resizedDiceBox = await diceDrawer.boundingBox();
  expect(resizedDiceBox!.width).toBeGreaterThan(movedDiceBox!.width + 60);

  await diceDrawer.getByRole("button", { name: "Chiudi Dadi" }).click();
  await page.getByRole("button", { name: /^Dadi/ }).click();
  const reopenedDiceDrawer = page.getByRole("dialog", { name: "Dadi" });
  await reopenedDiceDrawer.evaluate((element) => Promise.all(element.getAnimations().map((animation) => animation.finished)));
  const reopenedDiceBox = await reopenedDiceDrawer.boundingBox();
  expect(reopenedDiceBox!.x).toBeCloseTo(diceBox!.x, 0);
  expect(reopenedDiceBox!.y).toBeCloseTo(diceBox!.y, 0);
  expect(reopenedDiceBox!.width).toBeCloseTo(diceBox!.width, 0);
  expect(reopenedDiceBox!.height).toBeCloseTo(diceBox!.height, 0);
});

test("le scorciatoie configurate aprono pagine, Diario e Dadi", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("link", { name: "Sala principale", exact: true }).press("Alt+G");
  await expect(page).toHaveURL(/\/guides$/);
  await expect(page.getByRole("heading", { name: "Guide", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Guide", exact: true }).press("Alt+B");
  await expect(page).toHaveURL(/\/combat$/);
  await expect(page.getByRole("button", { name: /Mappa attiva/ })).toBeVisible();

  await page.getByRole("link", { name: "Combattimento", exact: true }).press("Alt+I");
  await expect(page).toHaveURL(/\/settings$/);
  await page.getByRole("tab", { name: "Scorciatoie" }).click();
  await expect(page.locator('.setting-row:has-text("Diario rapido") select')).toHaveValue("Alt+J");
  await expect(page.locator('.setting-row:has-text("Combattimento") select')).toHaveValue("Alt+B");
  const skillsShortcut = page.locator('.setting-row:has-text("Abilità") select');
  const loreShortcut = page.locator('.setting-row:has-text("Lore") select');
  await expect(skillsShortcut).toHaveValue("Alt+A");
  await expect(page.locator('.setting-row:has-text("Competenze") select')).toHaveValue("Alt+N");
  await expect(page.locator('.setting-row:has-text("Creazione") select')).toHaveValue("Alt+K");
  await expect(page.locator('.setting-row:has-text("Viaggio") select')).toHaveValue("Alt+V");
  await expect(page.locator('.setting-row:has-text("Mercato") select')).toHaveValue("Alt+Q");
  await expect(loreShortcut).toHaveValue("Alt+L");
  await expect(page.locator('.setting-row:has-text("Strumenti") select')).toHaveValue("Alt+T");

  await page.locator('.setting-row:has-text("Profilo scorciatoie") select').selectOption("custom");
  await loreShortcut.selectOption("Alt+A");
  await expect(page.locator(".setting-row-conflict")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Salva impostazioni" })).toBeDisabled();
  await loreShortcut.selectOption("Alt+L");
  await expect(page.locator(".setting-row-conflict")).toHaveCount(0);

  await page.getByRole("link", { name: "Impostazioni", exact: true }).press("Alt+J");
  await expect(page.getByRole("dialog", { name: "Diario" })).toBeVisible();
  await page.getByRole("button", { name: "Chiudi Diario" }).press("Escape");
  await expect(page.getByRole("dialog", { name: "Diario" })).toHaveCount(0);

  await page.getByRole("button", { name: /^Dadi/ }).press("Alt+R");
  await expect(page.getByRole("dialog", { name: "Dadi" })).toBeVisible();
  await page.getByRole("button", { name: "Chiudi Dadi" }).click();

  await page.getByRole("link", { name: "Impostazioni", exact: true }).press("Alt+A");
  await expect(page).toHaveURL(/\/skills$/);
  await expect(page.getByRole("heading", { name: "Abilità", exact: true }).first()).toBeVisible();
});
