import { expect, test } from "@playwright/test";

test("il bordo di contrasto è globale, automatico e non sostituisce gli effetti esistenti", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Campagna attiva" })).toBeVisible();
  await expect(page.locator(".campaign-settings-panel select")).toBeVisible();

  const checkbox = page.getByRole("checkbox", { name: /Bordo di contrasto del testo/ });
  await checkbox.uncheck();
  await checkbox.check();

  await expect(page.locator("html")).toHaveAttribute("data-text-outline", "true");
  const metrics = await page.evaluate(() => {
    const futureText = document.createElement("span");
    futureText.id = "future-contrast-text";
    futureText.textContent = "Testo di una pagina futura";
    futureText.style.textShadow = "rgb(255, 0, 0) 1px 2px 3px";
    document.body.append(futureText);

    const root = getComputedStyle(document.documentElement);
    const future = getComputedStyle(futureText);
    const heading = getComputedStyle(document.querySelector("h1")!);
    const control = getComputedStyle(document.querySelector('input[type="checkbox"]')!);
    return {
      outlineColor: root.getPropertyValue("--text-outline-color").trim(),
      futureStrokeWidth: future.getPropertyValue("-webkit-text-stroke-width"),
      futureStrokeColor: future.getPropertyValue("-webkit-text-stroke-color"),
      futureShadow: future.textShadow,
      headingStrokeWidth: heading.getPropertyValue("-webkit-text-stroke-width"),
      controlStrokeWidth: control.getPropertyValue("-webkit-text-stroke-width"),
    };
  });

  expect(["#000000", "#ffffff"]).toContain(metrics.outlineColor);
  expect(metrics.futureStrokeWidth).toBe("0.45px");
  expect(metrics.futureStrokeColor).not.toBe("");
  expect(metrics.futureShadow).toContain("rgb(255, 0, 0)");
  expect(metrics.headingStrokeWidth).toBe("0.45px");
  expect(metrics.controlStrokeWidth).toBe("0.45px");
});
