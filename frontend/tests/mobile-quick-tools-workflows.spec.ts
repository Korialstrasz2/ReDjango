import { expect, test, type Locator, type Page } from "@playwright/test";

import { expectNoDocumentOverflow, isPhoneProject } from "./helpers/stage-f";

async function openTool(page: Page, label: string): Promise<Locator> {
  const launcher = page.getByRole("button", { name: "Apri strumenti rapidi" });
  await launcher.click();
  const chooser = page.getByRole("dialog", { name: "Strumenti rapidi" });
  await expect(chooser).toBeVisible();
  await chooser.getByRole("button", { name: label, exact: true }).click();
  const drawer = page.getByRole("dialog", { name: label, exact: true });
  await expect(drawer).toBeVisible();
  return drawer;
}

async function closeTool(drawer: Locator) {
  await drawer.getByRole("button", { name: /^Chiudi / }).click();
  await expect(drawer).toHaveCount(0);
}

function silentWav(seconds = 8, sampleRate = 8000): Buffer {
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

test("phone Journal edits autosave, survive closing, and expose special resources", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Journal workflow");
  await page.goto("/");
  let drawer = await openTool(page, "Diario");

  const appunti = drawer.getByRole("button", { name: "Appunti", exact: true });
  if (await appunti.isEnabled()) {
    await appunti.click();
    const editor = drawer.getByLabel("Note Appunti");
    const marker = `Stage F mobile ${Date.now()}`;
    await editor.fill(marker);
    await expect(drawer.getByText("Da salvare", { exact: true })).toBeVisible();
    await expect(drawer.getByText("Salvato", { exact: true })).toBeVisible({ timeout: 10_000 });
    await closeTool(drawer);

    drawer = await openTool(page, "Diario");
    await drawer.getByRole("button", { name: "Appunti", exact: true }).click();
    await expect(drawer.getByLabel("Note Appunti")).toHaveValue(marker);
  }

  const resources = drawer.getByRole("button", { name: "Risorse speciali", exact: true });
  if (await resources.isEnabled()) {
    await resources.click();
    const panel = drawer.locator(".campaign-special-resources");
    await expect(panel).toBeVisible();
    const create = panel.getByRole("button", { name: "Nuova risorsa" });
    await create.click();
    const editor = page.getByRole("dialog", { name: "Nuova risorsa speciale" });
    await expect(editor).toBeVisible();
    await expect(editor.getByLabel("Nome della risorsa")).toBeVisible();
    await editor.getByRole("button", { name: "Chiudi" }).click();
    await expect(editor).toHaveCount(0);
  }

  await expectNoDocumentOverflow(page, testInfo, "journal-workflow");
  await closeTool(drawer);
});

test("phone Dice performs a roll, records session history, and opens group history", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Dice workflow");
  await page.goto("/");
  const drawer = await openTool(page, "Dadi");
  const die = drawer.locator("button[aria-label^='Tira d']").first();
  await expect(die).toBeVisible();
  await die.click();
  const historyEntry = drawer.locator(".dice-history li").first();
  await expect(historyEntry).toBeVisible({ timeout: 15_000 });
  await expect(historyEntry.locator("strong")).not.toHaveText("");

  const groupHistory = drawer.getByRole("tab", { name: "Tiri del gruppo" });
  if (await groupHistory.count()) {
    await groupHistory.click();
    await expect(drawer.getByRole("tabpanel").filter({ hasText: "Ultimi 100 tiri" })).toBeVisible();
    await drawer.getByRole("tab", { name: "Tiro", exact: true }).click();
  }

  await drawer.getByRole("button", { name: "Pulisci" }).click();
  await expect(drawer.getByText("La cronaca dei tiri di questa sessione apparirà qui.")).toBeVisible();
  await expectNoDocumentOverflow(page, testInfo, "dice-workflow");
  await closeTool(drawer);
});

test("phone Theft recalculates lockpicking and pickpocket thresholds with touch controls", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Theft workflow");
  await page.goto("/");
  const drawer = await openTool(page, "Furto");
  const initial = await drawer.locator(".theft-total strong").textContent();

  await drawer.getByRole("tab", { name: /Borseggio/ }).click();
  const bases = drawer.locator(".theft-bases button");
  if ((await bases.count()) > 1) await bases.nth(1).click();
  const circumstance = drawer.locator(".theft-toggles input[type='checkbox']").first();
  if (await circumstance.count()) await circumstance.check();
  const diversion = drawer.locator(".theft-diversion button").filter({ hasText: "−2" });
  if (await diversion.count()) await diversion.click();
  await drawer.getByRole("button", { name: "Aumenta il modificatore manuale" }).click();

  await expect(drawer.locator(".theft-total strong")).not.toHaveText(initial || "");
  await expect(drawer.locator(".theft-competence")).toContainText("contro");
  await drawer.getByRole("button", { name: "Azzera circostanze" }).click();
  await expect(drawer.getByLabel("Modificatore manuale alla soglia")).toHaveValue("0");
  await expectNoDocumentOverflow(page, testInfo, "theft-workflow");
  await closeTool(drawer);
});

