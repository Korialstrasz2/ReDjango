import { expect, test } from "@playwright/test";


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
  expect(payload.data.entries.every((entry: { url: string }) => entry.url.startsWith("/media/"))).toBe(true);

  await page.goto("/settings");
  await page.getByRole("tab", { name: "Media locali" }).click();

  await expect(page.getByRole("heading", { name: "Archivio locale della campagna" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Scarica media campagna" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Mantieni su questo dispositivo" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Svuota cache media locale" })).toBeEnabled();
  await expect(page.getByText("I contenuti a visibilità limitata non entrano mai nel pacchetto locale.")).toBeVisible();
});
