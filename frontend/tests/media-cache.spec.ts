import { expect, test } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";


test("le impostazioni espongono il pacchetto media persistente della campagna", async ({ page }) => {
  const workerResponse = await page.request.get("/service-worker.js");
  expect(workerResponse.status()).toBe(200);
  expect(workerResponse.headers()["service-worker-allowed"]).toBe("/");
  expect(workerResponse.headers()["cache-control"]).toContain("no-cache");

  const manifestResponse = await page.request.get("/api/media/cache-manifest/");
  expect(manifestResponse.status()).toBe(200);
  const payload = await manifestResponse.json();
  expect(payload.data.scope).toMatch(/^user-\d+-campaign-\d+$/);
  expect(payload.data.entries.length).toBeGreaterThan(0);
  expect(payload.data.entries.some((entry: { kind: string }) => entry.kind === "static_media")).toBe(true);
  expect(payload.data.entries.every((entry: { url: string }) => /^\/(media|static\/frontend\/(images|audio|video|fonts))\//.test(entry.url))).toBe(true);

  await page.goto("/settings");
  await page.getByRole("tab", { name: "Media locali" }).click();

  await expect(page.getByRole("heading", { name: "Archivio locale della campagna" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Scarica tutti i media" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Importa pacchetto media ZIP" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Esporta pacchetto media ZIP" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Mantieni su questo dispositivo" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Svuota cache media locale" })).toBeEnabled();
  await expect(page.getByText("I contenuti a visibilità limitata non entrano mai nel pacchetto locale.")).toBeVisible();

  await page.getByRole("button", { name: "Scarica tutti i media" }).click();
  await expect(page.locator(".toast.success")).toContainText("Media della campagna", { timeout: 120_000 });
  const staticUrl = payload.data.entries.find((entry: { kind: string }) => entry.kind === "static_media").url;
  expect(await page.evaluate(async (url) => Boolean(await caches.match(url)), staticUrl)).toBe(true);
});


test("un pacchetto esportato viene verificato e importato atomicamente", async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Media locali" }).click();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Esporta pacchetto media ZIP" }).click(),
  ]);
  const archivePath = await download.path();
  expect(archivePath).toBeTruthy();

  await page.locator(".media-cache-import-input").setInputFiles(archivePath || "");
  await expect(page.locator(".toast.success")).toContainText("Pacchetto di", { timeout: 120_000 });
  await expect(page.getByText(/Aggiornamento completato: \d+ nuovi/)).toBeVisible();

  const cached = await page.evaluate(async () => {
    const response = await caches.match("/static/frontend/images/items/spadalunga.webp");
    const packageCaches = (await caches.keys()).filter((name) => name.includes("-package-"));
    return { hasItemIcon: Boolean(response), packageCaches };
  });
  expect(cached.hasItemIcon).toBe(true);
  expect(cached.packageCaches).toHaveLength(1);

  const corrupted = readFileSync(archivePath || "");
  corrupted[Math.floor(corrupted.length / 2)] ^= 0xff;
  const corruptedPath = testInfo.outputPath("pacchetto-corrotto.zip");
  writeFileSync(corruptedPath, corrupted);
  await page.locator(".media-cache-import-input").setInputFiles(corruptedPath);
  await expect(page.locator(".toast.error")).toBeVisible({ timeout: 120_000 });

  const cacheAfterFailure = await page.evaluate(async () => ({
    hasItemIcon: Boolean(await caches.match("/static/frontend/images/items/spadalunga.webp")),
    packageCaches: (await caches.keys()).filter((name) => name.includes("-package-")),
  }));
  expect(cacheAfterFailure.hasItemIcon).toBe(true);
  expect(cacheAfterFailure.packageCaches).toHaveLength(1);
});
