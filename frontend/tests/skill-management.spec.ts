import { expect, test } from "@playwright/test";

test("Gestione Skill rende catalogo, struttura e revisione Elder controllabili", async ({ page }) => {
  await page.goto("/tools/skills");

  await expect(page.getByRole("heading", { name: "Gestione Skill", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Panoramica", exact: true })).toHaveAttribute("aria-selected", "true");
  const metrics = page.locator(".skill-management-metrics article");
  await expect(metrics).toHaveCount(5);
  for (const label of ["Skill attive", "Incantesimi", "Famiglie", "Gruppi", "Archiviate"]) {
    await expect(metrics.filter({ hasText: label })).toHaveCount(1);
  }
  await expect(page.getByRole("heading", { name: "Tutto il catalogo a colpo d'occhio", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Catalogo completo", exact: true }).click();
  await expect(page.locator(".skill-management-table-body > button").first()).toBeVisible();
  await expect(page.locator(".skill-management-inspector")).toBeVisible();
  await expect(page.getByRole("button", { name: "Modifica completa", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Gruppi e famiglie", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Gruppi di famiglie", exact: true })).toBeVisible();
  await expect(page.locator(".skill-group-manager > div > button").first()).toBeVisible();
  await expect(page.locator(".skill-family-management-grid > article").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Nuovo gruppo", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Nuova famiglia", exact: true })).toBeVisible();

  await page.getByRole("tab", { name: /Revisione Elder/ }).click();
  await expect(page.getByRole("heading", { name: "Revisione the_elder_django", exact: true })).toBeVisible();
  await expect(page.locator(".skill-review-list > button").first()).toBeVisible();
  await expect(page.locator(".skill-review-inspector > header h2")).toBeVisible();
  await expect(page.getByRole("button", { name: "Correggi proposta", exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Correggi proposta", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("Costo PE base", { exact: false })).toBeVisible();
  await expect(page.getByText("Effetti passivi", { exact: true })).toBeVisible();
  await expect(page.getByText("Azioni attive e promemoria", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Chiudi", exact: true }).click();
});
