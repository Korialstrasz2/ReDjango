import { expect, type Locator, type Page, type TestInfo } from "@playwright/test";

import { measureDocumentOverflow } from "./layout";

export type AccessibilityProfile = {
  fontScale: 75 | 85 | 100 | 125 | 150 | 175;
  density: "spacious" | "comfortable" | "compact" | "condensed";
  reducedMotion?: boolean;
};

export type RoutePerformanceSnapshot = {
  path: string;
  navigationMs: number;
  domContentLoadedMs: number;
  transferredBytes: number;
  decodedBodyBytes: number;
  resourceCount: number;
  largestResource: { name: string; bytes: number } | null;
  jsBytes: number;
  cssBytes: number;
  imageBytes: number;
  heapBytes: number | null;
};

export const isPhoneProject = (name: string) => name.startsWith("phone-");
export const isTabletProject = (name: string) => name.startsWith("tablet-");
export const isCompactProject = (name: string) => isPhoneProject(name) || isTabletProject(name);

export function primaryHeading(page: Page): Locator {
  const pathname = new URL(page.url()).pathname;
  const workspaceTitle = pathname.startsWith("/combat")
    ? "Combattimento"
    : pathname.startsWith("/travel")
      ? "Viaggio"
      : null;
  if (workspaceTitle) {
    return page.locator(".tablet-route-heading:visible, [role='banner'] strong:visible")
      .filter({ hasText: new RegExp(`^${workspaceTitle}$`) })
      .first();
  }
  return page.locator([
    "main h1",
    "main [role='heading'][aria-level='1']",
    "main h2",
    "[role='main'] h1",
    "[role='main'] h2",
  ].join(", ")).first();
}

export async function applyAccessibilityProfile(page: Page, profile: AccessibilityProfile) {
  await page.evaluate(({ fontScale, density, reducedMotion }) => {
    const root = document.documentElement;
    root.style.fontSize = `${fontScale}%`;
    root.dataset.fontScale = fontScale >= 150 ? "large" : fontScale <= 85 ? "small" : "normal";
    root.dataset.density = density;
    root.dataset.reducedMotion = reducedMotion ? "true" : "false";
  }, profile);
}

export async function expectNoDocumentOverflow(page: Page, testInfo: TestInfo, label: string) {
  const diagnostics = await measureDocumentOverflow(page);
  await testInfo.attach(`${label.replace(/[^a-z0-9-]+/gi, "-").toLowerCase()}-overflow.json`, {
    body: JSON.stringify(diagnostics, null, 2),
    contentType: "application/json",
  });
  expect(diagnostics.document, JSON.stringify(diagnostics.offenders, null, 2)).toBeLessThanOrEqual(1);
}

export async function auditVisibleTouchTargets(page: Page, testInfo: TestInfo, label: string) {
  const audit = await page.evaluate(() => {
    const candidates = Array.from(document.querySelectorAll<HTMLElement>(
      "button, a[href], input, select, textarea, summary, [role='button'], [role='tab']",
    ));
    return candidates
      .filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
      })
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const label = element.getAttribute("aria-label") || element.textContent?.trim().replace(/\s+/g, " ").slice(0, 80) || element.tagName;
        return {
          label,
          tag: element.tagName,
          className: typeof element.className === "string" ? element.className : "",
          width: Math.round(rect.width * 100) / 100,
          height: Math.round(rect.height * 100) / 100,
          tooSmall: rect.width < 44 || rect.height < 44,
        };
      });
  });
  await testInfo.attach(`${label.replace(/[^a-z0-9-]+/gi, "-").toLowerCase()}-touch-targets.json`, {
    body: JSON.stringify(audit, null, 2),
    contentType: "application/json",
  });
  return audit;
}

export async function expectFixedChromeDoesNotCoverFocus(page: Page) {
  const focusables = page.locator("main a[href], main button:not([disabled]), main input:not([disabled]), main select:not([disabled]), main textarea:not([disabled])");
  const count = await focusables.count();
  if (!count) return;
  const last = focusables.nth(count - 1);
  await last.scrollIntoViewIfNeeded();
  await last.focus();
  const result = await last.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const inset = 2;
    const points = [
      [rect.left + rect.width / 2, rect.top + rect.height / 2],
      [rect.left + inset, rect.top + inset],
      [rect.right - inset, rect.top + inset],
      [rect.left + inset, rect.bottom - inset],
      [rect.right - inset, rect.bottom - inset],
    ];
    const covering = Array.from(new Set(points.flatMap(([x, y]) => {
      const top = document.elementFromPoint(
        Math.max(0, Math.min(document.documentElement.clientWidth - 1, x)),
        Math.max(0, Math.min(document.documentElement.clientHeight - 1, y)),
      ) as HTMLElement | null;
      if (!top || top === element || element.contains(top) || top.contains(element)) return [];
      const fixed = top.closest<HTMLElement>("body *");
      if (!fixed) return [];
      const style = getComputedStyle(fixed);
      if (style.pointerEvents === "none") return [];
      return [typeof fixed.className === "string" && fixed.className ? fixed.className : fixed.tagName];
    })));
    return { rect: { top: rect.top, right: rect.right, bottom: rect.bottom, left: rect.left }, covering };
  });
  expect(result.covering, JSON.stringify(result, null, 2)).toEqual([]);
  await expect(last).toBeFocused();
}

export async function collectRoutePerformanceSnapshot(page: Page, path: string): Promise<RoutePerformanceSnapshot> {
  return page.evaluate((routePath) => {
    const navigation = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    const transferredBytes = resources.reduce((sum, entry) => sum + (entry.transferSize || 0), 0);
    const decodedBodyBytes = resources.reduce((sum, entry) => sum + (entry.decodedBodySize || 0), 0);
    const largest = [...resources].sort((a, b) => (b.transferSize || b.decodedBodySize) - (a.transferSize || a.decodedBodySize))[0];
    const bytesFor = (suffix: RegExp) => resources
      .filter((entry) => suffix.test(new URL(entry.name, location.href).pathname))
      .reduce((sum, entry) => sum + (entry.transferSize || entry.decodedBodySize || 0), 0);
    const memory = performance as Performance & { memory?: { usedJSHeapSize?: number } };
    return {
      path: routePath,
      navigationMs: navigation ? navigation.loadEventEnd - navigation.startTime : 0,
      domContentLoadedMs: navigation ? navigation.domContentLoadedEventEnd - navigation.startTime : 0,
      transferredBytes,
      decodedBodyBytes,
      resourceCount: resources.length,
      largestResource: largest ? { name: largest.name, bytes: largest.transferSize || largest.decodedBodySize || 0 } : null,
      jsBytes: bytesFor(/\.m?js$/i),
      cssBytes: bytesFor(/\.css$/i),
      imageBytes: bytesFor(/\.(?:avif|gif|jpe?g|png|svg|webp)$/i),
      heapBytes: typeof memory.memory?.usedJSHeapSize === "number" ? memory.memory.usedJSHeapSize : null,
    };
  }, path);
}
