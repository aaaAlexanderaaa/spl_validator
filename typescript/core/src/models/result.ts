import type { Position } from "../tokens.js";

export const Severity = {
  ERROR: "error",
  WARNING: "warning",
  INFO: "info",
} as const;

export type Severity = (typeof Severity)[keyof typeof Severity];

export interface ValidationIssue {
  severity: Severity;
  code: string;
  message: string;
  start: Position;
  end: Position;
  suggestion?: string;
}

export interface ValidationResult {
  spl: string;
  is_valid: boolean;
  issues: ValidationIssue[];
  ast: unknown;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  infos: ValidationIssue[];
  /** Lexer input after map/markdown preprocessing (matches Python `_lex_spl`). */
  _lexSpl?: string;
}

export function createValidationResult(spl: string): ValidationResult {
  return {
    spl,
    is_valid: true,
    issues: [],
    ast: null,
    errors: [],
    warnings: [],
    infos: [],
  };
}

export function addError(
  result: ValidationResult,
  code: string,
  message: string,
  start: Position,
  end: Position,
  suggestion?: string,
): void {
  const issue: ValidationIssue = {
    severity: Severity.ERROR,
    code,
    message,
    start,
    end,
    suggestion,
  };
  result.issues.push(issue);
  result.errors.push(issue);
  result.is_valid = false;
}

export function addWarning(
  result: ValidationResult,
  code: string,
  message: string,
  start: Position,
  end: Position,
  suggestion?: string,
): void {
  const issue: ValidationIssue = {
    severity: Severity.WARNING,
    code,
    message,
    start,
    end,
    suggestion,
  };
  result.issues.push(issue);
  result.warnings.push(issue);
}

export function addInfo(
  result: ValidationResult,
  code: string,
  message: string,
  start: Position,
  end: Position,
): void {
  const issue: ValidationIssue = {
    severity: Severity.INFO,
    code,
    message,
    start,
    end,
  };
  result.issues.push(issue);
  result.infos.push(issue);
}
