import { expect, test } from "@playwright/test";

import { expectNoDocumentOverflow, isPhoneProject } from "./helpers/stage-f";

const audioTrack = {
  id: 92001,
  title: "Traccia da eliminare",
  tags: ["musica"],
  tagLabels: ["Musica"],
  url: "/modal-audit-audio.wav",
  originalName: "modal-audit-audio.wav",
  mimeType: "audio/wav",
  sizeBytes: 512,
  durationSeconds: 4,
  notes: "",
  createdAt: null,
};

const envelope = <T,>(data: T, events: Array<{ type: string; message: string }> = []) => ({
  ok: true,
  requestId: "stage-f-modal-audit",
  data,
  events,
  warnings: [],
  errors: [],
});

test("phone audio deletion uses a blocking responsive dialog with focus restoration", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only modal contract");
  let deleted = false;
  await page.route("**/api/audio/tracks/", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(envelope({ tracks: deleted ? [] : [audioTrack], tags: [{ value: "musica", label: "Musica" }], canManage: true })),
    });
  });
  await page.route("**/api/audio/tracks/92001/", async (route) => {
    if (route.request().method() !== "DELETE") {
      await route.continue();
      return;
    }
    deleted = true;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(envelope({ tracks: [], tags: [{ value: "musica", label: "Musica" }], canManage: true }, [{ type: "success", message: "Traccia eliminata." }])),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Apri strumenti rapidi" }).click();
  await page.getByRole("dialog", { name: "Strumenti rapidi" }).getByRole("button", { name: "Audio", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Audio", exact: true });
  await drawer.getByRole("button", { name: "Modifica Traccia da eliminare" }).click();
  const deleteTrigger = drawer.getByRole("button", { name: "Elimina", exact: true });
  await deleteTrigger.click();

  let confirmation = page.getByRole("dialog", { name: "Elimina traccia" });
  await expect(confirmation).toBeVisible();
  await expect(confirmation).toHaveAttribute("data-responsive-presentation", "dialog");
  await expect(confirmation.getByRole("button", { name: "Annulla" })).toBeFocused();
  await expect(confirmation).toContainText("Questa operazione non può essere annullata.");

  const backdrop = confirmation.locator("xpath=..");
  await backdrop.dispatchEvent("mousedown");
  await expect(confirmation).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(confirmation).toHaveCount(0);
  await expect(deleteTrigger).toBeFocused();

  await deleteTrigger.click();
  confirmation = page.getByRole("dialog", { name: "Elimina traccia" });
  await confirmation.getByRole("button", { name: "Elimina definitivamente" }).click();
  await expect(confirmation).toHaveCount(0);
  await expect(drawer.getByText("La colonna sonora è ancora vuota.")).toBeVisible();
  await expect(page.locator(".mobile-toast-stack .toast.success")).toContainText("Traccia eliminata.");
  await expectNoDocumentOverflow(page, testInfo, "audio-delete-modal");
});

test("phone nested Journal resource editor remains contained and closes before its parent", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only nested overlay contract");
  await page.goto("/");
  await page.getByRole("button", { name: "Apri strumenti rapidi" }).click();
  await page.getByRole("dialog", { name: "Strumenti rapidi" }).getByRole("button", { name: "Diario", exact: true }).click();
  const journal = page.getByRole("dialog", { name: "Diario", exact: true });
  const resources = journal.getByRole("button", { name: "Risorse speciali", exact: true });
  test.skip(!(await resources.count()) || !(await resources.isEnabled()), "No campaign fixture available");
  await resources.click();
  await journal.getByRole("button", { name: "Nuova risorsa" }).click();

  const editor = page.getByRole("dialog", { name: "Nuova risorsa speciale" });
  await expect(editor).toBeVisible();
  const rect = await editor.boundingBox();
  const viewport = page.viewportSize()!;
  expect(rect?.x || 0).toBeGreaterThanOrEqual(0);
  expect((rect?.x || 0) + (rect?.width || 0)).toBeLessThanOrEqual(viewport.width + 1);
  expect((rect?.y || 0) + (rect?.height || 0)).toBeLessThanOrEqual(viewport.height + 1);
  await editor.getByLabel("Nome della risorsa").fill("Bozza Stage F non salvata");
  await editor.getByRole("button", { name: "Chiudi" }).click();
  await expect(editor).toHaveCount(0);
  await expect(journal).toBeVisible();
  await expectNoDocumentOverflow(page, testInfo, "nested-resource-editor");
});
