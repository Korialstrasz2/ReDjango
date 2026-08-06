import { expect, test } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";
import { primaryHeading } from "./helpers/stage-f";

const isPhoneProject = (name: string) => name.startsWith("phone-");

const secondaryRoutes = [
  ["Competenze", "/competencies"],
  ["Creazione", "/creation"],
  ["Viaggio", "/travel"],
  ["Mercato", "/market"],
  ["Lore", "/lore"],
  ["Immagini", "/media"],
  ["Guide", "/guides"],
  ["Impostazioni", "/settings"],
] as const;

test("phone More navigation reaches every secondary player route and preserves browser history", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only integrated navigation contract");
  await page.goto("/");

  for (const [label, path] of secondaryRoutes) {
    await page.getByRole("button", { name: /Altro/ }).click();
    const menu = page.getByRole("dialog", { name: "Navigazione" });
    await menu.getByRole("link", { name: label, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${path.replace("/", "\\/")}$`));
    await expect(menu).toHaveCount(0);
    await expect(primaryHeading(page)).toBeVisible();
    expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);

    await page.goBack();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("link", { name: /Home/ })).toHaveAttribute("aria-current", "page");
  }
});

test("phone primary destinations and New Character have predictable Back behavior", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only integrated history contract");
  await page.goto("/");

  const primary = page.getByRole("navigation", { name: "Navigazione principale" });
  for (const name of [/PG/, /Abilità/, /Combattimento/]) {
    const link = primary.getByRole("link", { name });
    await link.click();
    await expect(primaryHeading(page)).toBeVisible();
    expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
    await page.goBack();
    await expect(page).toHaveURL(/\/$/);
  }

  await page.getByRole("link", { name: "Nuovo PG" }).click();
  await expect(page).toHaveURL(/\/new-character$/);
  await expect(primaryHeading(page)).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
});
