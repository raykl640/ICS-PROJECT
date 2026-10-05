import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig } from "@playwright/test";

// E2E runs against the real FastAPI app with HAKI_FAKE_BACKENDS=1 (synthetic corpus, fake models), serving dist/.
const PORT = 8765;
// A fresh accounts database per run, outside the repo (never data/app.db).
const APP_DB = join(tmpdir(), `hakiai-e2e-${process.pid}-${Date.now()}.db`);
const python = process.env.PYTHON ?? (existsSync("../.venv/bin/python") ? ".venv/bin/python" : "python");
const chromium = process.env.PLAYWRIGHT_CHROMIUM ?? (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined);

export default defineConfig({
  testDir: "e2e",
  outputDir: "test-results",
  workers: 1,
  reporter: "line",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    acceptDownloads: true,
    launchOptions: chromium ? { executablePath: chromium } : {},
  },
  webServer: {
    command: `${python} -m uvicorn backend.app.main:app --host 127.0.0.1 --port ${PORT}`,
    cwd: "..",
    env: { HAKI_FAKE_BACKENDS: "1", HAKI_APP_DB_PATH: APP_DB },
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
