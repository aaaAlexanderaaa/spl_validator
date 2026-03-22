import { Lexer } from "./lexer.js";
import { TokenType } from "./tokens.js";
import { createValidationResult, addError, addWarning } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";
import { posFromOffset, maskMapSearchStringPayloads, maskMarkdownTripleBackticks } from "./preprocess.js";
import { parseSimple } from "./parseSimple.js";
import { validateSequence } from "./analyzer/sequence.js";
import { validateAllSubsearches } from "./analyzer/subsearch.js";
import { checkSuggestions } from "./analyzer/suggestions.js";
import { trackFields } from "./analyzer/fields.js";
import { validateCommands } from "./validateCommands.js";
import { validateLimits } from "./validateLimits.js";
import { validateFunctions } from "./validateFunctions.js";
import { validateSemantics } from "./validateSemantics.js";

export interface ValidateOptions {
  strict?: boolean;
  schemaFields?: Set<string> | null;
  schemaMissingSeverity?: "error" | "warning";
}

export function validate(spl: string, options?: ValidateOptions): ValidationResult {
  const strict = options?.strict ?? false;
  const result = createValidationResult(spl);

  const [splForLexing, fencedSpans, unclosedFence] = maskMarkdownTripleBackticks(spl);
  if (fencedSpans.length) {
    const [startOff, endOff] = fencedSpans[0]!;
    addWarning(
      result,
      "SPL052",
      "Ignoring markdown fence ```...``` blocks (not SPL syntax)",
      posFromOffset(spl, startOff),
      posFromOffset(spl, endOff),
      "Remove ```...``` from the SPL before running in Splunk.",
    );
  }
  if (unclosedFence) {
    const startOff = spl.indexOf("```");
    const start = posFromOffset(spl, startOff >= 0 ? startOff : 0);
    addError(
      result,
      "SPL011",
      "Unclosed markdown fence ``` (expected closing ```)",
      start,
      start,
      "Add the closing ``` or remove the fence markers.",
    );
    return result;
  }

  const [splMasked, mapPayloadSpans] = maskMapSearchStringPayloads(splForLexing);
  if (mapPayloadSpans.length) {
    const p0 = mapPayloadSpans[0]![0];
    const p1 = mapPayloadSpans[mapPayloadSpans.length - 1]![1] - 1;
    addWarning(
      result,
      "SPL054",
      'Ignoring inner SPL in map search="..." strings (opaque for validation; Splunk still runs each mapped search)',
      posFromOffset(spl, p0),
      posFromOffset(spl, Math.max(p0, p1)),
      "Expand or remove map search strings if you need them validated as SPL.",
    );
  }

  result._lexSpl = splMasked;

  const lexer = new Lexer(splMasked);
  const tokens = lexer.tokenize();

  for (const token of tokens) {
    if (token.type === TokenType.ERROR) {
      if (token.value.startsWith('"') || token.value.startsWith("'")) {
        addError(result, "SPL004", "Unclosed string literal", token.start, token.end, "Add closing quote");
      } else {
        addError(result, "SPL007", `Invalid character: ${JSON.stringify(token.value)}`, token.start, token.end);
      }
    }
  }

  const ast = parseSimple(tokens, result);
  result.ast = ast;

  if (!ast) {
    return result;
  }

  validateSequence(ast, result);
  validateAllSubsearches(ast, result);
  validateCommands(ast, result, strict);
  validateLimits(ast, result);
  validateFunctions(ast, result);
  validateSemantics(ast, result);
  checkSuggestions(ast, result);

  let missingSev = options?.schemaMissingSeverity ?? "error";
  if (missingSev !== "error" && missingSev !== "warning") missingSev = "error";
  trackFields(ast, result, {
    schemaFields: options?.schemaFields,
    schemaMissingSeverity: missingSev,
  });

  return result;
}

export { buildValidationJsonDict } from "./jsonPayload.js";
export { parseWarningGroups, groupWarnings, warningGroup } from "./warningGroups.js";
