import { expect, test, type Page } from "@playwright/test";

type ThemeSettings = {
  data: {
    theme: {
      overlayOpacity: number;
      panelOpacity: number;
      backgrounds: Record<string, string>;
    };
  };
};

// Le superfici di pagina raggiungibili dal menu laterale, con la loro rotta.
const PAGE_ROUTES: Record<string, string> = {
  dashboard: "/",
  skills: "/skills",
  competencies: "/competencies",
  creation: "/creation",
  combat: "/combat",
  travel: "/travel",
  market: "/market",
  lore: "/lore",
  media: "/media",
  guide: "/guides",
  settings: "/settings",
};

async function readThemeSettings(request: import("@playwright/test").APIRequestContext): Promise<ThemeSettings> {
  return (await (await request.get("/api/settings/")).json()) as ThemeSettings;
}

/** Opacità del velo di pagina: .workspace::after usa `opacity: var(--overlay-opacity)`. */
function workspaceVeilOpacity(page: Page): Promise<number | null> {
  return page.evaluate(() => {
    const main = document.querySelector<HTMLElement>("main.workspace");
    return main ? Number(getComputedStyle(main, "::after").opacity) : null;
  });
}

function hasBackground(settings: ThemeSettings, key: string): boolean {
  return Boolean(settings.data.theme.backgrounds[key]);
}

test("una pagina con sfondo parte trasparente e raggiunge i valori del tema in 1,5s", async ({ page, request }) => {
  const settings = await readThemeSettings(request);
  test.skip(!hasBackground(settings, "dashboard"), "il tema attivo non veste la Sala principale");
  const target = settings.data.theme.overlayOpacity;

  await page.goto("/");
  await page.waitForSelector("main.workspace");

  const early = await workspaceVeilOpacity(page);
  expect(early).not.toBeNull();
  expect(early!).toBeLessThan(0.25);

  // Il testo resta pieno per tutta la rivelazione: si animano solo le trasparenze.
  const heading = page.locator(".dashboard-page h1").first();
  await expect(heading).toHaveCSS("opacity", "1");

  await page.waitForTimeout(1700);
  const settled = await workspaceVeilOpacity(page);
  expect(settled!).toBeGreaterThan(target * 0.85);
  expect(settled!).toBeLessThanOrEqual(1);
});

test("la navigazione tra pagine fa ripartire la rivelazione", async ({ page, request }) => {
  const settings = await readThemeSettings(request);
  const dressedRoutes = Object.entries(PAGE_ROUTES).filter(([surface]) => hasBackground(settings, surface));
  test.skip(dressedRoutes.length < 2, "il tema attivo veste meno di due pagine");
  const [surfaceA, routeA] = dressedRoutes[0];
  const [surfaceB, routeB] = dressedRoutes[1];
  const target = settings.data.theme.overlayOpacity;

  await page.goto(routeA);
  await page.waitForSelector("main.workspace");
  await page.waitForTimeout(1700);
  expect((await workspaceVeilOpacity(page))!).toBeGreaterThan(target * 0.85);

  // Navigazione SPA: clic sul link laterale, nessun ricaricamento del documento.
  const navLink = page.locator(".side-nav").getByRole("link", { name: new RegExp(`${surfaceToLabel(surfaceB)}`) });
  await navLink.click();
  await page.waitForSelector(`main.workspace[data-screen="${surfaceB}"]`);

  const restarted = await workspaceVeilOpacity(page);
  expect(restarted!).toBeLessThan(0.25);
  await page.waitForTimeout(1700);
  expect((await workspaceVeilOpacity(page))!).toBeGreaterThan(target * 0.85);
});

function surfaceToLabel(surface: string): string {
  const labels: Record<string, string> = {
    dashboard: "Menu",
    skills: "Abilità",
    competencies: "Competenze",
    creation: "Creazione",
    combat: "Combattimento",
    travel: "Viaggio",
    market: "Mercato",
    lore: "Lore",
    media: "Immagini",
    guide: "Guide",
    settings: "Impostazioni",
  };
  return labels[surface] || surface;
}

