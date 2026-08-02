import { expect, test } from "@playwright/test";

test("la famiglia selezionata resta nella griglia come carta quadrata", async ({ page }) => {
  await page.goto("/skills");
  await expect(page.getByRole("heading", { name: /Abilit/ })).toBeVisible();

  const groups = page.locator(".skill-group-rail");
  await groups.getByRole("button", { name: /Scuole di Magia/ }).click();
  const familyNav = page.locator(".skill-family-nav");
  const targetFamily = familyNav.getByRole("tab", { name: /Misticismo/ });
  await targetFamily.click();

  await expect(targetFamily).toHaveAttribute("aria-selected", "true");
  await expect(targetFamily).toHaveCSS("aspect-ratio", "1 / 1");
  const targetBounds = await targetFamily.boundingBox();
  expect(targetBounds).not.toBeNull();
  expect(Math.abs(targetBounds!.width - targetBounds!.height)).toBeLessThanOrEqual(1);
  expect(await targetFamily.evaluate((button) => getComputedStyle(button, "::before").backgroundSize)).toBe("contain");

  const unselectedBounds = await familyNav.locator('button[aria-selected="false"]').first().boundingBox();
  expect(unselectedBounds).not.toBeNull();
  expect(unselectedBounds!.height).toBeLessThan(unselectedBounds!.width);
  await expect(page.locator(".skill-family-pop")).toHaveCount(0);
});

