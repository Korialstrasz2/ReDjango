import { expect, test } from "@playwright/test";

test("le competenze restano leggibili insieme e tirano dal server", async ({ page }) => {
  await page.goto("/competencies");

  await expect(page.getByRole("heading", { name: "Competenze", exact: true })).toHaveCount(0);
  await expect(page.locator(".competencies-hero")).toHaveCount(0);
  const atlas = page.getByRole("complementary", { name: "Tutte le competenze" });
  await expect(atlas.locator("[data-competence-key]")).toHaveCount(21);
  await expect(atlas.locator("[data-competence-key='scalare']")).toHaveAttribute("aria-pressed", "true");
  await expect(atlas.locator("[data-competence-key='scalare'] .competence-card-bars > span")).toHaveCount(3);
  await expect(page.locator(".competencies-resources")).toHaveCount(0);
  await expect(page.locator(".competence-extra-panel")).toHaveCount(0);
  await expect(atlas.locator("[data-competence-key='scalare'] .competence-card-copy")).toContainText("Scalare -");
  const initialBackdrop = await page.locator(".competencies-page").evaluate((element) => getComputedStyle(element).getPropertyValue("--competence-backdrop"));
  expect(initialBackdrop).toContain("/competencies/backgrounds/1.jpg");
  await expect.poll(() => page.locator(".competence-focus-main").evaluate((element) => getComputedStyle(element, "::before").backgroundImage)).toContain("/competencies/backgrounds/1.jpg");

  const normalLayout = await atlas.evaluate((element) => {
    const list = element.firstElementChild as HTMLElement;
    const firstCard = list.firstElementChild as HTMLElement;
    return {
      overflow: getComputedStyle(element).overflow,
      listOverflow: getComputedStyle(list).overflow,
      listHeight: list.getBoundingClientRect().height,
      listScrollHeight: list.scrollHeight,
      firstCardHeight: firstCard.getBoundingClientRect().height,
    };
  });
  expect(normalLayout.overflow).toBe("visible");
  expect(normalLayout.listOverflow).toBe("visible");
  expect(normalLayout.listScrollHeight).toBeLessThanOrEqual(normalLayout.listHeight + 1);
  expect(normalLayout.firstCardHeight).toBeLessThanOrEqual(60);

  await page.evaluate(() => {
    document.documentElement.style.fontSize = "150%";
    document.documentElement.dataset.fontScale = "large";
  });
  await expect(atlas.locator("[data-competence-key]")).toHaveCount(21);
  const largeFontLayout = await atlas.evaluate((element) => {
    const list = element.firstElementChild as HTMLElement;
    const clippedLabels = Array.from(list.querySelectorAll<HTMLElement>(".competence-card-copy strong")).filter(
      (label) => label.scrollHeight > label.clientHeight + 1,
    ).length;
    return { listHeight: list.getBoundingClientRect().height, listScrollHeight: list.scrollHeight, clippedLabels };
  });
  expect(largeFontLayout.listScrollHeight).toBeLessThanOrEqual(largeFontLayout.listHeight + 1);
  expect(largeFontLayout.clippedLabels).toBe(0);
  await page.evaluate(() => {
    document.documentElement.style.removeProperty("font-size");
    delete document.documentElement.dataset.fontScale;
  });

  await atlas.locator("[data-competence-key='percezione']").click();
  await expect.poll(() => page.locator(".competencies-page").evaluate((element) => getComputedStyle(element).getPropertyValue("--competence-backdrop"))).not.toBe(initialBackdrop);
  const detail = page.locator(".competence-detail");
  await expect(detail.locator(".competence-focus-main").getByRole("heading", { name: "Percezione", exact: true })).toBeVisible();
  await expect(detail.locator(".competence-track")).toHaveCount(3);
  await expect(detail.locator(".competence-rank-control")).toHaveCount(4);
  await expect(detail.getByText("Manuale permanente", { exact: true })).toHaveCount(0);
  await expect(detail.getByRole("tab", { name: "Attuale", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(detail.locator(".competence-thresholds li")).toHaveCount(0);

  await detail.getByRole("tab", { name: "Linee guida", exact: true }).click();
  await expect(detail.locator(".competence-thresholds li")).toHaveCount(6);
  await expect(detail.locator(".competence-track")).toHaveCount(0);

  await detail.getByRole("tab", { name: "Attuale", exact: true }).click();
  await expect(detail.locator(".competence-track")).toHaveCount(3);
  await expect(detail.locator(".competence-rank-control")).toHaveCount(4);

  const history = page.locator(".competence-history button");
  const priorHistoryCount = await history.count();
  await page.getByRole("button", { name: "Tira d6", exact: true }).click();
  await expect(page.getByText("Ultimo risultato", { exact: true })).toBeVisible();
  await expect(history).toHaveCount(Math.min(10, priorHistoryCount + 1));
  await expect(history.first()).toContainText("Percezione");

  await expect(page.getByRole("button", { name: "Note della pagina: Competenze", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Diario", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Diario" }).getByRole("button", { name: "Competenze", exact: true })).toBeVisible();
});

test("un tiro potenziato resta disponibile e avvisa prima di aumentare la stanchezza", async ({ page }) => {
  await page.route("**/api/v1/characters/*/competencies", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    const scalare = body.data.competencies.find((entry: { key: string }) => entry.key === "scalare");
    scalare.masteryRank = 3;
    body.data.character.energyCurrent = 0;
    await route.fulfill({ response, json: body });
  });
  await page.goto("/competencies");

  await page.getByRole("button", { name: /Impulso \+1/ }).click();
  const rollButton = page.locator(".competence-roll-button");
  await expect(rollButton).toBeEnabled();
  await expect(rollButton).toHaveAttribute("data-energy-overdraw", "true");

  let prompt = "";
  page.once("dialog", async (dialog) => {
    prompt = dialog.message();
    await dialog.dismiss();
  });
  await rollButton.click();
  await expect.poll(() => prompt).toBe("Usare Energia farà aumentare la stanchezza. Continuare?");
});
