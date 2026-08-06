import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isTabletProject = (name: string) => name.startsWith("tablet-");
const isCompactProject = (name: string) => isPhoneProject(name) || isTabletProject(name);

test("compact Skills exposes touch navigation, XP editing, and search", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Skills contract");
  await page.goto("/skills");

  await expect(page.getByRole("heading", { level: 1, name: "Abilità" })).toBeVisible();
  const layout = page.locator(".skills-layout");
  const groupRail = page.locator(".skill-group-rail");
  await expect(layout).toBeVisible();
  await expect(groupRail).toBeVisible();
  await expect(groupRail.locator("button").first()).toBeVisible();

  const layoutColumns = await layout.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  if ((page.viewportSize()?.width || 0) <= 900) expect(layoutColumns).toHaveLength(1);
  expect((await groupRail.locator("button").first().boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);

  const xpRibbon = page.getByRole("button", { name: "Modifica Punti Esperienza disponibili" });
  if (await xpRibbon.count()) {
    await xpRibbon.click();
    const xpDialog = page.getByRole("dialog", { name: "Modifica Punti Esperienza" });
    await expect(xpDialog).toBeVisible();
    if (isPhoneProject(testInfo.project.name)) {
      await expect(xpDialog).toHaveAttribute("data-responsive-presentation", "sheet");
      const xpInput = xpDialog.locator("input[type='number']").first();
      await expect(xpInput).toBeVisible();
      expect(await xpInput.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(16);
    }
    await xpDialog.getByRole("button", { name: "Chiudi" }).click();
  }

  await groupRail.getByRole("button", { name: /Cerca Abilità/ }).click();
  const nameSearch = page.getByLabel("Nome dell'abilità");
  const cardSearch = page.getByLabel("Qualsiasi testo nella carta");
  await expect(nameSearch).toBeVisible();
  await expect(cardSearch).toBeVisible();
  if (isPhoneProject(testInfo.project.name)) {
    expect(await nameSearch.evaluate((element) => Number.parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(16);
    expect((await page.getByRole("button", { name: "Azzera filtri" }).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Skills cards and details remain readable and touch-safe", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Skills contract");
  await page.goto("/skills");

  const familyTabs = page.locator(".skill-family-nav");
  if (await familyTabs.count()) {
    await expect(familyTabs.locator("button").first()).toBeVisible();
    expect((await familyTabs.locator("button").first().boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
  }

  const grid = page.locator(".skill-card-grid");
  await expect(grid).toBeVisible();
  const cards = grid.locator(".skill-card");
  if (await cards.count()) {
    if (isPhoneProject(testInfo.project.name)) {
      const columns = await grid.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
      expect(columns).toHaveLength(1);
    }

    const dragHandle = cards.first().locator(".skill-drag-handle");
    if (await dragHandle.count() && isPhoneProject(testInfo.project.name)) {
      const box = await dragHandle.boundingBox();
      expect(box?.width || 0).toBeGreaterThanOrEqual(44);
      expect(box?.height || 0).toBeGreaterThanOrEqual(44);
      await expect(dragHandle).toHaveCSS("touch-action", "none");
    }

    await cards.first().click();
    const detailDialog = page.locator(".rd-modal").filter({ has: page.locator(".skill-detail-card") });
    await expect(detailDialog).toBeVisible();
    if (isPhoneProject(testInfo.project.name)) {
      await expect(detailDialog).toHaveAttribute("data-responsive-presentation", "fullscreen");
      const facts = detailDialog.locator(".skill-document-facts");
      if (await facts.count()) {
        const factColumns = await facts.evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
        expect(factColumns).toHaveLength(1);
      }
    }
    await detailDialog.getByRole("button", { name: "Chiudi" }).click();
  } else {
    await expect(page.locator(".skill-empty-catalog")).toBeVisible();
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});