test("phone Names generates, rerolls, and exposes tap-reachable culture choices", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Names workflow");
  await page.goto("/");
  const drawer = await openTool(page, "Nomi");
  const races = drawer.locator(".name-cascade-races > li > button");
  test.skip((await races.count()) === 0, "The E2E database has no name catalog");

  await races.first().click();
  const generated = drawer.locator(".name-result strong");
  await expect(generated).toBeVisible({ timeout: 10_000 });
  const firstName = await generated.textContent();
  await drawer.getByRole("button", { name: "Tira di nuovo" }).click();
  await expect(generated).toBeVisible({ timeout: 10_000 });
  await expect(drawer.locator(".name-result")).toContainText(/\S+/);
  const cultureList = drawer.locator(".name-cascade-cultures");
  await expect(cultureList).toBeVisible();
  await expect(cultureList.locator("button").first()).toBeVisible();
  expect(firstName?.trim()).toBeTruthy();
  await expectNoDocumentOverflow(page, testInfo, "names-workflow");
  await closeTool(drawer);
});

test("phone AI submits or clearly reports unavailable chat without trapping the user", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only AI workflow");
  await page.goto("/");
  const drawer = await openTool(page, "AI");
  const chat = drawer.locator(".ai-chat");

  if (await chat.count()) {
    const question = `Stage F mobile probe ${Date.now()}`;
    await drawer.getByLabel("Domanda per l'assistente").fill(question);
    await drawer.getByRole("button", { name: "Chiedi" }).click();
    await expect(drawer.locator(".ai-bubble.user").filter({ hasText: question })).toBeVisible();
    const cancel = drawer.getByRole("button", { name: "Annulla", exact: true });
    if (await cancel.count()) await cancel.click();
    await expect.poll(async () => {
      return drawer.locator(".ai-bubble.assistant, .ai-bubble.pending, button:has-text('Riprova')").count();
    }, { timeout: 15_000 }).toBeGreaterThan(0);
  } else {
    await expect(drawer.locator(".ai-empty")).toBeVisible();
    await expect(drawer.getByText(/Chat non pronta|Serve almeno un agente/)).toBeVisible();
  }

  await expectNoDocumentOverflow(page, testInfo, "ai-workflow");
  await closeTool(drawer);
});

test("phone audio playback and mini-player controls survive route navigation", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only audio continuity workflow");
  const track = {
    id: 91001,
    title: "Traccia E2E continua",
    tags: ["musica"],
    tagLabels: ["Musica"],
    url: "/e2e-audio.wav",
    originalName: "e2e-audio.wav",
    mimeType: "audio/wav",
    sizeBytes: silentWav().byteLength,
    durationSeconds: 8,
    notes: "",
    createdAt: null,
  };
  await page.route("**/api/audio/tracks/", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ data: { tracks: [track], tags: [{ value: "musica", label: "Musica" }], canManage: true }, events: [] }),
    });
  });
  await page.route("**/e2e-audio.wav", async (route) => {
    await route.fulfill({ contentType: "audio/wav", body: silentWav() });
  });

  await page.goto("/");
  const drawer = await openTool(page, "Audio");
  await drawer.getByRole("button", { name: "Riproduci Traccia E2E continua" }).click();
  const miniPlayer = page.getByRole("group", { name: "Traccia in riproduzione" });
  await expect(miniPlayer).toBeVisible();
  await closeTool(drawer);

  await page.getByRole("link", { name: /Abilità/ }).click();
  await expect(page).toHaveURL(/\/skills$/);
  await expect(miniPlayer).toBeVisible();
  await expect(miniPlayer).toContainText("Traccia E2E continua");
  const controls = miniPlayer.getByRole("button");
  for (let index = 0; index < await controls.count(); index += 1) {
    const box = await controls.nth(index).boundingBox();
    expect(box?.height || 0).toBeGreaterThanOrEqual(44);
  }
  const playerBox = await miniPlayer.boundingBox();
  const navigationBox = await page.locator(".mobile-bottom-navigation").boundingBox();
  expect(playerBox?.y || 0).toBeLessThan(navigationBox?.y || Number.POSITIVE_INFINITY);
  await miniPlayer.getByRole("button", { name: "Interrompi la traccia" }).click();
  await expect(miniPlayer).toHaveCount(0);
});
