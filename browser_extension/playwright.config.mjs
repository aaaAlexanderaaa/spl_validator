import { defineConfig } from "@playwright/test";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(root, "..");

export default defineConfig({
  testDir: "e2e",
  timeout: 120_000,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: {
    trace: "retain-on-failure",
  },
  webServer: {
    command: "python3 -m spl_validator.httpd --host 127.0.0.1 --port 19999",
    cwd: repoRoot,
    url: "http://127.0.0.1:19999/health",
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
});