test("lo strumento rapido con sfondo si rivelano dal trasparente", async ({ page, request }) => {
  const settings = await readThemeSettings(request);
  test.skip(!hasBackground(settings, "journal"), "il tema attivo non veste il Diario");
  const target = settings.data.theme.overlayOpacity;

  await page.goto("/");
  await page.waitForSelector("main.workspace");
  await page.getByRole("button", { name: /^Diario/ }).click();
  const drawer = page.getByRole("dialog", { name: "Diario" });
  await expect(drawer).toBeVisible();

  const readDrawerAlpha = (): Promise<number | null> => drawer.evaluate((el) => {
    const color = getComputedStyle(el).backgroundColor;
    const rgba = color.match(/rgba?\(([^)]+)\)/);
    if (rgba) {
      const parts = rgba[1].split(/[ ,/]+/).map(Number);
      return parts.length > 3 ? parts[3] : null;
    }
    const srgb = color.match(/color\(srgb[^)]*? \/ ([\d.]+)\)/);
    return srgb ? Number(srgb[1]) : null;
  });

  const earlyAlpha = await readDrawerAlpha();
  expect(earlyAlpha).not.toBeNull();
  expect(earlyAlpha!).toBeLessThan(target * 0.3 + 0.05);

  await page.waitForTimeout(1700);
  const settledAlpha = await readDrawerAlpha();
  expect(settledAlpha!).toBeGreaterThan(target * 0.85);
});

test("la modale vestita riparte dal trasparente a ogni apertura", async ({ page, request }) => {
  const settings = await readThemeSettings(request);
  test.skip(!hasBackground(settings, "tools"), "il tema attivo non veste la superficie degli strumenti");
  const target = settings.data.theme.overlayOpacity;

  await page.goto("/tools/themes");
  await page.waitForSelector("main.workspace");
  await page.getByRole("button", { name: "Nuovo tema" }).click();
  const modal = page.locator(".rd-modal-dressed");
  await expect(modal).toBeVisible();

  const readBackdropAlpha = (): Promise<number | null> => page.evaluate(() => {
    const backdrop = document.querySelector<HTMLElement>(".modal-backdrop");
    if (!backdrop) return null;
    const color = getComputedStyle(backdrop).backgroundColor;
    const rgba = color.match(/rgba?\(([^)]+)\)/);
    if (rgba) {
      const parts = rgba[1].split(/[ ,/]+/).map(Number);
      return parts.length > 3 ? parts[3] : null;
    }
    const srgb = color.match(/color\(srgb[^)]*? \/ ([\d.]+)\)/);
    return srgb ? Number(srgb[1]) : null;
  });

  const earlyAlpha = await readBackdropAlpha();
  expect(earlyAlpha).not.toBeNull();
  expect(earlyAlpha!).toBeLessThan(0.25);

  await page.waitForTimeout(1700);
  const settledAlpha = await readBackdropAlpha();
  expect(settledAlpha!).toBeGreaterThan(target * 0.85);
});

test("una pagina senza sfondo mostra subito i valori del tema, senza animazione", async ({ page, request }) => {
  const settings = await readThemeSettings(request);
  const undressed = Object.entries(PAGE_ROUTES).find(([surface]) => !hasBackground(settings, surface));
  test.skip(!undressed, "il tema attivo veste tutte le pagine");
  const target = settings.data.theme.overlayOpacity;

  await page.goto(undressed![1]);
  await page.waitForSelector("main.workspace");

  await expect(page.locator("main.workspace")).not.toHaveClass(/theme-reveal-surface/);
  await page.waitForTimeout(300);
  const veil = await workspaceVeilOpacity(page);
  expect(veil!).toBeGreaterThan(target * 0.9);
});

test("con riduzione del movimento le trasparenze valgono subito il tema", async ({ page, request }) => {
  const settings = await readThemeSettings(request);
  test.skip(!hasBackground(settings, "dashboard"), "il tema attivo non veste la Sala principale");
  const target = settings.data.theme.overlayOpacity;

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.waitForSelector("main.workspace");
  await page.waitForTimeout(300);

  const veil = await workspaceVeilOpacity(page);
  expect(veil!).toBeGreaterThan(target * 0.9);
});
