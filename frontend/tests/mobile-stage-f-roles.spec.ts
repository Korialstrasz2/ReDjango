import { expect, test } from "@playwright/test";

import { expectNoDocumentOverflow, primaryHeading } from "./helpers/stage-f";

type SettingsEnvelope = {
  data: { security: { canManageGameData: boolean; canManageAdminSettings: boolean } };
};

const roleProjects = new Set(["phone-combat-master", "phone-combat-player"]);

test("Stage F preserves player and Master route permissions across the phone shell", async ({ page, request }, testInfo) => {
  test.skip(!roleProjects.has(testInfo.project.name), "Independent player/Master phone sessions only");
  const settingsResponse = await request.get("/api/settings/");
  expect(settingsResponse.ok()).toBeTruthy();
  const settings = await settingsResponse.json() as SettingsEnvelope;
  const isMaster = testInfo.project.name.endsWith("master");
  const expectedRole = isMaster ? "master" : "user";
  expect(settings.data.security.canManageGameData).toBe(isMaster);
  expect(settings.data.security.canManageAdminSettings).toBe(false);

  await page.goto("/");
  await expect(page.locator(".mobile-app-bar")).toBeVisible();
  await page.getByRole("button", { name: /Altro/ }).click();
  const more = page.getByRole("dialog", { name: "Navigazione" });
  await expect(more).toBeVisible();
  if (isMaster) {
    await expect(more.getByText("Gestione da schermo più grande")).toBeVisible();
  } else {
    await expect(more.getByText("Gestione da schermo più grande")).toHaveCount(0);
  }
  await more.getByRole("button", { name: "Chiudi" }).click();

  await page.goto("/tools");
  if (isMaster) {
    await expect(page).toHaveURL(/\/tools$/);
    await expect(page.getByRole("heading", { name: "Gestione richiede un tablet o un computer" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Indietro" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Torna alla Home" })).toBeVisible();
  } else {
    await expect(page).toHaveURL(/\/$/);
    await expect(primaryHeading(page)).toBeVisible();
  }
  await expectNoDocumentOverflow(page, testInfo, `role-${expectedRole}`);
});

test("Stage F role sessions retain player routes and Quick Tools without exposing hidden management UI", async ({ page }, testInfo) => {
  test.skip(!roleProjects.has(testInfo.project.name), "Independent player/Master phone sessions only");
  for (const path of ["/skills", "/competencies", "/combat", "/travel"] as const) {
    await page.goto(path);
    await expect(primaryHeading(page)).toBeVisible();
    await expect(page.locator(".mobile-bottom-navigation")).toBeVisible();
    await expect(page.locator(".side-nav")).toBeHidden();
    await expectNoDocumentOverflow(page, testInfo, `${testInfo.project.name}-${path}`);
  }

  await page.getByRole("button", { name: "Apri strumenti rapidi" }).click();
  const tools = page.getByRole("dialog", { name: "Strumenti rapidi" });
  await expect(tools.getByRole("button", { name: "Diario", exact: true })).toBeVisible();
  await expect(tools.getByRole("button", { name: "Dadi", exact: true })).toBeVisible();
  await expect(tools.getByRole("button", { name: "Audio", exact: true })).toBeVisible();
});
