import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");

test("captures the authenticated shell baseline for the configured viewport", async ({ page }, testInfo) => {
  await page.goto("/");

  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect(page.locator(".fatal-error")).toHaveCount(0);

  if (isPhoneProject(testInfo.project.name)) {
    await expect(page.locator(".mobile-app-bar")).toBeVisible();
    await expect(page.locator(".mobile-bottom-navigation")).toBeVisible();
    await expect(page.locator(".side-nav")).toBeHidden();
  } else {
    await expect(page.locator(".side-nav")).toBeVisible();
    await expect(page.locator(".mobile-shell-chrome")).toHaveCount(0);
  }

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

test("phone shell exposes secondary destinations and quick tools", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only shell contract");
  await page.goto("/");

  const bottomNavigation = page.locator(".mobile-bottom-navigation");
  await expect(bottomNavigation.getByRole("link", { name: /Home/ })).toBeVisible();
  await expect(bottomNavigation.getByRole("link", { name: /PG/ })).toBeVisible();
  await expect(bottomNavigation.getByRole("link", { name: /Abilità/ })).toBeVisible();
  await expect(bottomNavigation.getByRole("link", { name: /Combattimento/ })).toBeVisible();

  await bottomNavigation.getByRole("button", { name: /Altro/ }).click();
  const navigationDialog = page.getByRole("dialog", { name: "Navigazione" });
  await expect(navigationDialog).toBeVisible();
  await expect(navigationDialog.getByRole("link", { name: /Impostazioni/ })).toBeVisible();
  await expect(navigationDialog.getByText("Gestione da schermo più grande")).toBeVisible();
  await navigationDialog.getByRole("button", { name: "Chiudi" }).click();

  await page.locator(".mobile-app-tools").click();
  const toolsDialog = page.getByRole("dialog", { name: "Strumenti rapidi" });
  await expect(toolsDialog.getByRole("button", { name: /Diario/ })).toBeVisible();
  await expect(toolsDialog.getByRole("button", { name: /Dadi/ })).toBeVisible();
  await expect(toolsDialog.getByRole("button", { name: /Audio/ })).toBeVisible();
});
