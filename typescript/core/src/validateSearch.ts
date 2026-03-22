import type { Command } from "./ast.js";
import { Lexer } from "./lexer.js";
import { KEYWORDS, type Token, TokenType } from "./tokens.js";
import { addError, addWarning } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";

const DOTTED_SEGMENT_TYPES = new Set<TokenType>([TokenType.IDENTIFIER, ...Object.values(KEYWORDS)]);

function commandTokens(cmd: Command, result: ValidationResult): Token[] {
  const lexSource = result._lexSpl ?? result.spl;
  const lexer = new Lexer(lexSource);
  const all = lexer.tokenize();
  const out: Token[] = [];
  for (const t of all) {
    if (t.type === TokenType.EOF) break;
    if (t.start.offset >= cmd.start.offset && t.end.offset <= cmd.end.offset) {
      out.push(t);
    }
  }
  while (out.length && out[0]!.type === TokenType.PIPE) out.shift();
  if (out.length && out[0]!.type === TokenType.IDENTIFIER && out[0]!.value.toLowerCase() === "search") {
    out.shift();
  }
  return out;
}

function consumeFieldRef(tokens: Token[], start: number): [string, number] | null {
  if (start >= tokens.length || tokens[start]!.type !== TokenType.IDENTIFIER) return null;
  const parts = [tokens[start]!.value];
  let i = start;
  while (
    i + 2 < tokens.length &&
    tokens[i + 1]!.type === TokenType.DOT &&
    DOTTED_SEGMENT_TYPES.has(tokens[i + 2]!.type)
  ) {
    parts.push(tokens[i + 2]!.value);
    i += 2;
  }
  return [parts.join("."), i + 1];
}

function consumeInValue(tokens: Token[], start: number): [number, boolean] | null {
  if (start >= tokens.length) return null;
  const t0 = tokens[start]!;
  if (t0.type === TokenType.STRING) return [start + 1, false];
  if (t0.type === TokenType.NUMBER) {
    let i = start + 1;
    let sawIpLike = false;
    while (
      i < tokens.length &&
      tokens[i]!.type === TokenType.NUMBER &&
      tokens[i]!.value.startsWith(".")
    ) {
      sawIpLike = true;
      i += 1;
    }
    if (
      sawIpLike &&
      i + 1 < tokens.length &&
      tokens[i]!.type === TokenType.SLASH &&
      tokens[i + 1]!.type === TokenType.NUMBER
    ) {
      i += 2;
    }
    if (sawIpLike) return [i, false];
    return [start + 1, false];
  }
  if (
    t0.type !== TokenType.IDENTIFIER &&
    t0.type !== TokenType.STAR &&
    t0.type !== TokenType.MINUS &&
    t0.type !== TokenType.PLUS
  ) {
    return null;
  }
  let i = start;
  let sawSlashNumber = false;
  while (i < tokens.length) {
    const t = tokens[i]!;
    if (
      t.type === TokenType.IDENTIFIER ||
      t.type === TokenType.STAR ||
      t.type === TokenType.NUMBER ||
      t.type === TokenType.MINUS ||
      t.type === TokenType.PLUS
    ) {
      i += 1;
      continue;
    }
    if (
      t.type === TokenType.SLASH &&
      !sawSlashNumber &&
      i > start &&
      i + 1 < tokens.length &&
      tokens[i + 1]!.type === TokenType.NUMBER
    ) {
      sawSlashNumber = true;
      i += 2;
      continue;
    }
    if (
      t.type === TokenType.DOT &&
      i + 1 < tokens.length &&
      (tokens[i + 1]!.type === TokenType.IDENTIFIER || tokens[i + 1]!.type === TokenType.STAR)
    ) {
      i += 2;
      continue;
    }
    break;
  }
  return [i, false];
}

