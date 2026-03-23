/**
 * Edge-case unit tests for the TypeScript SPL validator.
 *
 * Covers lexer, parser, validator, and JSON output edge cases that go
 * beyond the shared golden integration tests.
 */
import test from "node:test";
import assert from "node:assert/strict";
import { validate, buildValidationJsonDict } from "../src/index.ts";
import { Lexer } from "../src/lexer.ts";

// ── Lexer edge cases ─────────────────────────────────────────────────

test("lexer: empty input produces only EOF", () => {
  const tokens = new Lexer("").tokenize();
  assert.equal(tokens.length, 1);
  assert.equal(tokens[0].type, "EOF");
});

test("lexer: whitespace-only input", () => {
  const tokens = new Lexer("   \t  ").tokenize();
  assert.equal(tokens[tokens.length - 1].type, "EOF");
});

test("lexer: single pipe token", () => {
  const tokens = new Lexer("|").tokenize();
  const pipes = tokens.filter((t) => t.type === "PIPE");
  assert.equal(pipes.length, 1);
});

test("lexer: unclosed double quote produces ERROR token", () => {
  const tokens = new Lexer('"hello').tokenize();
  const errors = tokens.filter((t) => t.type === "ERROR");
  assert.ok(errors.length >= 1, "Expected at least one ERROR token");
});

test("lexer: unclosed single quote produces ERROR token", () => {
  const tokens = new Lexer("'hello").tokenize();
  const errors = tokens.filter((t) => t.type === "ERROR");
  assert.ok(errors.length >= 1, "Expected at least one ERROR token");
});

test("lexer: escaped quotes inside double-quoted string", () => {
  const tokens = new Lexer('"say \\"hi\\""').tokenize();
  const strings = tokens.filter((t) => t.type === "STRING");
  assert.equal(strings.length, 1);
});

test("lexer: nested parentheses", () => {
  const tokens = new Lexer("sum(if(a>0,b,c))").tokenize();
  const lp = tokens.filter((t) => t.type === "LPAREN");
  const rp = tokens.filter((t) => t.type === "RPAREN");
  assert.equal(lp.length, 2);
  assert.equal(rp.length, 2);
});

test("lexer: very long identifier does not crash", () => {
  const longId = "a".repeat(10000);
  const tokens = new Lexer(`index=${longId}`).tokenize();
  assert.ok(tokens.some((t) => t.value === longId));
});

test("lexer: comparison operators", () => {
  for (const op of ["==", "!=", ">=", "<=", ">", "<"]) {
    const tokens = new Lexer(`x ${op} 1`).tokenize();
    assert.ok(
      tokens.some((t) => t.value === op),
      `Expected operator ${op} to be tokenized`,
    );
  }
});

test("lexer: boolean keywords AND/OR/NOT", () => {
  const tokens = new Lexer("a AND b OR c NOT d").tokenize();
  const keywords = tokens.filter(
    (t) => t.type === "AND" || t.type === "OR" || t.type === "NOT",
  );
  assert.equal(keywords.length, 3);
});

test("lexer: LIKE keyword operator", () => {
  const tokens = new Lexer('user LIKE "adm%"').tokenize();
  assert.ok(tokens.some((t) => t.type === "LIKE"));
});

// ── Validator edge cases ─────────────────────────────────────────────

test("validator: empty string is invalid with SPL005", () => {
  const r = validate("", { strict: false });
  assert.equal(r.is_valid, false);
  assert.ok(r.errors.some((e) => e.code === "SPL005"));
});

test("validator: whitespace-only is invalid", () => {
  const r = validate("   \t  ", { strict: false });
  assert.equal(r.is_valid, false);
});

test("validator: single pipe is invalid", () => {
  const r = validate("|", { strict: false });
  assert.equal(r.is_valid, false);
});

test("validator: trailing pipe is tolerated", () => {
  const r = validate("index=web | stats count |", { strict: false });
  assert.equal(r.is_valid, true);
});

test("validator: double pipe is invalid", () => {
  const r = validate("index=web || stats count", { strict: false });
  assert.equal(r.is_valid, false);
});

