import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:8003",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure"
  },
  webServer: {
    command: "..\\venv\\Scripts\\python.exe ..\\manage.py runserver 127.0.0.1:8003 --noreload",
    url: "http://127.0.0.1:8003/api/health/",
    reuseExistingServer: true,
    timeout: 120000
  }
});
