import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";
import { validate, buildValidationJsonDict } from "../src/index.ts";

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const goldenDir = join(repoRoot, "tests", "golden");

interface GoldenFile {
  golden_format_version?: number;
  tests: Array<{
    name: string;
    spl: string;
    expected: Record<string, unknown>;
  }>;
}

function runCase(t: GoldenFile["tests"][0]): string[] {
  const failures: string[] = [];
  const { spl, expected, name } = t;
  const result = validate(spl, { strict: false });
  const json = buildValidationJsonDict(result, result.ast as never, { warningGroups: "all" });

  const expValid = expected.valid !== false;
  if (result.is_valid !== expValid) {
    failures.push(`${name}: valid expected ${expValid} got ${result.is_valid}`);
  }

  if (Array.isArray(expected.error_codes)) {
    const codes = result.errors.map((e) => e.code);
    for (const c of expected.error_codes as string[]) {
      if (!codes.includes(c)) {
        failures.push(`${name}: missing error code ${c}, got ${codes.join(",")}`);
      }
    }
  }

  if (typeof expected.error_count === "number") {
    if (result.errors.length !== expected.error_count) {
      failures.push(`${name}: error_count expected ${expected.error_count} got ${result.errors.length}`);
    }
  }

  if (Array.isArray(expected.warning_codes)) {
    const codes = result.warnings.map((w) => w.code);
    for (const c of expected.warning_codes as string[]) {
      if (!codes.includes(c)) {
        failures.push(`${name}: missing warning ${c}, got ${codes.join(",")}`);
      }
    }
  }

  if (Array.isArray(expected.warning_codes_not)) {
    const codes = result.warnings.map((w) => w.code);
    for (const c of expected.warning_codes_not as string[]) {
      if (codes.includes(c)) {
        failures.push(`${name}: unexpected warning ${c}`);
      }
    }
  }

  if (Array.isArray(expected.warning_text_contains)) {
    const blob = result.warnings.map((w) => w.message + (w.suggestion ?? "")).join(" ");
    for (const frag of expected.warning_text_contains as string[]) {
      if (!blob.includes(frag)) {
        failures.push(`${name}: warning text should contain ${JSON.stringify(frag)}`);
      }
    }
  }

  if (Array.isArray(expected.warning_text_not_contains)) {
    const blob = result.warnings.map((w) => w.message + (w.suggestion ?? "")).join(" ");
    for (const frag of expected.warning_text_not_contains as string[]) {
      if (blob.includes(frag)) {
        failures.push(`${name}: warning text should NOT contain ${JSON.stringify(frag)}`);
      }
    }
  }

  if (expected.valid_json === true) {
    try {
      JSON.stringify(json);
    } catch {
      failures.push(`${name}: JSON serialization failed`);
    }
  }

  return failures;
}

for (const name of readdirSync(goldenDir).filter((f) => f.endsWith(".json"))) {
  const path = join(goldenDir, name);
  const data = JSON.parse(readFileSync(path, "utf-8")) as GoldenFile;
  if ((data.golden_format_version ?? 1) > 1) continue;

  test(`golden: ${name}`, () => {
    const all: string[] = [];
    for (const t of data.tests) {
      all.push(...runCase(t));
    }
    assert.equal(all.length, 0, all.join("\n"));
  });
}
