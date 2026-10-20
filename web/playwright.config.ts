import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Browser smoke tests against the real server and the built client
// (run `npm run build` first). MIMO_SERVER overrides the server command,
// e.g. `mimo-array-server` when it is on PATH (CI) or a Windows venv path.
const port = Number(process.env.E2E_PORT ?? 8765);
const server = process.env.MIMO_SERVER ?? "../.venv/bin/mimo-array-server";
const dataDir = mkdtempSync(join(tmpdir(), "mimo-e2e-"));
// CI runs Chromium; E2E_BROWSERS=chromium,firefox,webkit adds the other engines
// (install them first with `npx playwright install firefox webkit`).
const browsers = (process.env.E2E_BROWSERS ?? "chromium").split(",").map((name) => name.trim());
const devicesByBrowser: Record<string, (typeof devices)[string]> = {
  chromium: devices["Desktop Chrome"],
  firefox: devices["Desktop Firefox"],
  webkit: devices["Desktop Safari"],
};

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: "zh-CN",
    trace: "retain-on-failure",
  },
  projects: browsers
    .filter((name) => name in devicesByBrowser)
    .map((name) => ({ name, use: { ...devicesByBrowser[name], viewport: { width: 1440, height: 900 } } })),
  webServer: {
    command: `${server} --host 127.0.0.1 --port ${port} --data-dir "${dataDir}"`,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
