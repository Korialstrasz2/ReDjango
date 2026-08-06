import { expect, test, type Page } from "@playwright/test";

import { collectRoutePerformanceSnapshot } from "./helpers/stage-f";

const performanceProjects = new Set(["phone-large-portrait", "desktop-1920"]);
const routes = ["/", "/skills", "/combat", "/travel"] as const;

async function sampleAnimationFrames(page: Page, durationMs = 1200) {
  return page.evaluate((duration) => new Promise<{ frames: number; elapsedMs: number; fps: number }>((resolve) => {
    const started = performance.now();
    let frames = 0;
    const tick = (now: number) => {
      frames += 1;
      const elapsedMs = now - started;
      if (elapsedMs >= duration) {
        resolve({ frames, elapsedMs, fps: frames / (elapsedMs / 1000) });
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }), durationMs);
}

test("records startup, transfer, route, image, CSS, and memory budgets", async ({ page }, testInfo) => {
  test.skip(!performanceProjects.has(testInfo.project.name), "Dedicated phone and protected desktop performance evidence");
  const evidence: Array<Awaited<ReturnType<typeof collectRoutePerformanceSnapshot>> & { wallClockMs: number }> = [];

  for (const path of routes) {
    const started = Date.now();
    await page.goto(path);
    await page.getByRole("heading", { level: 1 }).first().waitFor({ state: "visible" });
    const wallClockMs = Date.now() - started;
    evidence.push({ ...(await collectRoutePerformanceSnapshot(page, path)), wallClockMs });
  }

  await testInfo.attach(`performance-${testInfo.project.name}.json`, {
    body: JSON.stringify(evidence, null, 2),
    contentType: "application/json",
  });

  for (const snapshot of evidence) {
    expect(snapshot.wallClockMs, `${snapshot.path} exceeded the catastrophic route budget`).toBeLessThan(15_000);
    expect(snapshot.navigationMs, `${snapshot.path} exceeded the navigation budget`).toBeLessThan(12_000);
    expect(snapshot.largestResource?.bytes || 0, `${snapshot.path} transferred an individual resource over 25 MB`).toBeLessThan(25 * 1024 * 1024);
  }

  const heapSamples = evidence.map((entry) => entry.heapBytes).filter((value): value is number => typeof value === "number");
  if (heapSamples.length > 1) {
    const growth = heapSamples.at(-1)! - heapSamples[0];
    expect(growth, "Heap grew by more than 160 MB across the route sequence").toBeLessThan(160 * 1024 * 1024);
  }
});

test("records Combat and Travel animation-frame budgets on phone", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "phone-large-portrait", "Phone map performance evidence");
  const evidence: Record<string, { frames: number; elapsedMs: number; fps: number }> = {};

  for (const path of ["/combat", "/travel"] as const) {
    await page.goto(path);
    await page.getByRole("heading", { level: 1 }).first().waitFor({ state: "visible" });
    evidence[path] = await sampleAnimationFrames(page);
    expect(evidence[path].fps, `${path} fell below the minimum interactive frame budget`).toBeGreaterThanOrEqual(15);
  }

  await testInfo.attach("phone-map-frame-rate.json", {
    body: JSON.stringify(evidence, null, 2),
    contentType: "application/json",
  });
});