function validateInOperators(tokens: Token[], cmd: Command, result: ValidationResult): void {
  let sawLowercaseIn = false;
  let sawLowercaseNot = false;
  for (const t of tokens) {
    if (t.type === TokenType.NOT && t.value.toLowerCase() === "not" && t.value !== "NOT") {
      sawLowercaseNot = true;
    }
  }

  let i = 0;
  while (i < tokens.length) {
    const consumed = consumeFieldRef(tokens, i);
    if (consumed === null) {
      i += 1;
      continue;
    }
    const [, j] = consumed;

    if (
      j + 2 < tokens.length &&
      tokens[j]!.type === TokenType.NOT &&
      tokens[j + 1]!.type === TokenType.IDENTIFIER &&
      tokens[j + 1]!.value.toLowerCase() === "in" &&
      tokens[j + 2]!.type === TokenType.LPAREN
    ) {
      if (tokens[j + 1]!.value !== "IN") sawLowercaseIn = true;
      addError(
        result,
        "SPL011",
        "Invalid search syntax: use NOT <field> IN (...), not <field> NOT IN (...)",
        tokens[j]!.start,
        tokens[j + 2]!.end,
        "Example: index=main NOT action IN (addtocart, purchase)",
      );
      i = j + 3;
      continue;
    }

    if (
      j + 1 < tokens.length &&
      tokens[j]!.type === TokenType.IDENTIFIER &&
      tokens[j]!.value.toLowerCase() === "in" &&
      tokens[j + 1]!.type === TokenType.LPAREN
    ) {
      if (tokens[j]!.value !== "IN") sawLowercaseIn = true;
      let k = j + 2;
      if (k >= tokens.length) {
        addError(
          result,
          "SPL011",
          "IN operator requires a value list: IN (<value>(,<value>)*)",
          tokens[j]!.start,
          tokens[j + 1]!.end,
          "Example: action IN (addtocart, purchase)",
        );
        i = j + 2;
        continue;
      }

      let expectValue = true;
      let seenAnyValue = false;
      let sawEmptyValue = false;
      let sawTrailingComma = false;
      let emittedListError = false;
      let sawImplicitStringSeparator = false;
      let prevValueEndOffset: number | null = null;

      while (k < tokens.length) {
        const t = tokens[k]!;
        if (t.type === TokenType.RPAREN) break;
        if (expectValue) {
          if (t.type === TokenType.COMMA) {
            sawEmptyValue = true;
            k += 1;
            continue;
          }
          const consumedV = consumeInValue(tokens, k);
          if (consumedV === null) {
            addError(
              result,
              "SPL011",
              "Invalid IN value list: expected a value",
              t.start,
              t.end,
              "Example: action IN (addtocart, purchase)",
            );
            emittedListError = true;
            break;
          }
          seenAnyValue = true;
          expectValue = false;
          prevValueEndOffset = tokens[consumedV[0] - 1]!.end.offset;
          k = consumedV[0];
          continue;
        }
        if (t.type === TokenType.COMMA) {
          expectValue = true;
          k += 1;
          continue;
        }
        if (prevValueEndOffset !== null && t.type === TokenType.STRING) {
          if (t.start.offset > prevValueEndOffset) {
            sawImplicitStringSeparator = true;
            expectValue = true;
            continue;
          }
        }
        addError(
          result,
          "SPL011",
          "Invalid IN value list: expected ',' or ')'",
          t.start,
          t.end,
          "Example: action IN (addtocart, purchase)",
        );
        emittedListError = true;
        break;
      }

      if (
        k < tokens.length &&
        tokens[k]!.type === TokenType.RPAREN &&
        expectValue &&
        seenAnyValue
      ) {
        sawTrailingComma = true;
      }

      if (k >= tokens.length || tokens[k]!.type !== TokenType.RPAREN) {
        if (!emittedListError) {
          const endTok = tokens[Math.min(k, tokens.length - 1)]!;
          addError(
            result,
            "SPL011",
            "Unclosed IN value list: expected ')'",
            tokens[j + 1]!.start,
            endTok.end,
          );
        }
      } else if (!seenAnyValue) {
        addError(
          result,
          "SPL011",
          "IN value list cannot be empty",
          tokens[j + 1]!.start,
          tokens[k]!.end,
          "Example: action IN (addtocart, purchase)",
        );
      } else {
        const spanEnd = tokens[k]!.end;
        if (sawImplicitStringSeparator) {
          addWarning(
            result,
            "BEST015",
            "IN value lists should use commas between quoted values (tolerated when whitespace-separated, but error-prone)",
            tokens[j]!.start,
            spanEnd,
            'Example: action IN ("a", "b")',
          );
        }
        if (sawEmptyValue || sawTrailingComma) {
          addWarning(
            result,
            "BEST014",
            "Avoid empty items/trailing commas in IN value lists (Splunk often accepts them, but they are error-prone)",
            tokens[j]!.start,
            spanEnd,
            "Example: action IN (addtocart, purchase)",
          );
        }
      }

      i = k + 1;
      continue;
    }

    i = j;
  }

  if (sawLowercaseIn) {
    addWarning(
      result,
      "BEST011",
      "Use uppercase keyword IN in search filters (case-insensitive but clearer)",
      cmd.start,
      cmd.end,
      "Example: action IN (addtocart, purchase)",
    );
  }
  if (sawLowercaseNot) {
    addWarning(
      result,
      "BEST012",
      "Use uppercase keyword NOT in search filters (case-insensitive but clearer)",
      cmd.start,
      cmd.end,
      "Example: NOT action IN (addtocart, purchase)",
    );
  }
}

export function validateSearchTerms(cmd: Command, result: ValidationResult, warnPlainText: boolean): void {
  const toks = commandTokens(cmd, result);
  validateInOperators(toks, cmd, result);

  const validSearchKeys = new Set(["index", "sourcetype", "host", "source", "earliest", "latest"]);
  let hasValidPattern = false;
  for (const key of Object.keys(cmd.options)) {
    if (validSearchKeys.has(key.toLowerCase())) {
      hasValidPattern = true;
      break;
    }
  }
  if (Object.keys(cmd.clauses).length) hasValidPattern = true;

  if (
    warnPlainText &&
    !hasValidPattern &&
    Object.keys(cmd.options).length === 0
  ) {
    addWarning(
      result,
      "SPL050",
      "Search appears to be plain text without index/sourcetype specification. Consider using: index=<index_name> <search_terms>",
      cmd.start,
      cmd.end,
      "Valid search: index=main sourcetype=access_combined status=200",
    );
  }
}