test("le abilità usano gruppi laterali, famiglie in alto e carte interamente cliccabili", async ({ page }) => {
  await page.goto("/skills");

  await expect(page.getByRole("heading", { name: /Abilit/ })).toBeVisible();
  const xpRibbon = page.getByRole("button", { name: "Modifica Punti Esperienza disponibili" });
  await expect(xpRibbon.getByText("Punti Esperienza Spesi", { exact: true })).toBeVisible();
  await xpRibbon.click();
  await expect(page.getByRole("dialog", { name: "Modifica Punti Esperienza" })).toBeVisible();
  await expect(page.getByLabel("Competenze", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Annulla" }).click();

  const groups = page.locator(".skill-group-rail");
  await expect(groups.getByRole("button")).toHaveCount(7);
  await expect(groups.getByRole("button", { name: /Generali/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".skill-family-nav > button")).toHaveCount(15);
  await expect(page.locator(".skill-family-nav").getByRole("tab", { name: /Viaggio e Inventario/ })).toBeVisible();
  await expect(page.getByText("Categoria iniziale per l'organizzazione delle abilità V2.", { exact: true })).toHaveCount(0);

  const initialSelectedFamily = page.locator('.skill-family-nav > button[aria-selected="true"]');
  await expect(initialSelectedFamily).toHaveCSS("aspect-ratio", "1 / 1");
  const initialSelectedBounds = await initialSelectedFamily.boundingBox();
  expect(initialSelectedBounds).not.toBeNull();
  expect(Math.abs(initialSelectedBounds!.width - initialSelectedBounds!.height)).toBeLessThanOrEqual(1);
  const initialUnselectedBounds = await page.locator('.skill-family-nav > button[aria-selected="false"]').first().boundingBox();
  expect(initialUnselectedBounds).not.toBeNull();
  expect(initialUnselectedBounds!.height).toBeLessThan(initialUnselectedBounds!.width);
  await expect(page.locator(".skill-family-pop")).toHaveCount(0);

  await page.getByRole("button", { name: "Crea abilità", exact: true }).click();
  const createDialog = page.getByRole("dialog", { name: "Crea abilità" });
  const exampleSelect = createDialog.getByLabel("Usa un'abilità come esempio");
  await expect(exampleSelect).toBeVisible();
  const firstExample = exampleSelect.locator("option").nth(1);
  const firstExampleValue = await firstExample.getAttribute("value");
  expect(firstExampleValue).toBeTruthy();
  await exampleSelect.selectOption(firstExampleValue!);
  const copiedName = createDialog.getByRole("textbox", { name: "Nome", exact: true }).first();
  await expect(copiedName).not.toHaveValue("");
  await expect(createDialog.getByRole("button", { name: "Crea abilità", exact: true })).toBeDisabled();
  await copiedName.fill(`${await copiedName.inputValue()} - copia`);
  await expect(createDialog.getByRole("button", { name: "Crea abilità", exact: true })).toBeEnabled();
  await createDialog.getByRole("button", { name: "Annulla", exact: true }).click();

  await groups.getByRole("button", { name: /Scuole di Magia/ }).click();
  await expect(groups.getByRole("button", { name: /Scuole di Magia/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".skill-family-nav > button")).toHaveCount(8);
  await page.locator(".skill-family-nav").getByRole("tab", { name: /Misticismo/ }).click();
  const selectedFamily = page.locator(".skill-family-nav").getByRole("tab", { name: /Misticismo/ });
  await expect(selectedFamily).toHaveClass(/active/);
  await expect(selectedFamily.locator("span")).toHaveCSS("visibility", "hidden");
  await expect(selectedFamily).toHaveCSS("aspect-ratio", "1 / 1");
  expect(await selectedFamily.evaluate((button) => getComputedStyle(button, "::before").opacity)).toBe("1");
  expect(await selectedFamily.evaluate((button) => getComputedStyle(button, "::before").filter)).toBe("none");
  expect(await selectedFamily.evaluate((button) => getComputedStyle(button, "::before").backgroundSize)).toBe("contain");
  await expect(page.locator(".skill-family-pop")).toHaveCount(0);
  await expect(page.locator(".skill-catalog").getByRole("heading", { name: "Misticismo", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "POC - Intuito arcano", exact: true })).toHaveCount(0);

  await groups.getByRole("button", { name: /Cerca Abilità/ }).click();
  await expect(page.getByRole("heading", { name: "Cerca Abilità", exact: true })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Nome dell'abilità" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Qualsiasi testo nella carta" })).toBeVisible();
  await page.locator(".skill-search-advanced > summary").click();
  await page.getByRole("checkbox", { name: "Includi archiviate" }).check();
  await page.getByRole("searchbox", { name: "Nome dell'abilità" }).fill("POC - Intuito arcano");
  await expect(page.getByRole("heading", { name: "POC - Intuito arcano", exact: true })).toBeVisible();
  const spellCard = page.locator('.skill-card[data-spell-tier="base"]', { hasText: "POC - Intuito arcano" });
  await expect(spellCard).toBeVisible();
  await expect(spellCard.locator(".skill-card-number")).toHaveCount(0);
  await expect(spellCard.getByText(/Base \d+/)).toHaveCount(0);
  await expect(spellCard.getByText(/passivi|azioni/)).toHaveCount(0);
  await expect(spellCard.getByRole("button", { name: "Apri la carta" })).toHaveCount(0);
  await spellCard.click();
  await expect(page.getByText("Costo base", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Costo", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Incantesimo", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Calcola l'incantesimo", exact: true })).toBeVisible();
  await expect(page.getByText("Predisposto per il combattimento", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Modifica", exact: true }).click();
  await expect(page.getByLabel("Costo PE base", { exact: false })).toHaveValue("7");
  await expect(page.getByLabel("Livello minimo", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Riassunto", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Chiudi" }).click();

  await groups.getByRole("button", { name: /Personaggio/ }).click();
  await expect(page.getByRole("tab", { name: /^Sbloccate/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Analisi PG", exact: true })).toBeVisible();
  await expect(page.locator(".skill-card").first()).toBeVisible();
  await page.getByRole("tab", { name: "Analisi PG", exact: true }).click();
  await expect(page.getByRole("button", { name: /Progressione/ })).toBeVisible();
  await page.getByRole("button", { name: /Progressione/ }).click();
  await expect(page.getByRole("dialog", { name: "Progressione del personaggio" })).toBeVisible();
  await expect(page.getByText("Mancano", { exact: true })).toBeVisible();
});
