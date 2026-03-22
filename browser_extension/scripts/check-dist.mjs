import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");

const required = [
  "manifest.json",
  "background.js",
  "popup.html",
  "popup.js",
  "options.html",
  "options.js",
];

let ok = true;
for (const name of required) {
  const p = join(dist, name);
  if (!existsSync(p)) {
    console.error(`Missing dist artifact: ${name} (run npm run build)`);
    ok = false;
  }
}

if (!ok) {
  process.exit(1);
}

console.log("dist/ artifacts OK");
