import { expect, test, type APIRequestContext } from "@playwright/test";

async function loreCommand(request: APIRequestContext, action: string, payload: Record<string, unknown>, requestId: string) {
  const csrfToken = (await request.storageState()).cookies.find((cookie) => cookie.name === "csrftoken")?.value || "";
  const response = await request.post("/api/v1/actions", {
    headers: { "X-CSRFToken": csrfToken },
    data: { action, requestId, context: { screen: "lore" }, payload, meta: { clientVersion: "playwright" } },
  });
  const body = await response.json();
  expect(response.ok(), JSON.stringify(body)).toBe(true);
  return body;
}

test("Timeline resta dentro Lore e presenta gli eventi in ordine", async ({ page, request }) => {
  const runId = Date.now();
  const mediaResponse = await request.get("/api/media/");
  const media = await mediaResponse.json();
  const imageId = media.data.assets[0]?.id ?? null;
  const createdIds: number[] = [];

  try {
    for (const event of [
      { title: `Rivolta E2E ${runId}`, year: -20, description: "Primo evento della verifica cronologica.", imageId, tags: ["E2E"] },
      { title: `Warp E2E ${runId}`, year: -10, description: "Evento senza immagine per verificare il fallback.", imageId: null, tags: ["E2E"] },
      { title: `Titus Mede E2E ${runId}`, year: 23, description: "Ultimo evento della verifica cronologica.", imageId: null, tags: ["E2E"] },
    ]) {
      const body = await loreCommand(request, "lore.timeline.save", { values: event }, `timeline-create-${runId}-${event.year}`);
      const created = body.data.lore.timelineEvents.find((entry: { title: string }) => entry.title === event.title);
      expect(created).toBeTruthy();
      createdIds.push(created.id);
    }

    await page.goto("/lore");
    const tabs = page.getByRole("tablist", { name: "Sezioni del lore" });
    await expect(tabs.getByRole("tab")).toHaveCount(3);
    await tabs.getByRole("tab", { name: "Timeline" }).click();

    const panel = page.getByRole("tabpanel", { name: "Timeline" });
    await expect(panel.getByRole("heading", { name: "Timeline" })).toBeVisible();
    const search = panel.getByRole("searchbox", { name: "Cerca nella cronologia" });
    await search.fill(String(runId));
    await expect(panel.locator(".lore-history-events > li")).toHaveCount(3);
    await expect(panel.getByText("3 eventi", { exact: true })).toBeVisible();

    const eventButtons = panel.locator(".lore-history-events button");
    await expect(eventButtons.nth(0)).toContainText(`Rivolta E2E ${runId}`);
    await expect(eventButtons.nth(1)).toContainText(`Warp E2E ${runId}`);
    await expect(eventButtons.nth(2)).toContainText(`Titus Mede E2E ${runId}`);
    if (imageId) await expect(eventButtons.first().locator("img")).toBeVisible();

    await eventButtons.nth(1).click();
    const inspector = panel.locator(".lore-timeline-inspector");
    await expect(inspector.getByRole("heading", { name: `Warp E2E ${runId}` })).toBeVisible();
    await expect(inspector).toHaveClass(/without-image/);
    await expect(inspector.getByText("10 anni prima di Dagoth")).toBeVisible();

    await search.fill("Titus Mede E2E");
    await expect(panel.locator(".lore-history-events > li")).toHaveCount(1);
    await expect(panel.getByText("1 evento", { exact: true })).toBeVisible();
    await expect(panel.getByRole("heading", { name: `Titus Mede E2E ${runId}` })).toBeVisible();
  } finally {
    for (const id of createdIds) {
      await loreCommand(request, "lore.timeline.archive", { id }, `timeline-archive-${runId}-${id}`);
    }
  }
});
