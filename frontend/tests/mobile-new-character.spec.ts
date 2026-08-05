import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isTabletProject = (name: string) => name.startsWith("tablet-");
const isCompactProject = (name: string) => isPhoneProject(name) || isTabletProject(name);

test("compact New Character exposes validation and reachable actions", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet New Character contract");
  await page.goto("/new-character");

  const tabs = page.getByRole("navigation", { name: "Passi della creazione" });
  const actions = page.locator(".new-pg-actions");
  await expect(tabs).toBeVisible();
  await expect(page.locator(".new-pg-step")).toBeVisible();
  await expect(actions).toBeVisible();

  await actions.getByRole("button", { name: "Avanti" }).click();
  const issues = page.locator(".new-pg-page > .form-error");
  await expect(issues).toBeVisible();
  await expect(issues).toContainText("Serve un nome");
  await expect(issues).toContainText("Serve un'età");
  await expect(issues).toContainText("Scegli il sesso");

  if (isPhoneProject(testInfo.project.name)) {
    const stepButtons = tabs.getByRole("button");
    for (let index = 0; index < await stepButtons.count(); index += 1) {
      expect((await stepButtons.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
    const actionButtons = actions.getByRole("button");
    for (let index = 0; index < await actionButtons.count(); index += 1) {
      expect((await actionButtons.nth(index).boundingBox())?.height || 0).toBeGreaterThanOrEqual(44);
    }
  }

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("compact New Character preserves a draft across all four steps", async ({ page }, testInfo) => {
  test.skip(!isCompactProject(testInfo.project.name), "Phone and tablet New Character contract");
  await page.goto("/new-character");

  const draftName = `Mobile Draft ${testInfo.project.name}`;
  const actions = page.locator(".new-pg-actions");
  const tabs = page.getByRole("navigation", { name: "Passi della creazione" });

  await page.getByLabel("Nome").fill(draftName);
  await page.getByLabel("Età").fill("27");
  await page.getByLabel("Sesso").selectOption({ index: 1 });
  await actions.getByRole("button", { name: "Avanti" }).click();
  await expect(page.getByRole("heading", { name: "Razza e sottorazza" })).toBeVisible();

  const raceButtons = page.locator(".new-pg-race-grid button");
  expect(await raceButtons.count()).toBeGreaterThan(0);
  let selectedRace = raceButtons.first();
  for (let index = 0; index < await raceButtons.count(); index += 1) {
    const text = (await raceButtons.nth(index).innerText()).trim().toLocaleLowerCase("it-IT");
    if (!text.includes("altro")) {
      selectedRace = raceButtons.nth(index);
      break;
    }
  }
  await selectedRace.click();

  const subrace = page.locator(".new-pg-subrace select");
  if (await subrace.count()) await subrace.selectOption({ index: 1 });
  await actions.getByRole("button", { name: "Avanti" }).click();
  await expect(page.getByRole("heading", { name: "Caratteristica preferita" })).toBeVisible();

  const characteristics = page.locator(".new-pg-characteristic-grid button");
  expect(await characteristics.count()).toBeGreaterThan(0);
  await characteristics.first().click();
  await actions.getByRole("button", { name: "Avanti" }).click();
  await expect(page.getByRole("heading", { name: "Riepilogo" })).toBeVisible();
  await expect(page.locator(".new-pg-summary")).toContainText(draftName);
  await expect(actions.getByRole("button", { name: "Crea il personaggio" })).toBeVisible();

  await tabs.getByRole("button", { name: /Identità/ }).click();
  await expect(page.getByLabel("Nome")).toHaveValue(draftName);
  await expect(page.getByLabel("Età")).toHaveValue("27");
  await expect(page.getByLabel("Sesso")).not.toHaveValue("");

  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});
