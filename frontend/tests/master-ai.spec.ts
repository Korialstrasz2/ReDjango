import { expect, type Page, test } from "@playwright/test";

type ApiResult = { status: number; body: any };

async function api(
  page: Page,
  path: string,
  options: { method?: "GET" | "POST" | "PATCH" | "DELETE"; action?: string; payload?: Record<string, unknown> } = {},
): Promise<ApiResult> {
  return page.evaluate(async ({ path, method = "GET", action, payload = {} }) => {
    const csrfToken = document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith("csrftoken="))
      ?.slice("csrftoken=".length) || "";
    const requestId = `e2e-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const headers: Record<string, string> = {
      Accept: "application/json",
      "X-ReDjango-Client": "playwright-master-ai",
      "X-ReDjango-Request-Id": requestId,
    };
    let body: string | undefined;
    if (method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["X-CSRFToken"] = decodeURIComponent(csrfToken);
      if (action) headers["X-ReDjango-Action"] = action;
      body = JSON.stringify({
        action: action || "master-ai.e2e",
        requestId,
        context: { screen: "master-ai" },
        payload,
        meta: { clientVersion: "playwright" },
      });
    }
    const response = await fetch(path, { method, headers, body, credentials: "same-origin" });
    return { status: response.status, body: await response.json() };
  }, { path, ...options });
}

const searchItem = (page: Page, name: string) => api(page, `/api/ai/change-entities/item/search/?q=${encodeURIComponent(name)}&limit=10`);

async function createProposal(page: Page, title: string, itemName: string) {
  const created = await api(page, "/api/ai/change-sets/", {
    method: "POST",
    action: "ai.changeSet.create",
    payload: { title, requestText: `Crea ${itemName}`, context: { entityType: "item", sourceSurface: "master-ai" } },
  });
  expect(created.status).toBe(201);
  const changeSetId = created.body.data.changeSet.id as string;
  const operation = await api(page, `/api/ai/change-sets/${changeSetId}/operations/`, {
    method: "POST",
    action: "ai.changeOperation.add",
    payload: { entityType: "item", action: "create", values: { nome: itemName }, selected: true },
  });
  expect(operation.status).toBe(201);
  return changeSetId;
}

test("Master AI keeps proposal generation separate from human apply", async ({ page }) => {
  const suffix = Date.now().toString(36);
  const appliedName = `Lama E2E ${suffix}`;
  const discardedName = `Scarto E2E ${suffix}`;

  await page.goto("/");

  const changeSetId = await createProposal(page, `Applicazione ${suffix}`, appliedName);
  expect((await searchItem(page, appliedName)).body.data.results).toHaveLength(0);

  const validated = await api(page, `/api/ai/change-sets/${changeSetId}/validate/`, {
    method: "POST",
    action: "ai.changeSet.validate",
  });
  expect(validated.status).toBe(200);
  expect(validated.body.data.changeSet.status).toBe("ready");
  const token = validated.body.data.changeSet.validation.token as string;
  expect(token.length).toBeGreaterThan(20);

  const applied = await api(page, `/api/ai/change-sets/${changeSetId}/apply/`, {
    method: "POST",
    action: "ai.changeSet.apply",
    payload: { token },
  });
  expect(applied.status).toBe(200);
  expect(applied.body.data.changeSet.status).toBe("applied");
  const appliedSearch = await searchItem(page, appliedName);
  expect(appliedSearch.body.data.results.some((entry: { label: string }) => entry.label === appliedName)).toBe(true);

  const replay = await api(page, `/api/ai/change-sets/${changeSetId}/apply/`, {
    method: "POST",
    action: "ai.changeSet.apply",
    payload: { token },
  });
  expect(replay.status).toBe(409);

  const discardedSetId = await createProposal(page, `Scarto ${suffix}`, discardedName);
  const discarded = await api(page, `/api/ai/change-sets/${discardedSetId}/`, {
    method: "DELETE",
    action: "ai.changeSet.discard",
  });
  expect(discarded.status).toBe(200);
  expect(discarded.body.data.changeSet.status).toBe("discarded");
  expect((await searchItem(page, discardedName)).body.data.results).toHaveLength(0);

  let assistantPosts = 0;
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/api/ai/") assistantPosts += 1;
  });

  await page.goto("/tools/items");
  await page.getByLabel("Cerca").fill(appliedName);
  await expect(page.getByText(appliedName, { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Crea simile con AI" })).toBeVisible();
  await page.getByRole("button", { name: "Crea simile con AI" }).click();

  await expect(page).toHaveURL(/\/tools\/master-ai\?.*entity=item.*source=\d+.*surface=item-management/);
  await expect(page.getByRole("heading", { name: "Master AI" })).toBeVisible();
  await expect(page.locator(".master-ai-context-chip")).toContainText(appliedName);
  await expect(page.locator(".master-ai-chat textarea")).toHaveValue(new RegExp(`simile a .*${appliedName}`));
  expect(assistantPosts).toBe(0);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".master-ai-actionbar")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(2);

  await page.goto("/tools/themes");
  await expect(page.getByRole("button", { name: "AI Assist" })).toBeVisible();
  await page.goto("/tools/units");
  await expect(page.getByRole("button", { name: "AI Assist" })).toHaveCount(0);
});
