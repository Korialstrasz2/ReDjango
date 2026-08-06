import { defineConfig } from "@playwright/test";

const runtimePlatform = (globalThis as typeof globalThis & { process?: { platform?: string } }).process?.platform || "";
const python = runtimePlatform.startsWith("win") ? "..\\venv\\Scripts\\python.exe" : "python";
const django = (command: string) => `${python} ../manage.py ${command}`;
const authenticatedState = ".playwright/auth.json";
const combatMasterState = ".playwright/auth-combat-master.json";
const combatPlayerState = ".playwright/auth-combat-player.json";
const mobileMatrix = /mobile-(?:baseline|skills|competencies|creation|new-character|character|travel|combat|quick-tools|integrated)\.spec\.ts/;
const combatRoleMatrix = /mobile-combat-roles\.spec\.ts/;
const desktopVisualMatrix = /desktop-visual-(?:baseline\.spec|setup)\.ts/;

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
      // Canonical desktop project: run only the pre-existing desktop suite.
      // Mobile/role matrices and the pinned visual harness have protected jobs of their own.
      name: "authenticated",
      testIgnore: [/auth\.setup\.ts/, mobileMatrix, combatRoleMatrix, desktopVisualMatrix],
      dependencies: ["setup"],
      use: { storageState: authenticatedState },
    },
    {
      name: "desktop-1920",
      testMatch: mobileMatrix,
      dependencies: ["setup"],
      use: {
        storageState: authenticatedState,
        viewport: { width: 1920, height: 1080 },
      },
    },
    {
      name: "phone-small-portrait",
      testMatch: mobileMatrix,
      dependencies: ["setup"],
      use: {
        storageState: authenticatedState,
        viewport: { width: 360, height: 740 },
        deviceScaleFactor: 3,
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      // Exercises the 480–767px phone category rather than another narrow-phone width.
      name: "phone-large-portrait",
      testMatch: mobileMatrix,
      dependencies: ["setup"],
      use: {
        storageState: authenticatedState,
        viewport: { width: 540, height: 960 },
        deviceScaleFactor: 2,
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      // Stays below the phone/tablet layout boundary even in landscape.
      name: "phone-landscape",
      testMatch: mobileMatrix,
      dependencies: ["setup"],
      use: {
        storageState: authenticatedState,
        viewport: { width: 740, height: 360 },
        deviceScaleFactor: 3,
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      name: "tablet-portrait",
      testMatch: mobileMatrix,
      dependencies: ["setup"],
      use: {
        storageState: authenticatedState,
        viewport: { width: 820, height: 1180 },
        deviceScaleFactor: 2,
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      name: "tablet-landscape",
      testMatch: mobileMatrix,
      dependencies: ["setup"],
      use: {
        storageState: authenticatedState,
        viewport: { width: 1180, height: 820 },
        deviceScaleFactor: 2,
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      name: "phone-combat-master",
      testMatch: combatRoleMatrix,
      dependencies: ["setup"],
      use: {
        storageState: combatMasterState,
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      name: "phone-combat-player",
      testMatch: combatRoleMatrix,
      dependencies: ["setup"],
      use: {
        storageState: combatPlayerState,
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 3,
        hasTouch: true,
        isMobile: true,
      },
    },
    {
      name: "desktop-combat-master",
      testMatch: combatRoleMatrix,
      dependencies: ["setup"],
      use: {
        storageState: combatMasterState,
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "desktop-combat-player",
      testMatch: combatRoleMatrix,
      dependencies: ["setup"],
      use: {
        storageState: combatPlayerState,
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
  webServer: {
    command: [
      django("migrate --noinput"),
      django("flush --noinput"),
      django("seed_minimum_data"),
      django("ensure_admin_login"),
      django("ensure_combat_e2e_roles"),
      django("ensure_master_ai_e2e"),
      django("runserver 127.0.0.1:8128 --noreload"),
    ].join(" && "),
    env: {
      REDJANGO_ACCESS_MODE: "locked",
      REDJANGO_DATABASE_NAME: "frontend/e2e.sqlite3",
      REDJANGO_ADMIN_USERNAME: "local_master",
      REDJANGO_ADMIN_PASSWORD: "ReDjango-E2E-only-2026!",
      REDJANGO_ADMIN_GAME_ROLE: "admin",
      REDJANGO_COMBAT_E2E_PASSWORD: "ReDjango-Combat-E2E-2026!",
    },
    url: "http://127.0.0.1:8128/api/auth/session/",
    reuseExistingServer: false,
    timeout: 120000
  }
});
