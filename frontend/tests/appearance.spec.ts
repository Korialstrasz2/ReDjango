import { expect, test } from "@playwright/test";

test("il bordo di contrasto è globale, automatico e non sostituisce gli effetti esistenti", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("tab", { name: "Sessione" }).click();
  await expect(page.getByRole("heading", { name: "Campagna attiva" })).toBeVisible();
  await expect(page.locator(".campaign-settings-panel select")).toBeVisible();

  await page.getByRole("tab", { name: "Accessibilità" }).click();
  const outline = page.getByRole("combobox", { name: /Bordo di contrasto del testo/ });
  await outline.selectOption("soft");
  await expect(page.locator("html")).toHaveAttribute("data-text-outline", "soft");
  await expect.poll(async () => page.evaluate(() => getComputedStyle(document.querySelector("h1")!).getPropertyValue("-webkit-text-stroke-width"))).toBe("0.38px");

  await outline.selectOption("strong");
  await expect(page.locator("html")).toHaveAttribute("data-text-outline", "strong");
  const awareOutline = page.getByRole("checkbox", { name: /Contrasto adattivo al colore del testo/ });
  await awareOutline.check();
  await expect(page.locator("html")).toHaveAttribute("data-text-outline-aware", "true");
  await page.evaluate(() => {
    const lightText = document.createElement("span");
    lightText.id = "future-light-contrast-text";
    lightText.textContent = "Testo chiaro di una pagina futura";
    lightText.style.color = "rgb(245, 239, 255)";
    lightText.style.textShadow = "rgb(255, 0, 0) 1px 2px 3px";
    document.body.append(lightText);

    const darkText = document.createElement("span");
    darkText.id = "future-dark-contrast-text";
    darkText.textContent = "Testo scuro di una pagina futura";
    darkText.style.color = "rgb(41, 29, 21)";
    document.body.append(darkText);
  });

  await expect.poll(async () => page.evaluate(() => getComputedStyle(document.querySelector("#future-light-contrast-text")!).getPropertyValue("-webkit-text-stroke-color"))).toBe("rgb(0, 0, 0)");
  await expect.poll(async () => page.evaluate(() => getComputedStyle(document.querySelector("#future-dark-contrast-text")!).getPropertyValue("-webkit-text-stroke-color"))).toBe("rgb(255, 255, 255)");
  const finalMetrics = await page.evaluate(() => {
    const lightText = getComputedStyle(document.querySelector("#future-light-contrast-text")!);
    const root = getComputedStyle(document.documentElement);
    const heading = getComputedStyle(document.querySelector("h1")!);
    const control = getComputedStyle(document.querySelector('input[type="checkbox"]')!);
    return {
      outlineColor: root.getPropertyValue("--text-outline-color").trim(),
      futureStrokeWidth: lightText.getPropertyValue("-webkit-text-stroke-width"),
      futureStrokeColor: lightText.getPropertyValue("-webkit-text-stroke-color"),
      futureShadow: lightText.textShadow,
      headingStrokeWidth: heading.getPropertyValue("-webkit-text-stroke-width"),
      controlStrokeWidth: control.getPropertyValue("-webkit-text-stroke-width"),
    };
  });

  expect(["#000000", "#ffffff"]).toContain(finalMetrics.outlineColor);
  expect(finalMetrics.futureStrokeWidth).toBe("0.55px");
  expect(finalMetrics.futureStrokeColor).toBe("rgb(0, 0, 0)");
  expect(finalMetrics.futureShadow).toContain("rgb(255, 0, 0)");
  expect(finalMetrics.headingStrokeWidth).toBe("0.55px");
  expect(finalMetrics.controlStrokeWidth).toBe("0.55px");
});
