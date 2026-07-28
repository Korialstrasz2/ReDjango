import { expect, test } from "@playwright/test";

test("l'indice delle guide resta compatto e indipendente dal contenuto", async ({ page }) => {
  await page.goto("/guides");

  const index = page.locator(".guide-index");
  await expect(index).toHaveCSS("position", "sticky");
  await expect(index).toHaveCSS("align-content", "start");

  const indexBox = await index.boundingBox();
  expect(indexBox?.width).toBeGreaterThanOrEqual(299);
  expect(indexBox?.width).toBeLessThanOrEqual(301);

  const cardHeights = await index.locator("button").evaluateAll((buttons) => buttons.map((button) => button.getBoundingClientRect().height));
  expect(cardHeights.length).toBeGreaterThan(1);
  expect(Math.max(...cardHeights)).toBeLessThan(100);
});

test("le immagini dell'archivio si aprono al clic", async ({ page, request }) => {
  const response = await request.get("/api/media/");
  const library = await response.json();
  const asset = library.data.assets[0];
  test.skip(!asset, "L'archivio non contiene immagini da aprire.");

  await page.goto("/media");
  await page.getByRole("button", { name: `Apri ${asset.title}` }).first().click();

  const preview = page.getByRole("dialog", { name: asset.title });
  await expect(preview).toBeVisible();
  await expect(preview.getByRole("img", { name: asset.title })).toHaveAttribute("src", asset.url);
  await expect(preview.getByRole("link", { name: "Apri originale" })).toHaveAttribute("href", asset.url);
});

test("il selettore immagini usa miniature quadrate, scorrimento e azioni contestuali", async ({ page }) => {
  await page.goto("/tools/items");
  await page.getByRole("button", { name: "Crea oggetto" }).click();

  const editor = page.getByRole("dialog", { name: "Crea oggetto" });
  await editor.getByRole("button", { name: "Scegli dall'archivio" }).click();

  const picker = page.getByRole("dialog", { name: "Scegli un'immagine" });
  await picker.locator(".image-picker-filters").getByLabel("Categoria").selectOption("");

  const grid = picker.getByRole("list", { name: "Immagini disponibili" });
  const metrics = await grid.evaluate((element) => {
    const thumbnail = element.querySelector<HTMLImageElement>(".image-picker-card-trigger img");
    const rect = thumbnail?.getBoundingClientRect();
    return {
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
      overflowY: getComputedStyle(element).overflowY,
      thumbnailWidth: rect?.width || 0,
      thumbnailHeight: rect?.height || 0,
    };
  });
  expect(metrics.overflowY).toBe("auto");
  expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight);
  expect(metrics.thumbnailWidth).toBeGreaterThan(150);
  expect(Math.abs(metrics.thumbnailWidth - metrics.thumbnailHeight)).toBeLessThan(1);

  const triggers = grid.locator(".image-picker-card-trigger");
  test.skip(await triggers.count() === 0, "L'archivio non contiene immagini da selezionare.");
  const trigger = triggers.first();
  const triggerLabel = await trigger.getAttribute("aria-label");
  const assetTitle = triggerLabel?.replace("Azioni per ", "") || "";
  await trigger.click();

  const menu = picker.getByRole("menu", { name: triggerLabel || "" });
  await expect(menu.getByRole("menuitem", { name: "Apri" })).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: "Seleziona" })).toBeVisible();

  await menu.getByRole("menuitem", { name: "Apri" }).click();
  const preview = picker.getByRole("dialog", { name: `Anteprima ${assetTitle}` });
  await expect(preview.getByRole("img", { name: assetTitle })).toBeVisible();
  await preview.getByRole("button", { name: "Chiudi", exact: true }).click();

  await trigger.click();
  await picker.getByRole("menu", { name: triggerLabel || "" }).getByRole("menuitem", { name: "Seleziona" }).click();
  await expect(picker.locator(".image-picker-summary")).toContainText(`Selezionata: ${assetTitle}`);
  await expect(picker.getByRole("button", { name: "Usa immagine selezionata" })).toBeEnabled();
});
