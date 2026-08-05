import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isTabletProject = (name: string) => name.startsWith("tablet-");
const isCompactProject = (name: string) => isPhoneProject(name) || isTabletProject(name);

test("compact Competencies keeps the index and selected detail continuous", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Competencies contract");
  await page.goto("/competencies");

  const workbench = page.locator(".competence-workbench");
  const index = page.getByLabel("Tutte le competenze");
  const detail = page.locator(".competence-detail");
  await expect(workbench).toBeVisible();
  await expect(index).toBeVisible();
  await expect(detail).toBeVisible();

  const columns = await workbench.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  if ((page.viewportSize()?.width || 0) <= 900) expect(columns).toHaveLength(1);

  const cards = index.locator(".competence-card");
  expect(await cards.count()).toBeGreaterThan(0);
  expect((await cards.first().boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);

  if (await cards.count() > 1) {
    const next = cards.nth(1);
    const key = await next.getAttribute("data-competence-key");
    await next.click();
    await expect(detail).toHaveAttribute("data-selected-competence", key || "");
    await expect(next).toHaveAttribute("aria-pressed", "true");
  }

  const summaryTabs = page.getByRole("tablist", { name: "Riepilogo della competenza" });
  await expect(summaryTabs.getByRole("tab", { name: "Attuale" })).toBeVisible();
  await summaryTabs.getByRole("tab", { name: "Linee guida" }).click();
  await expect(page.getByRole("tabpanel", { name: "Interpretazioni del risultato" })).toBeVisible();
  await summaryTabs.getByRole("tab", { name: "Attuale" }).click();

  if (isPhoneProject(testInfo.project.name)) {
    const rankControls = page.locator(".competence-rank-control");
    const count = await rankControls.count();
    for (let index = 0; index < count; index += 1) {
      const box = await rankControls.nth(index).boundingBox();
      expect(box?.width || 0).toBeGreaterThanOrEqual(44);
      expect(box?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Competencies preserves roll controls, mastery, and history", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Competencies contract");
  await page.goto("/competencies");

  const rollWorkspace = page.locator(".competence-roll-workspace");
  const techniqueButtons = page.locator(".competence-techniques button");
  const rollButton = page.locator(".competence-roll-button");
  await expect(rollWorkspace).toBeVisible();
  await expect(techniqueButtons.first()).toBeVisible();
  await expect(rollButton).toBeVisible();

  if (isPhoneProject(testInfo.project.name)) {
    expect((await rollButton.boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    const techniqueCount = await techniqueButtons.count();
    for (let index = 0; index < techniqueCount; index += 1) {
      expect((await techniqueButtons.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
    const workspaceBox = await rollWorkspace.boundingBox();
    expect(workspaceBox?.width || 0).toBeLessThanOrEqual((page.viewportSize()?.width || 0) + 1);
  }

  const mastery = page.getByLabel("Gradi di maestria");
  const history = page.locator(".competence-history");
  await expect(mastery).toBeVisible();
  await expect(mastery.locator("li").first()).toBeVisible();
  await expect(history).toBeVisible();

  const historyTabs = page.getByRole("tablist", { name: "Cronologia dei tiri" });
  if (await historyTabs.count()) {
    await expect(historyTabs.getByRole("tab", { name: "Personaggio" })).toBeVisible();
    if (isPhoneProject(testInfo.project.name)) {
      expect((await historyTabs.getByRole("tab", { name: "Personaggio" }).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});
