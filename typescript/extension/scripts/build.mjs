import * as esbuild from "esbuild";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const coreEntry = join(root, "..", "core", "dist", "index.js");

rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });

await esbuild.build({
  entryPoints: [join(root, "src", "popup.js")],
  bundle: true,
  format: "iife",
  platform: "browser",
  target: ["chrome114"],
  outfile: join(dist, "popup.js"),
  legalComments: "none",
  minify: true,
  alias: {
    "@spl-validator/core": coreEntry,
  },
  logLevel: "info",
});

cpSync(join(root, "src", "popup.html"), join(dist, "popup.html"));
cpSync(join(root, "src", "background.js"), join(dist, "background.js"));

const manifestPath = join(root, "src", "manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
writeFileSync(join(dist, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

console.log(`Built standalone extension to ${dist}`);
