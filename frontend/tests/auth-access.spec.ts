import { expect, test } from "@playwright/test";


test("un visitatore anonimo vede soltanto il login e può accedere", async ({ context, page }) => {
  await context.clearCookies();
  await page.goto("/");

  await expect(page).toHaveURL(/\/login\/\?next=\//);
  await expect(page.getByRole("heading", { name: "ReDjango" })).toBeVisible();
  await page.getByLabel("Nome utente").fill("local_master");
  await page.getByLabel("Password").fill("ReDjango-E2E-only-2026!");
  await page.getByRole("button", { name: "Accedi" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("navigation", { name: "Menu principale" })).toBeVisible();
});

test("la pagina iniziale mostra l'alias del giocatore e ospita personaggi e uscita", async ({ page, request }) => {
  const settingsResponse = await request.get("/api/settings/");
  expect(settingsResponse.ok()).toBeTruthy();
  const settings = await settingsResponse.json();
  const displayName = settings.data.giocatore.displayName;

  await page.goto("/");

  await expect(page.getByRole("heading", { name: displayName, exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Personaggi della campagna" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Esci", exact: true })).toBeVisible();

  const navigation = page.getByRole("navigation", { name: "Menu principale" });
  await expect(navigation.getByRole("link", { name: "Personaggi", exact: true })).toHaveCount(0);
  await expect(navigation.getByRole("button", { name: "Esci", exact: true })).toHaveCount(0);

  await page.goto("/settings");
  await expect(page.getByRole("button", { name: "Esci", exact: true })).toHaveCount(0);

  await page.goto("/characters");
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Personaggi della campagna" })).toBeVisible();
});


test("il cambio della modalità di accesso chiede il riavvio prima di salvare", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Amministrazione" }).click();
  await page.getByRole("combobox", { name: /Modalità di accesso/ }).selectOption("lan");
  await page.getByRole("button", { name: "Salva impostazioni" }).click();

  const dialog = page.getByRole("dialog", { name: "Riavvio necessario" });
  await expect(dialog).toContainText(
    "Cambiare questa impostazione richiede il riavvio del server. Riavviare?",
  );
  await dialog.getByRole("button", { name: "Annulla" }).click();
  await expect(dialog).toHaveCount(0);
});
