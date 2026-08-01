import { expect, test } from "@playwright/test";

test("l'assistente AI è un modale e la configurazione vive in Gestione AI", async ({ page }) => {
  await page.goto("/");

  const aiButton = page.getByRole("button", { name: /^AI/ });
  await expect(aiButton).toBeVisible();
  await aiButton.click();

  // È una finestra sovrapposta, non una pagina: l'URL non cambia.
  const modal = page.getByRole("dialog", { name: "AI" });
  await expect(modal).toBeVisible();
  await expect(page).toHaveURL(/\/$/);

  // Senza chiave configurata il modale lo dice e rimanda alla configurazione.
  await expect(modal.getByText("Nessun provider configurato")).toBeVisible();
  await modal.getByRole("link", { name: "Apri Gestione AI" }).click();
  await expect(page).toHaveURL(/\/tools\/ai$/);
  await expect(page.getByRole("heading", { name: "Gestione AI" })).toBeVisible();

  // La configurazione elenca i provider preconfigurati, chat e immagini separati.
  const list = page.getByRole("complementary", { name: "Provider configurati" });
  await expect(list.getByRole("button", { name: /Anthropic/ })).toBeVisible();
  await expect(list.getByRole("button", { name: /DeepSeek/ })).toBeVisible();
  await expect(list.getByRole("button", { name: /Immagini OpenAI/ })).toBeVisible();

  // Il campo chiave è di sola scrittura: non riespone mai un valore salvato.
  await list.getByRole("button", { name: /Anthropic/ }).click();
  const secret = page.getByLabel("Chiave API");
  await expect(secret).toHaveAttribute("type", "password");
  await expect(secret).toHaveValue("");

  await page.getByLabel("Modello").fill("claude-sonnet-5");
  await secret.fill("sk-finta-per-il-test");
  await page.getByRole("button", { name: "Salva", exact: true }).click();
  await expect(page.locator(".toast")).toContainText("aggiornato");
  // Dopo il salvataggio il campo torna vuoto e la scheda segnala solo la presenza.
  await expect(secret).toHaveValue("");
  await expect(list.getByRole("button", { name: /Anthropic/ })).toContainText("chiave presente");

  // Un indirizzo malformato viene rifiutato dal backend con un messaggio chiaro.
  await page.getByLabel("Indirizzo API").fill("api.anthropic.com");
  await page.getByRole("button", { name: "Salva", exact: true }).click();
  await expect(page.locator(".toast.error")).toContainText("http://");
});

test("la scorciatoia configurata apre l'assistente AI", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Scorciatoie" }).click();
  await expect(page.locator('.setting-row:has-text("Assistente AI") select')).toHaveValue("Alt+H");

  await page.getByRole("link", { name: "Impostazioni", exact: true }).press("Alt+H");
  await expect(page.getByRole("dialog", { name: "AI" })).toBeVisible();
  await page.getByRole("button", { name: "Chiudi AI" }).press("Escape");
  await expect(page.getByRole("dialog", { name: "AI" })).toHaveCount(0);
});

test("il modello si può scrivere, filtrare e scegliere dal catalogo completo", async ({ page }) => {
  await page.goto("/tools/ai");
  await page.getByRole("button", { name: "Provider", exact: true }).click();
  await page.getByRole("complementary", { name: "Provider configurati" }).getByRole("button", { name: /^OpenAI/ }).first().click();

  const model = page.getByRole("combobox", { name: "Modello" });
  await expect(model).toHaveAttribute("autocomplete", "off");
  await model.fill("gpt-4.1-");
  await expect(page.getByRole("listbox", { name: "Modelli disponibili" })).toBeVisible();
  await expect(page.getByRole("option", { name: "gpt-4.1-mini" })).toBeVisible();
  await expect(page.getByRole("option", { name: "gpt-5.1" })).toHaveCount(0);

  await model.fill("modello-personalizzato");
  await expect(page.getByText("Nessun modello corrispondente.")).toBeVisible();
  await page.getByRole("button", { name: "Mostra tutti i modelli" }).click();
  await expect(page.getByRole("option", { name: "gpt-5.1" })).toBeVisible();
  await page.getByRole("option", { name: "gpt-4.1-mini" }).click();
  await expect(model).toHaveValue("gpt-4.1-mini");

  await expect(page.getByLabel("Chiave API")).toHaveAttribute("autocomplete", "new-password");
});
