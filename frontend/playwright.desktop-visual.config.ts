import { defineConfig } from "@playwright/test";

const runtimePlatform = (globalThis as typeof globalThis & { process?: { platform?: string } }).process?.platform || "";
const python = runtimePlatform.startsWith("win") ? "..\\venv\\Scripts\\python.exe" : "python";
const django = (command: string) => `${python} ../manage.py ${command}`;
const authenticatedState = ".playwright/desktop-visual-auth.json";

export default defineConfig({
  testDir: "./tests",
  testMatch: /desktop-visual-baseline\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      maxDiffPixels: 0,
    },
  },
  use: {
    baseURL: "http://127.0.0.1:8130",
    trace: "retain-on-failure",
    colorScheme: "dark",
  },
  projects: [
    {
      name: "desktop-visual-setup",
      testMatch: /auth\.setup\.ts/,
    },
    {
      name: "desktop-1280",
      dependencies: ["desktop-visual-setup"],
      use: { storageState: authenticatedState, viewport: { width: 1280, height: 800 } },
    },
    {
      name: "desktop-1440",
      dependencies: ["desktop-visual-setup"],
      use: { storageState: authenticatedState, viewport: { width: 1440, height: 900 } },
    },
    {
      name: "desktop-1920",
      dependencies: ["desktop-visual-setup"],
      use: { storageState: authenticatedState, viewport: { width: 1920, height: 1080 } },
    },
  ],
  webServer: {
    command: [
      django("migrate --noinput"),
      django("flush --noinput"),
      django("seed_minimum_data"),
      django("ensure_admin_login"),
      django("runserver 127.0.0.1:8130 --noreload"),
    ].join(" && "),
    env: {
      REDJANGO_ACCESS_MODE: "locked",
      REDJANGO_DATABASE_NAME: "frontend/e2e-desktop-visual.sqlite3",
      REDJANGO_ADMIN_USERNAME: "local_master",
      REDJANGO_ADMIN_PASSWORD: "ReDjango-E2E-only-2026!",
      REDJANGO_ADMIN_GAME_ROLE: "admin",
    },
    url: "http://127.0.0.1:8130/api/auth/session/",
    reuseExistingServer: false,
    timeout: 120000,
  },
});
