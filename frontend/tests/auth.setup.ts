import { expect, test as setup, type APIRequestContext } from "@playwright/test";
import { mkdirSync } from "node:fs";


const PASSWORD = "ReDjango-Combat-E2E-2026!";
const ACCOUNTS = [
  { username: "local_master", password: "ReDjango-E2E-only-2026!", state: ".playwright/auth.json" },
  { username: "combat_e2e_master", password: PASSWORD, state: ".playwright/auth-combat-master.json" },
  { username: "combat_e2e_player", password: PASSWORD, state: ".playwright/auth-combat-player.json" },
] as const;


async function authenticate(request: APIRequestContext, username: string, password: string, state: string) {
  mkdirSync(".playwright", { recursive: true });
  await request.get("/api/auth/session/");
  const csrfToken = (await request.storageState()).cookies.find(
    (cookie) => cookie.name === "csrftoken",
  )?.value;
  expect(csrfToken).toBeTruthy();

  const response = await request.post("/api/auth/login/", {
    headers: { "X-CSRFToken": csrfToken || "" },
    data: { username, password },
  });
  expect(response.ok()).toBeTruthy();
  expect((await response.json()).data.authenticated).toBe(true);
  await request.storageState({ path: state });
}


for (const account of ACCOUNTS) {
  setup(`authenticate ${account.username} against the isolated E2E database`, async ({ request }) => {
    await authenticate(request, account.username, account.password, account.state);
  });
}
