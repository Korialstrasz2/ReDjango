import { expect, test } from "@playwright/test";

import { expectNoDocumentOverflow, isTabletProject } from "./helpers/stage-f";

const managementRoutes = [
  "/tools",
  "/tools/characters",
  "/tools/items",
  "/tools/skills",
  "/tools/units",
  "/tools/shops",
  "/tools/dungeon",
  "/tools/ai",
  "/tools/master-ai",
  "/tools/players",
  "/tools/backups",
  "/tools/dice",
  "/tools/themes",
  "/tools/variables",
  "/tools/variables/damage",
] as const;

test("tablet management routes mount at the supported minimum width without phone fallback", async ({ page }, testInfo) => {
  test.skip(!isTabletProject(testInfo.project.name), "Tablet management matrix only");
  const evidence: Array<{ path: string; heading: string }> = [];

  for (const path of managementRoutes) {
    await page.goto(path);
    await expect(page).toHaveURL(new RegExp(`${path.replaceAll("/", "\\/")}$`));
    await expect(page.locator(".mobile-unsupported-management")).toHaveCount(0);
    await expect(page.locator(".side-nav")).toBeVisible();
    const heading = page.getByRole("heading", { level: 1 }).first();
    await expect(heading).toBeVisible();
    await expectNoDocumentOverflow(page, testInfo, `${testInfo.project.name}-${path}`);
    evidence.push({ path, heading: (await heading.textContent())?.trim() || "" });
  }

  await testInfo.attach(`tablet-management-${testInfo.project.name}.json`, {
    body: JSON.stringify(evidence, null, 2),
    contentType: "application/json",
  });
});

test("tablet management keeps keyboard focus visible at the bottom of dense pages", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "tablet-minimum", "Minimum-width tablet focus audit");

  for (const path of ["/tools/items", "/tools/variables", "/tools/themes"] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    const focusable = page.locator("main button:not([disabled]), main a[href], main input:not([disabled]), main select:not([disabled]), main textarea:not([disabled])");
    const count = await focusable.count();
    expect(count).toBeGreaterThan(0);
    const last = focusable.nth(count - 1);
    await last.scrollIntoViewIfNeeded();
    await last.focus();
    await expect(last).toBeFocused();
    const rect = await last.boundingBox();
    expect(rect?.top || 0).toBeGreaterThanOrEqual(0);
    expect(rect?.bottom || 0).toBeLessThanOrEqual((page.viewportSize()?.height || 0) + 1);
  }
});
