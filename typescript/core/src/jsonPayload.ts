import type { Pipeline } from "./ast.js";
import type { ValidationResult, ValidationIssue } from "./models/result.js";
import { OUTPUT_JSON_SCHEMA_VERSION, PACKAGE_VERSION } from "./contract.js";
import { groupWarnings, parseWarningGroups } from "./warningGroups.js";

function issueToJson(issue: ValidationIssue) {
  return {
    code: issue.code,
    message: issue.message,
    line: issue.start.line,
    column: issue.start.column,
    suggestion: issue.suggestion,
  };
}

export function buildValidationJsonDict(
  result: ValidationResult,
  _pipeline: Pipeline | null,
  options?: {
    warningGroups?: string;
    debugAst?: unknown;
  },
): Record<string, unknown> {
  const advice = options?.warningGroups ?? "optimization";
  const enabled = parseWarningGroups(advice);
  const grouped = groupWarnings(result.warnings, enabled);
  const filteredWarnings = [
    ...grouped.limits,
    ...grouped.optimization,
    ...grouped.style,
    ...grouped.semantic,
    ...grouped.schema,
    ...grouped.diagnostic,
    ...grouped.other,
  ];

  const output: Record<string, unknown> = {
    output_schema_version: OUTPUT_JSON_SCHEMA_VERSION,
    package_version: PACKAGE_VERSION,
    valid: result.is_valid,
    errors: result.errors.map(issueToJson),
    warnings: filteredWarnings.map(issueToJson),
  };

  if (options?.debugAst !== undefined) {
    output.debug = { ast: options.debugAst };
  }

  return output;
}
