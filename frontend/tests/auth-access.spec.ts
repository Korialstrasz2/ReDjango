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
