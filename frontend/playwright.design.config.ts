import { existsSync } from "node:fs";
import { defineConfig } from "@playwright/test";

// Design screenshots: the dev-only /styleguide page on the Vite dev server (no backend needed).
const PORT = 5198;
const chromium = process.env.PLAYWRIGHT_CHROMIUM ?? (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined);

export default defineConfig({
  testDir: "e2e-design",
  outputDir: "test-results/design",
  workers: 2,
  reporter: "line",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    launchOptions: chromium ? { executablePath: chromium } : {},
  },
  webServer: {
    command: `npx vite --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}/styleguide`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
