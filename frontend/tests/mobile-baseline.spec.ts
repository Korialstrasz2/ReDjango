import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

test("captures the authenticated shell baseline for the configured viewport", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(page.locator(".fatal-error")).toHaveCount(0);

  const diagnostics = {
    project: testInfo.project.name,
    viewport: page.viewportSize(),
    touchPoints: await page.evaluate(() => navigator.maxTouchPoints),
    coarsePointer: await page.evaluate(() => window.matchMedia("(pointer: coarse)").matches),
    noHover: await page.evaluate(() => window.matchMedia("(hover: none)").matches),
    overflow: await measureDocumentOverflow(page),
  };

  await testInfo.attach("layout-diagnostics.json", {
    body: JSON.stringify(diagnostics, null, 2),
    contentType: "application/json",
  });
});
