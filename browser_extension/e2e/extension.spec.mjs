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

/** Launch a persistent context with the extension loaded. */
async function launchWithExtension() {
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    args: [
      `--disable-extensions-except=${pathToExtension}`,
      `--load-extension=${pathToExtension}`,
    ],
    viewport: { width: 1280, height: 720 },
  });
  let sw = context.serviceWorkers()[0];
  if (!sw) {
    sw = await context.waitForEvent("serviceworker");
  }
  const id = sw.url().split("/")[2];
  return { context, id };
}

test("options + popup validate valid SPL against local httpd", async () => {
  const { context, id } = await launchWithExtension();
  try {
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

test("popup shows valid:false for invalid SPL", async () => {
  const { context, id } = await launchWithExtension();
  try {
    const page = await context.newPage();
    await page.goto(`chrome-extension://${id}/options.html`);
    await page.locator("#apiBase").fill("http://127.0.0.1:19999");
    await page.locator("#apiBase").blur();
    await page.goto(`chrome-extension://${id}/popup.html`);
    await page.locator("#spl").fill("| stats count BY");
    await page.getByRole("button", { name: "Validate" }).click();
    await expect(page.locator("#out")).toContainText('"valid": false', { timeout: 30_000 });
  } finally {
    await context.close();
  }
});

test("popup shows error or stalls when server is unreachable", async () => {
  const { context, id } = await launchWithExtension();
  try {
    const page = await context.newPage();
    await page.goto(`chrome-extension://${id}/options.html`);
    await page.locator("#apiBase").fill("http://127.0.0.1:19998");
    await page.locator("#apiBase").blur();
    await page.goto(`chrome-extension://${id}/popup.html`);
    await page.locator("#spl").fill("index=web");
    await page.getByRole("button", { name: "Validate" }).click();
    await page.waitForTimeout(3_000);
    const text = await page.locator("#out").textContent();
    expect(text).not.toBe("{}");
  } finally {
    await context.close();
  }
});

test("options page persists apiBase setting", async () => {
  const { context, id } = await launchWithExtension();
  try {
    const page = await context.newPage();
    await page.goto(`chrome-extension://${id}/options.html`);
    await page.locator("#apiBase").fill("http://127.0.0.1:19999");
    await page.locator("#apiBase").blur();
    await page.waitForTimeout(500);
    await page.reload();
    const value = await page.locator("#apiBase").inputValue();
    expect(value).toBe("http://127.0.0.1:19999");
  } finally {
    await context.close();
  }
});
