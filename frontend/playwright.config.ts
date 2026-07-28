import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:8128",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "authenticated",
      testIgnore: /auth\.setup\.ts/,
      dependencies: ["setup"],
      use: { storageState: ".playwright/auth.json" },
    },
  ],
  webServer: {
    command: "..\\venv\\Scripts\\python.exe ..\\manage.py migrate --noinput && ..\\venv\\Scripts\\python.exe ..\\manage.py flush --noinput && ..\\venv\\Scripts\\python.exe ..\\manage.py seed_minimum_data && ..\\venv\\Scripts\\python.exe ..\\manage.py ensure_admin_login && ..\\venv\\Scripts\\python.exe ..\\manage.py runserver 127.0.0.1:8128 --noreload",
    env: {
      REDJANGO_ACCESS_MODE: "locked",
      REDJANGO_DATABASE_NAME: "frontend/e2e.sqlite3",
      REDJANGO_ADMIN_USERNAME: "local_master",
      REDJANGO_ADMIN_PASSWORD: "ReDjango-E2E-only-2026!",
      REDJANGO_ADMIN_GAME_ROLE: "admin",
    },
    url: "http://127.0.0.1:8128/api/auth/session/",
    reuseExistingServer: false,
    timeout: 120000
  }
});
