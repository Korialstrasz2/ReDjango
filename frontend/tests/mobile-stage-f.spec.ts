import { expect, test, type Page } from "@playwright/test";

import {
  applyAccessibilityProfile,
  auditVisibleTouchTargets,
  expectFixedChromeDoesNotCoverFocus,
  expectNoDocumentOverflow,
  isCompactProject,
  isPhoneProject,
  primaryHeading,
  type AccessibilityProfile,
} from "./helpers/stage-f";

const fixedPlayerRoutes = [
  "/",
  "/skills",
  "/competencies",
  "/creation",
  "/new-character",
  "/combat",
  "/travel",
  "/market",
  "/lore",
  "/media",
  "/guides",
  "/settings",
] as const;

async function resolveCharacterRoute(page: Page): Promise<string | null> {
  await page.goto("/");
  const characterLink = page.locator("a[href^='/character/']").first();
  if (!(await characterLink.count())) return null;
  return characterLink.getAttribute("href");
}

async function expectRouteShell(page: Page, projectName: string) {
  await expect(page.locator(".fatal-error")).toHaveCount(0);
  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(primaryHeading(page)).toBeVisible();
  if (isPhoneProject(projectName)) {
    await expect(page.locator(".mobile-app-bar")).toBeVisible();
    await expect(page.locator(".mobile-bottom-navigation")).toBeVisible();
  } else {
    await expect(page.locator(".side-nav")).toBeVisible();
  }
}

test("Stage F loads every player route without console errors, overflow, or covered actions", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name) && testInfo.project.name !== "desktop-1920", "Responsive and protected desktop matrix only");
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  const characterRoute = await resolveCharacterRoute(page);
  const routes = characterRoute ? [...fixedPlayerRoutes, characterRoute] : [...fixedPlayerRoutes];
  const routeDiagnostics: Array<{ path: string; title: string }> = [];

  for (const path of routes) {
    await page.goto(path);
    await page.waitForLoadState("domcontentloaded");
    await expectRouteShell(page, testInfo.project.name);
    await expectNoDocumentOverflow(page, testInfo, `stage-f-${testInfo.project.name}-${path}`);
    await expectFixedChromeDoesNotCoverFocus(page);
    routeDiagnostics.push({ path, title: await page.title() });
  }

  await testInfo.attach("stage-f-route-matrix.json", {
    body: JSON.stringify(routeDiagnostics, null, 2),
    contentType: "application/json",
  });
  expect(consoleErrors, consoleErrors.join("\n")).toEqual([]);
});

const fontScales: AccessibilityProfile["fontScale"][] = [75, 85, 100, 125, 150, 175];
const densities: AccessibilityProfile["density"][] = ["spacious", "comfortable", "compact", "condensed"];

test("Stage F exercises every supported font scale and density without compact-layout overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone-small-portrait", "Run the full accessibility-setting cross-product once");
  const characterRoute = await resolveCharacterRoute(page);
  const representativeRoutes = ["/", characterRoute || "/skills", "/settings", "/combat", "/travel"];
  const results: Array<AccessibilityProfile & { path: string }> = [];
  let index = 0;

  for (const fontScale of fontScales) {
    for (const density of densities) {
      const path = representativeRoutes[index % representativeRoutes.length];
      index += 1;
      await page.goto(path);
      await applyAccessibilityProfile(page, {
        fontScale,
        density,
        reducedMotion: index % 2 === 0,
      });
      await expect(primaryHeading(page)).toBeVisible();
      await expectNoDocumentOverflow(page, testInfo, `a11y-${fontScale}-${density}-${path}`);
      results.push({ fontScale, density, reducedMotion: index % 2 === 0, path });
    }
  }

  await testInfo.attach("accessibility-profile-matrix.json", {
    body: JSON.stringify(results, null, 2),
    contentType: "application/json",
  });
});

test("Stage F records phone touch-target evidence for every player destination", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone-large-portrait", "Run one deliberate phone touch-target audit");
  const characterRoute = await resolveCharacterRoute(page);
  const routes = characterRoute ? [...fixedPlayerRoutes, characterRoute] : [...fixedPlayerRoutes];
  const undersized: Array<{ path: string; label: string; width: number; height: number; className: string }> = [];

  for (const path of routes) {
    await page.goto(path);
    await expect(primaryHeading(page)).toBeVisible();
    const audit = await auditVisibleTouchTargets(page, testInfo, `touch-${path}`);
    undersized.push(...audit.filter((entry) => entry.tooSmall).map((entry) => ({
      path,
      label: entry.label,
      width: entry.width,
      height: entry.height,
      className: entry.className,
    })));
  }

  await testInfo.attach("undersized-touch-targets.json", {
    body: JSON.stringify(undersized, null, 2),
    contentType: "application/json",
  });
  // This is an evidence-producing audit. Known inline text links may be smaller than 44px;
  // critical navigation, modal, tab, and icon controls are asserted in their focused suites.
});
