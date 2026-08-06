import { expect, test } from "@playwright/test";

import { expectNoDocumentOverflow, isPhoneProject } from "./helpers/stage-f";

const failedEnvelope = (message: string) => ({
  ok: false,
  requestId: "stage-f-failure",
  data: null,
  events: [],
  warnings: [],
  errors: [{ code: "stage_f.injected_failure", message }],
});

test("phone loading state uses the dynamic viewport and recovers when bootstrap completes", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only global loading contract");
  let releaseBootstrap!: () => void;
  const bootstrapGate = new Promise<void>((resolve) => { releaseBootstrap = resolve; });

  await page.route("**/api/bootstrap/", async (route) => {
    await bootstrapGate;
    await route.continue();
  });

  await page.goto("/");
  const loading = page.locator(".loading-screen");
  await expect(loading).toBeVisible();
  const metrics = await loading.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      top: rect.top,
      bottom: rect.bottom,
      height: rect.height,
      viewportHeight: document.documentElement.clientHeight,
      bodyOverflow: document.documentElement.scrollHeight - document.documentElement.clientHeight,
    };
  });
  expect(metrics.top).toBeGreaterThanOrEqual(-1);
  expect(metrics.bottom).toBeGreaterThanOrEqual(metrics.viewportHeight - 1);
  expect(metrics.bodyOverflow).toBeLessThanOrEqual(1);

  releaseBootstrap();
  await expect(page.locator(".app-shell")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
});

test("phone fatal startup error exposes a touch-sized retry and reconnects cleanly", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only fatal/reconnect contract");
  let failing = true;

  await page.route("**/api/media/", async (route) => {
    if (!failing) {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify(failedEnvelope("Archivio temporaneamente non raggiungibile.")),
    });
  });

  await page.goto("/");
  const fatal = page.locator(".fatal-error");
  await expect(fatal).toBeVisible({ timeout: 20_000 });
  await expect(fatal.getByRole("heading", { name: "ReDjango non può avviarsi" })).toBeVisible();
  await expect(fatal).toContainText("Archivio temporaneamente non raggiungibile.");
  const retry = fatal.getByRole("button", { name: "Riprova" });
  const retryBox = await retry.boundingBox();
  expect(retryBox?.width || 0).toBeGreaterThanOrEqual(44);
  expect(retryBox?.height || 0).toBeGreaterThanOrEqual(44);
  await expectNoDocumentOverflow(page, testInfo, "fatal-startup");

  failing = false;
  await retry.click();
  await expect(page.locator(".app-shell")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator(".fatal-error")).toHaveCount(0);
});

test("phone error toast stays above fixed navigation and inside the viewport", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only toast placement contract");
  await page.route("**/api/v1/actions", async (route) => {
    const request = route.request();
    const payload = request.postDataJSON() as { action?: string } | null;
    if (payload?.action !== "dice.roll") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify(failedEnvelope("Tiro di prova non disponibile.")),
    });
  });

  await page.goto("/");
  const launcher = page.getByRole("button", { name: "Apri strumenti rapidi" });
  await launcher.click();
  await page.getByRole("dialog", { name: "Strumenti rapidi" }).getByRole("button", { name: "Dadi", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Dadi", exact: true });
  const die = drawer.locator("button[aria-label^='Tira d']").first();
  await expect(die).toBeVisible();
  await die.click();

  const toast = page.locator(".toast.error");
  await expect(toast).toContainText("Tiro di prova non disponibile.");
  const geometry = await toast.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const navigation = document.querySelector<HTMLElement>(".mobile-bottom-navigation")?.getBoundingClientRect();
    return {
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      left: rect.left,
      viewportWidth: document.documentElement.clientWidth,
      viewportHeight: document.documentElement.clientHeight,
      navigationTop: navigation?.top ?? document.documentElement.clientHeight,
    };
  });
  expect(geometry.left).toBeGreaterThanOrEqual(0);
  expect(geometry.right).toBeLessThanOrEqual(geometry.viewportWidth + 1);
  expect(geometry.top).toBeGreaterThanOrEqual(0);
  expect(geometry.bottom).toBeLessThanOrEqual(geometry.navigationTop + 1);
  await expectNoDocumentOverflow(page, testInfo, "toast-placement");
});
