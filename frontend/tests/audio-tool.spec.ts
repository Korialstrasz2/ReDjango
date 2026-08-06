import { expect, test } from "@playwright/test";

/** A one-second silent 8-bit PCM mono WAV: small, valid and decodable by the browser. */
function silentWav(seconds = 1, sampleRate = 8000): Buffer {
  const samples = seconds * sampleRate;
  const buffer = Buffer.alloc(44 + samples, 128);
  buffer.write("RIFF", 0, "ascii");
  buffer.writeUInt32LE(36 + samples, 4);
  buffer.write("WAVE", 8, "ascii");
  buffer.write("fmt ", 12, "ascii");
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate, 28);
  buffer.writeUInt16LE(1, 32);
  buffer.writeUInt16LE(8, 34);
  buffer.write("data", 36, "ascii");
  buffer.writeUInt32LE(samples, 40);
  return buffer;
}

test("la colonna sonora si carica, si filtra e continua a suonare cambiando pagina", async ({ page }) => {
  await page.goto("/");

  const audioButton = page.getByRole("button", { name: /^Audio/ });
  await expect(audioButton).toBeVisible();
  await audioButton.click();

  const drawer = page.getByRole("dialog", { name: "Audio" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("La colonna sonora è ancora vuota.")).toBeVisible();

  // Carica due tracce con tag diversi, così il filtro ha qualcosa da separare.
  await drawer.getByRole("group", { name: "Tag della traccia" }).first().waitFor();
  const uploadPanel = drawer.locator(".audio-manager");
  await uploadPanel.getByText("Aggiungi una traccia").click();

  const uploadTrack = async (name: string, tag: string) => {
    await uploadPanel.getByLabel("File audio").setInputFiles({
      name: `${name}.wav`,
      mimeType: "audio/wav",
      buffer: silentWav(),
    });
    await uploadPanel.getByLabel("Nome").fill(name);
    const tags = uploadPanel.getByRole("group", { name: "Tag della traccia" });
    for (const active of await tags.locator("button[aria-pressed='true']").all()) await active.click();
    await tags.getByRole("button", { name: tag, exact: true }).click();
    await uploadPanel.getByRole("button", { name: "Carica traccia" }).click();
    await expect(drawer.locator(".audio-track-list li", { hasText: name })).toBeVisible();
  };

  await uploadTrack("Taverna del Cinghiale", "Taverna");
  await uploadTrack("Vento sulle rovine", "Ambient");
  await expect(drawer.locator(".audio-track-list li")).toHaveCount(2);

  // Ricerca testuale e filtro per tag riducono l'elenco.
  const search = drawer.getByPlaceholder("Cerca per nome o tag…");
  await search.fill("vento");
  await expect(drawer.locator(".audio-track-list li")).toHaveCount(1);
  await search.fill("");
  await drawer.locator(".audio-filters").getByRole("button", { name: "Taverna", exact: true }).click();
  await expect(drawer.locator(".audio-track-list li")).toHaveCount(1);
  await drawer.getByRole("button", { name: "Azzera filtri" }).click();
  await expect(drawer.locator(".audio-track-list li")).toHaveCount(2);

  // La riproduzione parte dall'elenco e accende il lettore in miniatura della barra.
  await drawer.getByRole("button", { name: "Riproduci Taverna del Cinghiale" }).click();
  const mini = page.locator(".quick-tools-bar").getByRole("group", { name: "Traccia in riproduzione" });
  await expect(mini).toBeVisible();
  await expect(mini.getByRole("button", { name: /^Taverna del Cinghiale/ })).toBeVisible();
  await expect(mini.getByRole("button", { name: "Metti in pausa" })).toBeVisible();
  await expect(page.locator("audio")).toHaveJSProperty("paused", false);

  await drawer.getByRole("button", { name: "Chiudi Audio" }).click();
  await expect(drawer).toHaveCount(0);
  await expect(mini).toBeVisible();

  // Il requisito centrale: cambiare pagina non interrompe la traccia.
  await page.getByRole("link", { name: "Combattimento", exact: true }).click();
  await expect(page).toHaveURL(/\/combat$/);
  await expect(mini).toBeVisible();
  await expect(page.locator("audio")).toHaveJSProperty("paused", false);

  // Il trasporto in miniatura passa alla traccia successiva e mette in pausa.
  await mini.getByRole("button", { name: "Traccia successiva" }).click();
  await expect(mini.getByRole("button", { name: /^Vento sulle rovine/ })).toBeVisible();
  await mini.getByRole("button", { name: "Metti in pausa" }).click();
  await expect(page.locator("audio")).toHaveJSProperty("paused", true);
  await expect(mini.getByRole("button", { name: "Riprendi" })).toBeVisible();

  // Interrompi libera la barra: la miniatura esiste solo quando c'è una traccia.
  await mini.getByRole("button", { name: "Interrompi la traccia" }).click();
  await expect(mini).toHaveCount(0);

  // Ripulisce la libreria condivisa lasciata dal test.
  await page.getByRole("button", { name: /^Audio/ }).click();
  const reopened = page.getByRole("dialog", { name: "Audio" });
  for (const title of ["Taverna del Cinghiale", "Vento sulle rovine"]) {
    page.once("dialog", (confirmation) => confirmation.accept());
    await reopened.getByRole("button", { name: `Modifica ${title}` }).click();
    await reopened.getByRole("button", { name: "Elimina" }).click();
    await expect(reopened.locator(".audio-track-list li", { hasText: title })).toHaveCount(0);
  }
  await expect(reopened.getByText("La colonna sonora è ancora vuota.")).toBeVisible();
});

test("la scorciatoia configurata apre il lettore audio", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Scorciatoie" }).click();
  await expect(page.locator('.setting-row:has-text("Audio rapido") output')).toHaveText("Alt + U");

  await page.getByRole("tab", { name: "Audio", exact: true }).click();
  await expect(page.locator('.setting-row:has-text("Volume della colonna sonora") input')).toHaveValue("60");

  await page.keyboard.press("Alt+U");
  await expect(page.getByRole("dialog", { name: "Audio" })).toBeVisible();
  await page.getByRole("button", { name: "Chiudi Audio" }).press("Escape");
  await expect(page.getByRole("dialog", { name: "Audio" })).toHaveCount(0);
});
