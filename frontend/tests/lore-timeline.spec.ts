import { expect, test } from "@playwright/test";

test("Timeline resta dentro Lore e presenta gli eventi migrati in ordine", async ({ page }) => {
  await page.goto("/lore");

  const tabs = page.getByRole("tablist", { name: "Sezioni del lore" });
  await expect(tabs.getByRole("tab")).toHaveCount(3);
  await tabs.getByRole("tab", { name: "Timeline" }).click();

  const panel = page.getByRole("tabpanel", { name: "Timeline" });
  await expect(panel.getByRole("heading", { name: "Timeline" })).toBeVisible();
  await expect(panel.locator(".lore-history-events > li")).toHaveCount(14);
  await expect(panel.getByText("14 eventi", { exact: true })).toBeVisible();

  const firstEvent = panel.locator(".lore-history-events button").first();
  await expect(firstEvent).toContainText("Rivolta degli Schiavi Argoniani");
  await expect(firstEvent.locator("img")).toBeVisible();

  await panel.locator(".lore-history-events button", { hasText: "Il Warp in the West" }).click();
  const inspector = panel.locator(".lore-timeline-inspector");
  await expect(inspector.getByRole("heading", { name: "Il Warp in the West" })).toBeVisible();
  await expect(inspector).toHaveClass(/without-image/);
  await expect(inspector.getByText("10 anni prima di Dagoth")).toBeVisible();

  await panel.getByRole("searchbox", { name: "Cerca nella cronologia" }).fill("Titus Mede");
  await expect(panel.locator(".lore-history-events > li")).toHaveCount(1);
  await expect(panel.getByText("1 evento", { exact: true })).toBeVisible();
  await expect(panel.getByRole("heading", { name: "Ascesa di Titus Mede I" })).toBeVisible();
});
