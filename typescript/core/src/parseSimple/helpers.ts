import type { Argument, Clause, Pipeline, Subsearch } from "../ast.js";
import { CommandParser } from "../parser/commandParser.js";
import { ParseError } from "../parser/parseError.js";
import { KEYWORDS, type Token, TokenType } from "../tokens.js";
import type { ValidationResult } from "../models/result.js";
import { addError } from "../models/result.js";
import { isKnownCommand } from "../registry.js";

const DOTTED_SEGMENT_TYPES = new Set<TokenType>([TokenType.IDENTIFIER, ...Object.values(KEYWORDS)]);

export function extractSingleSubsearch(
  argTokens: Token[],
  result: ValidationResult,
  parseSimple: (tokens: Token[], r: ValidationResult) => Pipeline | null,
): [Subsearch | null, Token[]] {
  let bracketStart: number | null = null;
  let bracketEnd: number | null = null;
  let depth = 0;
  for (let idx = 0; idx < argTokens.length; idx++) {
    if (argTokens[idx]!.type === TokenType.LBRACKET) {
      bracketStart = idx;
      depth = 1;
      for (let jdx = idx + 1; jdx < argTokens.length; jdx++) {
        if (argTokens[jdx]!.type === TokenType.LBRACKET) depth += 1;
        else if (argTokens[jdx]!.type === TokenType.RBRACKET) {
          depth -= 1;
          if (depth === 0) {
            bracketEnd = jdx;
            break;
          }
        }
      }
      break;
    }
  }

  if (bracketStart === null) return [null, argTokens];
  if (bracketEnd === null) {
    const startTok = argTokens[bracketStart]!;
    addError(
      result,
      "SPL011",
      "Unclosed subsearch bracket '['",
      startTok.start,
      startTok.end,
      "Add a closing ']' for the subsearch",
    );
    return [null, argTokens];
  }

  const inner = argTokens.slice(bracketStart + 1, bracketEnd);
  const lbr = argTokens[bracketStart]!;
  const rbr = argTokens[bracketEnd]!;
  let innerPipeline: Pipeline | null = null;
  if (inner.length) {
    const eofPos = inner[inner.length - 1]!.end;
    const innerTokens: Token[] = [
      ...inner,
      { type: TokenType.EOF, value: "", start: eofPos, end: eofPos },
    ];
    innerPipeline = parseSimple(innerTokens, result);
  }
  const subsearch: Subsearch = {
    start: lbr.start,
    end: rbr.end,
    pipeline: innerPipeline,
  };
  const remaining = argTokens.slice(0, bracketStart).concat(argTokens.slice(bracketEnd + 1));
  return [subsearch, remaining];
}

export function scanSearchKvOptions(searchTokens: Token[]): Record<string, unknown> {
  const keys = new Set(["index", "sourcetype", "host", "source", "earliest", "latest"]);
  const out: Record<string, unknown> = {};
  let k = 0;
  while (k < searchTokens.length) {
    const tok = searchTokens[k]!;
    if (tok.type === TokenType.IDENTIFIER && keys.has(tok.value.toLowerCase())) {
      if (k + 1 < searchTokens.length && searchTokens[k + 1]!.type === TokenType.EQ) {
        const key = tok.value;
        const vIdx = k + 2;
        if (vIdx >= searchTokens.length) break;
        const v = searchTokens[vIdx]!;
        if (v.type === TokenType.STRING) {
          out[key] = v.value;
          k = vIdx + 1;
          continue;
        }
        if (v.type === TokenType.NUMBER) {
          try {
            out[key] = !v.value.includes(".") ? parseInt(v.value, 10) : parseFloat(v.value);
          } catch {
            out[key] = v.value;
          }
          k = vIdx + 1;
          continue;
        }
        if (v.type === TokenType.MINUS || v.type === TokenType.PLUS) {
          const sign = v.value;
          if (
            vIdx + 1 < searchTokens.length &&
            (searchTokens[vIdx + 1]!.type === TokenType.NUMBER ||
              searchTokens[vIdx + 1]!.type === TokenType.IDENTIFIER)
          ) {
            out[key] = sign + searchTokens[vIdx + 1]!.value;
            k = vIdx + 2;
            continue;
          }
          out[key] = sign;
          k = vIdx + 1;
          continue;
        }
        if (v.type === TokenType.TRUE) {
          out[key] = true;
          k = vIdx + 1;
          continue;
        }
        if (v.type === TokenType.FALSE) {
          out[key] = false;
          k = vIdx + 1;
          continue;
        }
        if (v.type === TokenType.IDENTIFIER || v.type === TokenType.MACRO) {
          out[key] = v.value;
          k = vIdx + 1;
          continue;
        }
      }
    }
    k += 1;
  }
  return out;
}

export function coalesceDottedIdentifiers(rawTokens: Token[]): (Token | string)[] {
  const out: (Token | string)[] = [];
  let k = 0;
  while (k < rawTokens.length) {
    const t = rawTokens[k]!;
    if (t.type === TokenType.IDENTIFIER) {
      const parts = [t.value];
      let kk = k;
      while (
        kk + 2 < rawTokens.length &&
        rawTokens[kk + 1]!.type === TokenType.DOT &&
        DOTTED_SEGMENT_TYPES.has(rawTokens[kk + 2]!.type)
      ) {
        parts.push(rawTokens[kk + 2]!.value);
        kk += 2;
      }
      if (kk !== k) {
        out.push(parts.join("."));
        k = kk + 1;
        continue;
      }
    }
    out.push(t);
    k += 1;
  }
  return out;
}

export function normalizePositionalArgTokens(rawTokens: Token[]): Token[] {
  const out: Token[] = [];
  let k = 0;
  while (k < rawTokens.length) {
    const t = rawTokens[k]!;
    if (t.type === TokenType.COMMA) {
      k += 1;
      continue;
    }
    if (t.type === TokenType.MINUS || t.type === TokenType.PLUS) {
      if (k + 1 < rawTokens.length && DOTTED_SEGMENT_TYPES.has(rawTokens[k + 1]!.type)) {
        const nxt = rawTokens[k + 1]!;
        out.push({
          type: TokenType.IDENTIFIER,
          value: t.value + nxt.value,
          start: t.start,
          end: nxt.end,
        });
        k += 2;
        continue;
      }
      k += 1;
      continue;
    }
    out.push(t);
    k += 1;
  }
  return out;
}

export function isPositionalArgToken(tok: Token): boolean {
  return (
    tok.type === TokenType.IDENTIFIER ||
    tok.type === TokenType.STRING ||
    tok.type === TokenType.NUMBER ||
    tok.type === TokenType.STAR ||
    tok.type === TokenType.MACRO
  );
}

export function isCommandKeyword(tokenType: TokenType): boolean {
  return tokenType === TokenType.WHERE;
}

export function appendMissingPipeError(result: ValidationResult, firstLeftover: Token): void {
  if (
    firstLeftover.type === TokenType.IDENTIFIER &&
    isKnownCommand(firstLeftover.value.toLowerCase())
  ) {
    addError(
      result,
      "SPL012",
      `Missing pipe '|' before command '${firstLeftover.value}'`,
      firstLeftover.start,
      firstLeftover.end,
      `Did you forget a pipe '|' before '${firstLeftover.value}'?`,
    );
  }
}
