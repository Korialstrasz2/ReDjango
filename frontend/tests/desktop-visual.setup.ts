import { expect, test as setup } from "@playwright/test";
import { mkdirSync } from "node:fs";

setup("authenticate the canonical desktop visual account", async ({ request }) => {
  mkdirSync(".playwright", { recursive: true });
  await request.get("/api/auth/session/");
  const csrfToken = (await request.storageState()).cookies.find(
    (cookie) => cookie.name === "csrftoken",
  )?.value;
  expect(csrfToken).toBeTruthy();

  const response = await request.post("/api/auth/login/", {
    headers: { "X-CSRFToken": csrfToken || "" },
    data: {
      username: "local_master",
      password: "ReDjango-E2E-only-2026!",
    },
  });
  expect(response.ok()).toBeTruthy();
  expect((await response.json()).data.authenticated).toBe(true);
  await request.storageState({ path: ".playwright/auth.json" });
});
