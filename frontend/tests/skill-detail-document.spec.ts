import { expect, test, type APIRequestContext } from "@playwright/test";

async function createSkill(request: APIRequestContext, values: Record<string, unknown>, requestId: string): Promise<number> {
  const csrfToken = (await request.storageState()).cookies.find((cookie) => cookie.name === "csrftoken")?.value || "";
  const response = await request.post("/api/v1/actions", {
    headers: { "X-CSRFToken": csrfToken },
    data: { action: "skills.create", requestId, payload: { values } },
  });
  const body = await response.json();
  expect(response.ok(), JSON.stringify(body)).toBe(true);
  return body.data.skill.id;
}

test("il documento abilità mostra i campi esistenti senza inventare regole", async ({ page, request }) => {
  const catalogResponse = await request.get("/api/v1/skills?character_id=1&search_mode=true");
  expect(catalogResponse.ok()).toBe(true);
  const catalog = (await catalogResponse.json()).data;
  const familyId = catalog.families.find((family: { name: string }) => family.name === "Misticismo")?.id || catalog.families[0].id;
  const prerequisiteSkillId = await createSkill(request, {
    name: "Test - Documento incantesimo", number: 990001, familyId, familyOrder: 0,
    magic: true, baseXpCost: 7, xpType: "blue", rulesCost: "3 Mana",
    description: "Un incantesimo usato per verificare il documento adattivo.", requirementsText: "", prerequisiteIds: [],
    spell: { tier: "base", range: "15 metri", effectUnit: "Danno", baseMana: 0, effectPerMana: 1, minimumMana: 0, fixedCosts: {}, rounding: "none", legacyFormula: "", costNotes: "", combatConfiguration: { prepared: true, spendsResources: false } },
    profileTags: { tipo: ["incantesimo"] }, profileNotes: "Controllo E2E", passiveEffects: [], activeReminders: [], icon: "runa", notes: "Nota magica visibile.", metadata: {},
  }, "skill-document-spell");
  await createSkill(request, {
    name: "Test - Triplo Missile", number: 990002, familyId, familyOrder: 1,
    magic: false, baseXpCost: 9999, xpType: "general", rulesCost: "3 Energia",
    description: "Scagli tre armi contro lo stesso bersaglio.", requirementsText: "Test - Documento incantesimo", prerequisiteIds: [prerequisiteSkillId], spell: null,
    profileTags: { tipo: ["attiva"] }, profileNotes: "", passiveEffects: [],
    activeReminders: [{ id: "triplo-missile", name: "Triplo Missile", description: "Scagli tre armi contro lo stesso bersaglio.", trigger: "", duration: "", usageNotes: "", costs: { energia: 3 }, icon: "runa" }],
    icon: "runa", notes: "Solo con armi a distanza. Non utilizzabile con armi da fuoco.", metadata: {},
  }, "skill-document-action");

  await page.goto("/skills");
  await page.getByRole("button", { name: /Cerca Abilità/ }).click();

  const nameSearch = page.getByRole("searchbox", { name: "Nome dell'abilità" });
  await nameSearch.fill("Test - Documento incantesimo");
  const spellCard = page.locator(".skill-card").filter({ has: page.getByRole("heading", { name: "Test - Documento incantesimo", exact: true }) });
  await expect(spellCard).toHaveCount(1);
  await spellCard.click();

  const spellDialog = page.getByRole("dialog", { name: "Test - Documento incantesimo" });
  await expect(spellDialog.locator(".modal-header").getByRole("heading", { name: "Test - Documento incantesimo", exact: true })).toBeVisible();
  await expect(spellDialog.locator(".skill-detail-heading").getByText("Test - Documento incantesimo", { exact: true })).toHaveCount(0);
  await expect(spellDialog.getByRole("heading", { name: "Calcola l'incantesimo", exact: true })).toBeVisible();
  await expect(spellDialog.getByRole("tab", { name: "Incantesimo", exact: true })).toHaveCount(0);
  await expect(spellDialog.getByRole("tab", { name: "Giocatore", exact: true })).toHaveAttribute("aria-selected", "true");
  await page.screenshot({ path: "test-results/skill-detail-document.png" });

  await spellDialog.getByRole("tab", { name: "Gestione", exact: true }).click();
  await expect(spellDialog.getByRole("heading", { name: "Profilo e classificazione", exact: true })).toBeVisible();
  await spellDialog.getByRole("button", { name: "Modifica abilità", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Nota visibile ai giocatori", exact: true })).toBeVisible();
  await spellDialog.getByRole("button", { name: "Chiudi", exact: true }).click();

  await nameSearch.fill("Test - Triplo Missile");
  const actionCard = page.locator(".skill-card").filter({ has: page.getByRole("heading", { name: "Test - Triplo Missile", exact: true }) });
  await expect(actionCard).toHaveCount(1);
  await actionCard.click();

  const actionDialog = page.getByRole("dialog", { name: "Test - Triplo Missile" });
  await expect(actionDialog.getByText("Test - Documento incantesimo", { exact: true })).toHaveCount(1);
  await expect(actionDialog.getByText("Requisiti", { exact: true })).toHaveCount(0);
  await expect(actionDialog.locator(".modal-footer").getByText("Avvertenze:", { exact: true })).toBeVisible();
  await expect(actionDialog.locator(".skill-player-document").getByText("Avvertenze:", { exact: true })).toHaveCount(0);
  await expect(actionDialog.getByText("Solo con armi a distanza. Non utilizzabile con armi da fuoco.", { exact: true })).toBeVisible();
  const actionSummary = actionDialog.locator(".skill-rule-disclosure summary").filter({ hasText: "Triplo Missile" });
  await expect(actionSummary).toHaveCount(1);
  await actionSummary.click();
  await expect(actionDialog.getByText("Innesco", { exact: true })).toHaveCount(0);
  await expect(actionDialog.getByText("Durata", { exact: true })).toHaveCount(0);
  await expect(actionDialog.getByText("Uso dichiarato dal giocatore", { exact: true })).toHaveCount(0);
  await expect(actionDialog.getByText("Istantanea", { exact: true })).toHaveCount(0);
  await page.screenshot({ path: "test-results/skill-detail-action.png" });
});