test("validator: leading pipe non-generating first (SPL001)", () => {
  const r = validate("| stats count", { strict: false });
  assert.equal(r.is_valid, false);
  assert.ok(r.errors.some((e) => e.code === "SPL001"));
});

test("validator: simplest valid query", () => {
  const r = validate("index=main", { strict: false });
  assert.equal(r.is_valid, true);
  assert.notEqual(r.ast, null);
});

test("validator: makeresults is generating", () => {
  const r = validate("| makeresults | eval x=1", { strict: false });
  assert.equal(r.is_valid, true);
});

test("validator: strict mode rejects unknown command", () => {
  const r = validate("| makeresults | unknowncmd123", { strict: true });
  assert.equal(r.is_valid, false);
  assert.ok(r.errors.some((e) => e.code === "SPL013"));
});

test("validator: strict mode allows macros", () => {
  const r = validate("index=web | `my_macro(arg1, arg2)`", { strict: true });
  assert.equal(r.is_valid, true);
});

test("validator: empty subsearch is SPL022", () => {
  const r = validate("index=web | join host []", { strict: false });
  assert.equal(r.is_valid, false);
  assert.ok(r.errors.some((e) => e.code === "SPL022"));
});

test("validator: very long pipeline does not crash", () => {
  const evals = Array.from({ length: 50 }, (_, i) => `eval f${i}=${i}`).join(" | ");
  const r = validate(`index=main | ${evals}`, { strict: false });
  assert.notEqual(r.ast, null);
});

// ── Suggestion/warning edge cases ────────────────────────────────────

test("warnings: stats BY triggers LIMSTA", () => {
  const r = validate("index=web | stats count BY host", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "LIMSTA"));
});

test("warnings: dedup without sort triggers BEST001", () => {
  const r = validate("index=web | dedup host", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST001"));
});

test("warnings: join without type triggers BEST002", () => {
  const r = validate("index=web | join host [search index=dns | head 100]", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST002"));
});

test("warnings: unbounded transaction triggers BEST003", () => {
  const r = validate("index=web | transaction host", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST003"));
});

test("warnings: transaction maxspan still triggers BEST003 (options not parsed)", () => {
  const r = validate("index=web | transaction host maxspan=30m", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST003"));
});

test("warnings: consecutive eval triggers BEST008", () => {
  const r = validate("index=web | eval a=1 | eval b=2", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST008"));
});

test("warnings: sort unlimited triggers BEST006", () => {
  const r = validate("index=web | stats count BY host | sort - count", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST006"));
});

test("warnings: table * triggers BEST007", () => {
  const r = validate("index=web | table *", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST007"));
});

test("warnings: mvexpand triggers BEST013", () => {
  const r = validate("index=web | mvexpand myfield", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "BEST013"));
});

test("warnings: tail triggers LIMTAI", () => {
  const r = validate("index=web | tail", { strict: false });
  assert.ok(r.warnings.some((w) => w.code === "LIMTAI"));
});

// ── JSON output edge cases ───────────────────────────────────────────

test("json output: valid query produces serializable JSON", () => {
  const r = validate("index=web | stats count", { strict: false });
  const json = buildValidationJsonDict(r, r.ast, { warningGroups: "all" });
  assert.equal(json.valid, true);
  assert.doesNotThrow(() => JSON.stringify(json));
});

test("json output: invalid query produces serializable JSON", () => {
  const r = validate("", { strict: false });
  const json = buildValidationJsonDict(r, r.ast, { warningGroups: "all" });
  assert.equal(json.valid, false);
  assert.doesNotThrow(() => JSON.stringify(json));
});

test("json output: contains schema version", () => {
  const r = validate("index=main", { strict: false });
  const json = buildValidationJsonDict(r, r.ast, { warningGroups: "all" });
  assert.ok("output_schema_version" in json);
  assert.ok("package_version" in json);
});

test("json output: warnings array present for valid query", () => {
  const r = validate("index=web | stats count BY host", { strict: false });
  const json = buildValidationJsonDict(r, r.ast, { warningGroups: "all" });
  assert.ok(Array.isArray(json.warnings));
  assert.ok(json.warnings.length > 0);
});
