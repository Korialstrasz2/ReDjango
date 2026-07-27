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
