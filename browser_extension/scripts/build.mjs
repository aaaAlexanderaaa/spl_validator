import * as esbuild from "esbuild";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));

rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });

await esbuild.build({
  entryPoints: {
    popup: join(root, "src/ui/popup.js"),
    options: join(root, "src/ui/options.js"),
  },
  bundle: true,
  format: "iife",
  platform: "browser",
  target: ["chrome114"],
  outdir: dist,
  legalComments: "none",
  minify: true,
  logLevel: "info",
});

cpSync(join(root, "src/popup.html"), join(dist, "popup.html"));
cpSync(join(root, "src/options.html"), join(dist, "options.html"));
cpSync(join(root, "src/background.js"), join(dist, "background.js"));

const manifestPath = join(root, "src/manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
manifest.version = String(pkg.version);
writeFileSync(join(dist, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

console.log(`Built extension to ${dist}`);
