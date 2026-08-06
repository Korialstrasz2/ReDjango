import { expect, test } from "@playwright/test";

test("gli strumenti esagono si aprono solo dal comando esplicito", async ({ page }) => {
  await page.goto("/combat");
  const launcher = page.locator(".combat-hex-tool-launcher");
  if (await launcher.count() === 0) {
    await page.evaluate(async () => {
      const workspaceResponse = await fetch("/api/combat/");
      const workspace = await workspaceResponse.json();
      const mapTypeId = workspace.data?.mapTypes?.[0]?.id;
      if (!mapTypeId) throw new Error("Nessun tipo mappa disponibile per il test.");
      const csrfToken = decodeURIComponent(document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || "");
      const requestId = `e2e-hex-tool-${Date.now()}`;
      const response = await fetch("/api/combat/actions/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
          action: "maps.save",
          requestId,
          payload: { name: "Mappa test strumenti esagono", mapTypeId, rows: 3, columns: 3 },
        }),
      });
      if (!response.ok) throw new Error(`Creazione mappa fallita: ${response.status}`);
    });
    await page.reload();
  }

  await expect(page.locator(".combat-hex-tool-window")).toHaveCount(0);
  const mapSurface = page.locator(".combat-map-stage svg");
  await expect(page.locator(".combat-hex").first()).toBeVisible();
  await mapSurface.click({ position: { x: 45, y: 45 } });
  await expect(page.locator(".combat-hex-tool-window")).toHaveCount(0);

  await launcher.click();
  await expect(page.locator(".combat-hex-tool-window")).toBeVisible();
});

test("la barra attivi prepara l'attacco e Percorso calcola dalla mappa", async ({ page }) => {
  await page.goto("/combat");
  const activeHeader = page.locator(".combat-active-strip-heading");
  await expect(activeHeader.getByRole("button", { name: /Mappa attiva/ })).toBeVisible();
  await expect(activeHeader.getByRole("button", { name: "Percorso" })).toBeVisible();
  const selected = page.locator(".combat-selected-character");
  const roster = page.locator(".combat-active-roster");
  const rosterCards = roster.locator(":scope > div");
  test.skip(await rosterCards.count() === 0, "Servono almeno due combattenti attivi.");

  const selectedId = await selected.locator(":scope > header").getAttribute("data-combat-character-id");
  await expect(selectedId).not.toBeNull();
  await expect(roster.locator(`[data-combat-character-id="${selectedId}"]`)).toHaveCount(0);

  const source = rosterCards.first().locator(":scope > button:first-child");
  await source.click();
  const contextDialog = page.getByRole("dialog");
  await expect(contextDialog.getByRole("button", { name: "Metti in primo piano" })).toBeVisible();
  await page.keyboard.press("Escape");

  await source.dragTo(selected.locator(":scope > header"));
  const attackPanel = page.locator(".combat-attack-drawer.open");
  await expect(attackPanel).toBeVisible();
  const attackerId = await source.getAttribute("data-combat-character-id");
  await expect(attackPanel.getByLabel("Attaccante", { exact: true })).toHaveValue(attackerId || "");
  await expect(attackPanel.getByLabel("Difensore", { exact: true })).toHaveValue(selectedId || "");

  await page.getByRole("button", { name: "Percorso", exact: true }).click();
  await expect(page.getByRole("button", { name: "Scegli destinazione…", exact: true })).toBeVisible();
  const hexes = page.locator(".combat-hex");
  const hexCount = await hexes.count();
  expect(hexCount).toBeGreaterThan(2);
  await hexes.nth(Math.min(50, hexCount - 1)).click({ position: { x: 10, y: 10 } });
  await expect(page.locator(".combat-map-status")).toContainText("Rapido");
  await expect(page.locator(".toast")).toContainText("Percorsi calcolati");
});

test("Azioni rapide è una finestra ridimensionabile senza ombra scura", async ({ page }) => {
  await page.goto("/combat");
  await expect(page.getByRole("button", { name: /Mappa attiva/ })).toBeVisible();
  const trigger = page.getByRole("button", { name: /Azioni rapide/ });
  test.skip(await trigger.count() === 0, "Serve una mappa di combattimento attiva.");
  await trigger.click();

  const dialog = page.locator(".combat-quick-actions-modal");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(".rd-modal-resize-handle")).toHaveCount(4);
  await expect(dialog).toHaveCSS("box-shadow", "none");
  await expect(page.locator(".modal-backdrop:has(.combat-quick-actions-modal)")).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
  // Niente intestazione: restano soltanto corpo e piè di pagina.
  await expect(dialog.locator(".modal-header")).toHaveCount(0);

  const original = await dialog.boundingBox();
  expect(original).not.toBeNull();
  const grip = dialog.locator(".modal-drag-grip");
  const gripBox = await grip.boundingBox();
  expect(gripBox).not.toBeNull();
  await page.mouse.move(gripBox!.x + gripBox!.width / 2, gripBox!.y + gripBox!.height / 2);
  await page.mouse.down();
  await page.mouse.move(gripBox!.x + 60, gripBox!.y + 15, { steps: 5 });
  await page.mouse.up();
  const moved = await dialog.boundingBox();
  expect(moved).not.toBeNull();
  expect(moved!.x).toBeGreaterThan(original!.x + 25);

  const leftHandle = dialog.locator('[data-resize-edge="left"]');
  const handleBox = await leftHandle.boundingBox();
  expect(handleBox).not.toBeNull();
  await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + handleBox!.height / 2);
  await page.mouse.down();
  await page.mouse.move(handleBox!.x + 70, handleBox!.y + handleBox!.height / 2, { steps: 5 });
  await page.mouse.up();
  const resized = await dialog.boundingBox();
  expect(resized).not.toBeNull();
  expect(resized!.width).toBeLessThan(moved!.width - 50);
});

