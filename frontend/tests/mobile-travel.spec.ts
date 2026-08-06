import { expect, test, type Page } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");
const isDesktopProject = (name: string) => name === "authenticated" || name === "desktop-1920";

async function openTravel(page: Page) {
  await page.goto("/travel");
  await expect(page.locator(".travel-page")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".fatal-error")).toHaveCount(0);
}

test("phone Travel is map-first and opens controls without remounting the workspace", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Travel workspace contract");
  await openTravel(page);

  const toolbar = page.locator(".travel-mobile-toolbar");
  await expect(toolbar).toBeVisible();
  await expect(page.getByRole("button", { name: "Indietro da Viaggio" })).toBeVisible();
  const sidebar = page.locator(".travel-sidebar");
  await expect(sidebar).toBeHidden();

  const canvas = page.locator(".travel-canvas");
  if (await canvas.count()) {
    await expect(canvas).toHaveAttribute("data-mobile-travel-touch-ready", "true");
    const panelBox = await page.locator(".travel-canvas-panel").boundingBox();
    expect(panelBox?.height || 0).toBeGreaterThanOrEqual(350);
  }

  await toolbar.getByRole("button", { name: "Controlli" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-mobile-travel-controls-open", "true");
  await expect(sidebar).toBeVisible();
  await expect(sidebar).toHaveAttribute("role", "dialog");
  await expect(sidebar).toHaveCSS("position", "fixed");

  await page.getByRole("button", { name: "← Mappa" }).click();
  await expect(sidebar).toBeHidden();
  await expect(toolbar).toBeVisible();
  expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);
});

test("phone Travel translates real touch pan and pinch gestures", async ({ context, page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Travel gesture contract");
  await openTravel(page);

  const canvas = page.locator(".travel-canvas");
  if (!await canvas.count()) test.skip(true, "Seed data has no Travel map canvas");
  await expect(canvas).toHaveAttribute("data-mobile-travel-touch-ready", "true");
  const box = await canvas.boundingBox();
  expect(box).toBeTruthy();
  const x = box!.x + box!.width * .45;
  const y = box!.y + box!.height * .55;
  const session = await context.newCDPSession(page);

  await session.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [{ x, y, radiusX: 2, radiusY: 2, force: 1, id: 1 }],
  });
  await session.send("Input.dispatchTouchEvent", {
    type: "touchMove",
    touchPoints: [{ x: x + 34, y: y + 20, radiusX: 2, radiusY: 2, force: 1, id: 1 }],
  });
  await expect(canvas).toHaveAttribute("data-mobile-travel-last-gesture", "pan");
  await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });

  await session.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [
      { x: x - 24, y, radiusX: 2, radiusY: 2, force: 1, id: 1 },
      { x: x + 24, y, radiusX: 2, radiusY: 2, force: 1, id: 2 },
    ],
  });
  await session.send("Input.dispatchTouchEvent", {
    type: "touchMove",
    touchPoints: [
      { x: x - 38, y: y - 4, radiusX: 2, radiusY: 2, force: 1, id: 1 },
      { x: x + 38, y: y + 4, radiusX: 2, radiusY: 2, force: 1, id: 2 },
    ],
  });
  await expect(canvas).toHaveAttribute("data-mobile-travel-last-gesture", "pinch");
  await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
});

test("phone Travel converts marker palette taps into explicit placement mode", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only marker placement contract");
  await openTravel(page);

  await page.locator(".travel-mobile-toolbar").getByRole("button", { name: "Controlli" }).click();
  const paletteButton = page.locator(".travel-marker-choice > button").first();
  await expect(paletteButton).toBeVisible();
  await paletteButton.click();

  const placement = page.getByRole("status");
  await expect(placement).toContainText("Tocca un esagono");
  await expect(page.locator(".travel-sidebar")).toBeHidden();
  await placement.getByRole("button", { name: "Annulla" }).click();
  await expect(placement).toHaveCount(0);
});


test("phone Travel Back closes controls and pending placement before leaving", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Travel Back contract");
  await openTravel(page);

  const back = page.getByRole("button", { name: "Indietro da Viaggio" });
  const toolbar = page.locator(".travel-mobile-toolbar");
  await toolbar.getByRole("button", { name: "Controlli" }).click();
  await expect(page.locator(".travel-sidebar")).toBeVisible();
  await back.click();
  await expect(page.locator(".travel-sidebar")).toBeHidden();
  await expect(page).toHaveURL(/\/travel$/);

  await back.click();
  await expect(page).toHaveURL(/\/$/);
});

test("desktop Travel retains the existing sidebar and two-column workspace", async ({ page }, testInfo) => {
  test.skip(!isDesktopProject(testInfo.project.name), "Protected desktop Travel contract");
  await openTravel(page);

  await expect(page.locator(".travel-mobile-toolbar")).toHaveCount(0);
  await expect(page.locator(".travel-sidebar")).toBeVisible();
  const columns = await page.locator(".travel-layout").evaluate((element) => getComputedStyle(element).gridTemplateColumns.trim().split(/\s+/).filter(Boolean));
  expect(columns.length).toBeGreaterThanOrEqual(2);
});
