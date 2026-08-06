import { expect, test, type Locator } from "@playwright/test";

import { measureDocumentOverflow } from "./helpers/layout";

const isPhoneProject = (name: string) => name.startsWith("phone-");

type ToolExpectation = {
  label: string;
  content: (drawer: Locator) => Locator;
};

const tools: ToolExpectation[] = [
  { label: "Diario", content: (drawer) => drawer.locator(".journal-sections, .journal-empty") },
  { label: "Dadi", content: (drawer) => drawer.locator(".dice-grid") },
  { label: "AI", content: (drawer) => drawer.locator(".ai-tool, .ai-empty, .form-error") },
  { label: "Audio", content: (drawer) => drawer.locator(".audio-tool, .form-error") },
  { label: "Furto", content: (drawer) => drawer.getByRole("tablist", { name: "Tipo di prova" }) },
  { label: "Nomi", content: (drawer) => drawer.locator(".name-tool, .name-empty, .form-error") },
];

test("phone Quick Tools expose every internal workspace as a contained full-screen drawer", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Quick Tools contract");
  await page.goto("/");

  const launcher = page.getByRole("button", { name: "Apri strumenti rapidi" });
  await expect(launcher).toBeVisible();

  for (const tool of tools) {
    await launcher.click();
    const chooser = page.getByRole("dialog", { name: "Strumenti rapidi" });
    await expect(chooser).toBeVisible();
    await chooser.getByRole("button", { name: tool.label, exact: true }).click();

    const drawer = page.getByRole("dialog", { name: tool.label, exact: true });
    await expect(drawer).toBeVisible();
    await expect(drawer).toHaveAttribute("data-responsive-presentation", "fullscreen");
    await expect(tool.content(drawer).first()).toBeVisible();

    const close = drawer.getByRole("button", { name: `Chiudi ${tool.label}` });
    await expect(close).toBeFocused();
    const box = await drawer.boundingBox();
    const viewport = page.viewportSize()!;
    expect(box?.width || 0).toBeGreaterThanOrEqual(viewport.width - 2);
    expect(box?.height || 0).toBeGreaterThanOrEqual(viewport.height - 2);
    expect((await measureDocumentOverflow(page)).document).toBeLessThanOrEqual(1);

    await close.click();
    await expect(drawer).toHaveCount(0);
    await expect(launcher).toBeFocused();
  }
});

test("phone Quick Tools close before route navigation and do not leave a hidden workspace", async ({ page }, testInfo) => {
  test.skip(!isPhoneProject(testInfo.project.name), "Phone-only Quick Tools navigation contract");
  await page.goto("/");

  const launcher = page.getByRole("button", { name: "Apri strumenti rapidi" });
  await launcher.click();
  await page.getByRole("dialog", { name: "Strumenti rapidi" }).getByRole("button", { name: "Diario", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Diario", exact: true });
  await expect(drawer).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await page.getByRole("link", { name: /Abilità/ }).click();
  await expect(page).toHaveURL(/\/skills$/);
  await expect(page.locator(".tool-drawer")).toHaveCount(0);
});
