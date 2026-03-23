#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { validate, buildValidationJsonDict } from "@spl-validator/core";

function readStdin(): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    process.stdin.on("data", (c) => chunks.push(c));
    process.stdin.on("end", () => resolve(Buffer.concat(chunks).toString("utf-8")));
    process.stdin.on("error", reject);
  });
}

const USAGE = `Usage: spl-validator-ts [options] [SPL]

Options:
  --spl SPL         SPL query string to validate
  --file PATH       Read SPL from file
  --strict          Treat unknown commands as errors
  --format=json     Output as JSON (default: text)
  --advice=GROUP    Warning groups: all, optimization, none, or comma-separated
  -h, --help        Show this help message

Examples:
  spl-validator-ts --spl "index=web | stats count BY host"
  spl-validator-ts --format=json "index=web | stats count"
  echo "index=web | head 5" | spl-validator-ts --format=json`;

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  let spl = "";
  let strict = false;
  let format: "text" | "json" = "text";
  let advice = "all";

  for (let i = 0; i < args.length; i++) {
    const a = args[i]!;
    if (a === "-h" || a === "--help") {
      console.log(USAGE);
      process.exit(0);
    } else if (a === "--strict") strict = true;
    else if (a === "--format=json") format = "json";
    else if (a.startsWith("--advice=")) advice = a.slice("--advice=".length);
    else if (a === "--spl" && args[i + 1]) {
      spl = args[++i]!;
    } else if (a === "--file" && args[i + 1]) {
      spl = readFileSync(args[++i]!, "utf-8");
    } else if (!a.startsWith("-") && !spl) {
      spl = a;
    }
  }

  if (!spl && !process.stdin.isTTY) {
    spl = await readStdin();
  }

  spl = spl.trimEnd();
  if (!spl) {
    console.error("Usage: spl-validator-ts [--strict] [--format=json] [--advice=all] (--spl SPL | --file path | SPL | stdin)");
    process.exit(2);
  }

  const result = validate(spl, { strict });
  if (format === "json") {
    console.log(
      JSON.stringify(buildValidationJsonDict(result, result.ast, { warningGroups: advice }), null, 2),
    );
    process.exit(result.is_valid ? 0 : 1);
  }

  console.log(result.is_valid ? "VALID" : "INVALID");
  for (const e of result.errors) {
    console.error(`[${e.code}] ${e.message} @ ${e.start.line}:${e.start.column}`);
  }
  for (const w of result.warnings) {
    console.error(`WARN [${w.code}] ${w.message}`);
  }
  process.exit(result.is_valid ? 0 : 1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
