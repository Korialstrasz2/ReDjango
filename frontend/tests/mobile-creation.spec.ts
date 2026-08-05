import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isTabletProject = (name: string) => name.startsWith("tablet-");
const isCompactProject = (name: string) => isPhoneProject(name) || isTabletProject(name);

test("compact Creation keeps alchemy selection and formula visible", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Creation contract");
  await page.goto("/creation");

  const tabs = page.getByRole("navigation", { name: "Banchi di creazione" });
  await expect(tabs).toBeVisible();
  await expect(tabs.getByRole("button", { name: /Alchimia/ })).toBeVisible();
  await expect(tabs.getByRole("button", { name: /Forgiatura/ })).toBeVisible();
  await expect(tabs.getByRole("button", { name: /Incantamento/ })).toBeVisible();

  const workspace = page.locator(".alchemy-workspace");
  await expect(workspace).toBeVisible();
  await expect(page.getByRole("table", { name: "Reagenti per colore e livello" })).toBeVisible();
  await expect(page.locator(".alchemy-slots")).toBeVisible();
  await expect(page.locator(".alchemy-formula-card")).toBeVisible();
  await expect(page.locator(".alchemy-brew-button")).toBeVisible();

  const availableReagent = page.locator(".alchemy-stock-row button:not([disabled])").first();
  if (await availableReagent.count()) {
    await availableReagent.click();
    await expect(page.locator(".alchemy-slot.filled").first()).toBeVisible();
    await expect(page.locator(".alchemy-formula-card")).toBeVisible();
  }

  if (isPhoneProject(testInfo.project.name)) {
    const tabButtons = tabs.getByRole("button");
    for (let index = 0; index < await tabButtons.count(); index += 1) {
      expect((await tabButtons.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
    expect((await page.locator(".alchemy-brew-button").boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact Creation switches Forge and Enchant without compressing their workbenches", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet Creation contract");
  await page.goto("/creation");

  const tabs = page.getByRole("navigation", { name: "Banchi di creazione" });
  await tabs.getByRole("button", { name: /Forgiatura/ }).click();
  const forgeBench = page.locator(".crafting-bench");
  await expect(forgeBench).toBeVisible();
  const forgeSubtabs = forgeBench.getByRole("navigation", { name: "Banchi di forgiatura" });
  await expect(forgeSubtabs).toBeVisible();
  await expect(forgeSubtabs.getByRole("button", { name: /^Fucina$/ })).toBeVisible();

  if (isPhoneProject(testInfo.project.name)) {
    const forgeButtons = forgeSubtabs.getByRole("button");
    for (let index = 0; index < await forgeButtons.count(); index += 1) {
      expect((await forgeButtons.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);

  await tabs.getByRole("button", { name: /Incantamento/ }).click();
  const enchantBench = page.locator(".crafting-bench");
  await expect(enchantBench).toBeVisible();
  const enchantSubtabs = enchantBench.getByRole("navigation", { name: "Banchi di incantamento" });
  await expect(enchantSubtabs).toBeVisible();
  await expect(enchantSubtabs.getByRole("button").first()).toBeVisible();

  if (isPhoneProject(testInfo.project.name)) {
    const enchantButtons = enchantSubtabs.getByRole("button");
    for (let index = 0; index < await enchantButtons.count(); index += 1) {
      expect((await enchantButtons.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});
