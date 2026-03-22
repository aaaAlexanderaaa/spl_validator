import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, expect, test } from "@playwright/test";

const root = dirname(fileURLToPath(import.meta.url));
const pathToExtension = join(root, "..", "dist");
const userDataDir = join(root, "..", ".pw-profile");

test.beforeAll(() => {
  if (!existsSync(join(pathToExtension, "manifest.json"))) {
    throw new Error("browser_extension/dist is missing; run: npm run build");
  }
});

test.describe.configure({ mode: "serial" });

test("options + popup validate SPL against local httpd", async () => {
  const context = await chromium.launchPersistentContext(userDataDir, {
    channel: "chromium",
    headless: false,
    args: [
      `--disable-extensions-except=${pathToExtension}`,
      `--load-extension=${pathToExtension}`,
    ],
    viewport: { width: 1280, height: 720 },
  });

  try {
    let sw = context.serviceWorkers()[0];
    if (!sw) {
      sw = await context.waitForEvent("serviceworker");
    }
    const id = sw.url().split("/")[2];
    expect(id.length).toBeGreaterThan(4);

    const page = await context.newPage();
    await page.goto(`chrome-extension://${id}/options.html`);
    await page.locator("#apiBase").fill("http://127.0.0.1:19999");
    await page.locator("#apiBase").blur();
    await page.goto(`chrome-extension://${id}/popup.html`);
    await page.locator("#spl").fill("index=web | stats count BY host");
    await page.getByRole("button", { name: "Validate" }).click();
    await expect(page.locator("#out")).toContainText('"valid": true', { timeout: 30_000 });
  } finally {
    await context.close();
  }
});