test("i PA del combattimento restano locali e offrono incrementi e riduzioni rapide", async ({ page }) => {
  await page.goto("/combat");
  const resources = page.locator(".combat-selected-resources");
  test.skip(await resources.count() === 0, "Serve un personaggio attivo sulla mappa.");

  await expect(resources.locator('[data-resource="stanchezza"]')).toHaveCount(0);
  const actionPoints = resources.locator('[data-resource="pa"]');
  const initialText = (await actionPoints.locator(".combat-rail-resource-heading strong").textContent()) || "0/0";
  const maximum = Number(initialText.split("/")[1] || 0);
  test.skip(maximum <= 0, "Servono Punti Azione positivi.");

  await actionPoints.getByRole("button", { name: "Riduci Punti Azione", exact: true }).click();
  await expect(actionPoints.locator(".combat-rail-resource-heading strong")).toHaveText(`${maximum - 1}/${maximum}`);
  await expect(actionPoints.getByRole("button", { name: "Riduci Punti Azione di 5" })).toBeVisible();
  await expect(actionPoints.getByRole("button", { name: "Riduci Punti Azione di 20" })).toBeVisible();

  const increase = actionPoints.getByRole("button", { name: "Aumenta Punti Azione", exact: true });
  await increase.hover();
  await expect(actionPoints.getByRole("button", { name: "Aumenta Punti Azione di 5" })).toBeVisible();
  await expect(actionPoints.getByRole("button", { name: "Aumenta Punti Azione di 20" })).toBeVisible();

  await page.reload();
  await expect(page.locator('.combat-selected-resources [data-resource="pa"] .combat-rail-resource-heading strong')).toHaveText(`${maximum}/${maximum}`);
});

test("Azioni rapide seleziona il tipo e converte l'effetto in Mana", async ({ page }) => {
  await page.goto("/combat");
  const trigger = page.getByRole("button", { name: /Azioni rapide/ });
  test.skip(await trigger.count() === 0, "Serve una mappa di combattimento attiva.");
  await trigger.click();

  const dialog = page.locator(".combat-quick-actions-modal");
  const ordinaryAction = dialog.locator(".combat-quick-option-list > button.power").first();
  test.skip(await ordinaryAction.count() === 0, "Serve un'azione rapida non magica.");
  await ordinaryAction.click();
  await expect(dialog.getByLabel("Tipo")).toHaveValue("power");

  const effect = dialog.getByLabel("Effetto", { exact: true });
  await effect.fill("7");
  await expect(dialog.locator(".planner-costs label").filter({ hasText: /^mana$/i }).locator("input")).toHaveValue("7");
  await dialog.getByRole("button", { name: "Aumenta effetto" }).click();
  await expect(effect).toHaveValue("8");
  await expect(dialog.getByText(/1 effetto = 1 Mana/)).toBeVisible();
});

test("il personaggio trascinato sulla mappa resta visibile sotto il cursore", async ({ page }) => {
  await page.goto("/combat");
  await expect(page.getByRole("button", { name: /Mappa attiva/ })).toBeVisible();
  const movableTokens = page.locator(".combat-token.can-move");
  test.skip(await movableTokens.count() === 0, "Serve un personaggio controllabile sulla mappa.");

  const token = movableTokens.first();
  const tokenBox = await token.boundingBox();
  expect(tokenBox).not.toBeNull();
  const start = { x: tokenBox!.x + tokenBox!.width / 2, y: tokenBox!.y + tokenBox!.height / 2 };
  const pointer = { x: start.x + 48, y: start.y + 34 };
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(pointer.x, pointer.y, { steps: 5 });

  await expect(page.locator(".combat-token.drag-origin")).toHaveCount(1);
  const preview = page.locator(".combat-token-drag-preview");
  await expect(preview).toBeVisible();
  const previewBox = await preview.boundingBox();
  expect(previewBox).not.toBeNull();
  expect(previewBox!.x + previewBox!.width / 2).toBeCloseTo(pointer.x, -1);
  expect(previewBox!.y + previewBox!.height / 2).toBeCloseTo(pointer.y, -1);

  await page.goto("/");
  await page.mouse.up();
});
