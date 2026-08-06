import { expect, test, type Page } from "@playwright/test";

const STATIC_ROUTES = [
  ["dashboard", "/"],
  ["skills", "/skills"],
  ["competencies", "/competencies"],
  ["creation", "/creation"],
  ["new-character", "/new-character"],
  ["combat", "/combat"],
  ["travel", "/travel"],
  ["market", "/market"],
  ["lore", "/lore"],
  ["media", "/media"],
  ["guides", "/guides"],
  ["settings", "/settings"],
  ["management", "/tools"],
] as const;

async function stabilize(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.addStyleTag({ content: `
    *, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }
    .toast { display: none !important; }
  ` });
  await page.evaluate(() => {
    document.documentElement.dataset.reducedMotion = "true";
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(120);
}

async function screenshotRoute(page: Page, name: string, path: string) {
  await page.goto(path);
  await expect(page.locator(".fatal-error")).toHaveCount(0);
  await expect(page.locator(".workspace-content")).toBeVisible({ timeout: 20_000 });
  await stabilize(page);
  await expect(page).toHaveScreenshot(`route-${name}.png`, { fullPage: false });
}

for (const [name, path] of STATIC_ROUTES) {
  test(`desktop route baseline: ${name}`, async ({ page }) => {
    await screenshotRoute(page, name, path);
  });
}

test("desktop route baseline: active character", async ({ page }) => {
  await page.goto("/");
  const response = await page.request.get("/api/personaggi/");
  const body = await response.json();
  const characterId = body.data?.giocatore?.activePersonaggioId || body.data?.personaggi?.[0]?.id;
  test.skip(!characterId, "Seed data has no character");
  await screenshotRoute(page, "character", `/character/${characterId}`);
});

test("desktop settings tabs remain pixel-identical", async ({ page }) => {
  await page.goto("/settings");
  const tabs = page.getByRole("tablist", { name: "Sezioni delle impostazioni" }).getByRole("tab");
  const count = await tabs.count();
  for (let index = 0; index < count; index += 1) {
    await tabs.nth(index).click();
    await stabilize(page);
    await expect(page).toHaveScreenshot(`settings-tab-${index}.png`, { fullPage: false });
  }
});

test("desktop quick-tool drawers remain pixel-identical", async ({ page }) => {
  await page.goto("/");
  for (const label of ["Diario", "Dadi", "Audio"]) {
    await page.locator(".quick-tools-actions").getByRole("button", { name: new RegExp(label) }).click();
    const drawer = page.locator(".tool-drawer").last();
    await expect(drawer).toBeVisible();
    await stabilize(page);
    await expect(page).toHaveScreenshot(`tool-drawer-${label.toLocaleLowerCase("it")}.png`, { fullPage: false });
    await drawer.getByRole("button", { name: "Chiudi" }).click();
  }
});

test("desktop common content modals remain pixel-identical when seeded", async ({ page }) => {
  await page.goto("/media");
  const mediaOpen = page.locator(".media-asset-open").first();
  if (await mediaOpen.count()) {
    await mediaOpen.click();
    await expect(page.locator(".media-preview-modal")).toBeVisible();
    await stabilize(page);
    await expect(page).toHaveScreenshot("modal-media-preview.png", { fullPage: false });
    await page.locator(".media-preview-modal").getByRole("button", { name: "Chiudi" }).click();
  }

  await page.goto("/market");
  const marketItem = page.locator(".market-item-card").first();
  if (await marketItem.count()) {
    await marketItem.click();
    await expect(page.locator(".market-item-modal")).toBeVisible();
    await stabilize(page);
    await expect(page).toHaveScreenshot("modal-market-item.png", { fullPage: false });
  }
});

test("desktop density surfaces remain pixel-identical", async ({ page }) => {
  await page.goto("/");
  for (const density of ["spacious", "compact", "condensed"]) {
    await page.evaluate((value) => { document.documentElement.dataset.density = value; }, density);
    await stabilize(page);
    await expect(page).toHaveScreenshot(`dashboard-density-${density}.png`, { fullPage: false });
  }
});
