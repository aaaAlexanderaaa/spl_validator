import type { ValidationIssue } from "./models/result.js";

export const GROUP_LIMITS = "limits";
export const GROUP_OPTIMIZATION = "optimization";
export const GROUP_STYLE = "style";
export const GROUP_SEMANTIC = "semantic";
export const GROUP_SCHEMA = "schema";
export const GROUP_DIAGNOSTIC = "diagnostic";
export const GROUP_OTHER = "other";

const ALL_GROUPS = new Set([
  GROUP_LIMITS,
  GROUP_OPTIMIZATION,
  GROUP_STYLE,
  GROUP_SEMANTIC,
  GROUP_SCHEMA,
  GROUP_DIAGNOSTIC,
  GROUP_OTHER,
]);

const OPTIMIZATION_CODES = new Set([
  "SPL050",
  "BEST003",
  "BEST004",
  "BEST005",
  "BEST006",
  "BEST007",
  "BEST008",
  "BEST009",
  "BEST010",
  "BEST013",
  "BEST014",
  "BEST016",
]);

const STYLE_CODES = new Set(["BEST001", "BEST002", "BEST011", "BEST012", "BEST015"]);

const DIAGNOSTIC_CODES = new Set(["SPL052", "SPL053"]);

export function warningGroup(issue: ValidationIssue): string {
  const code = issue.code;
  if (code.startsWith("LIM")) return GROUP_LIMITS;
  if (code.startsWith("FLD")) return GROUP_SCHEMA;
  if (code.startsWith("SEM-") || code.startsWith("SEM")) return GROUP_SEMANTIC;
  if (OPTIMIZATION_CODES.has(code)) return GROUP_OPTIMIZATION;
  if (STYLE_CODES.has(code)) return GROUP_STYLE;
  if (DIAGNOSTIC_CODES.has(code)) return GROUP_DIAGNOSTIC;
  if (code.startsWith("SPL")) return GROUP_DIAGNOSTIC;
  if (code.startsWith("BEST")) return GROUP_OTHER;
  return GROUP_OTHER;
}

export function parseWarningGroups(value: string): Set<string> {
  const raw = value.trim().toLowerCase();
  if (raw === "optimization" || raw === "opt") {
    return new Set([GROUP_LIMITS, GROUP_OPTIMIZATION]);
  }
  if (raw === "all") return new Set(ALL_GROUPS);
  if (raw === "none" || raw === "off") return new Set();

  const out = new Set<string>();
  for (let part of raw.split(",").map((p) => p.trim()).filter(Boolean)) {
    if (part === "opt") part = GROUP_OPTIMIZATION;
    if (part === "diag") part = GROUP_DIAGNOSTIC;
    if (part === "sem") part = GROUP_SEMANTIC;
    if (!ALL_GROUPS.has(part)) {
      throw new Error(
        `Unknown warning group '${part}'. Valid groups: ${[...ALL_GROUPS].sort().join(", ")}.`,
      );
    }
    out.add(part);
  }
  return out;
}

export interface WarningGroupSummary {
  limits: ValidationIssue[];
  optimization: ValidationIssue[];
  style: ValidationIssue[];
  semantic: ValidationIssue[];
  schema: ValidationIssue[];
  diagnostic: ValidationIssue[];
  other: ValidationIssue[];
}

export function groupWarnings(
  warnings: Iterable<ValidationIssue>,
  enabledGroups: Set<string>,
): WarningGroupSummary {
  const limits: ValidationIssue[] = [];
  const optimization: ValidationIssue[] = [];
  const style: ValidationIssue[] = [];
  const semantic: ValidationIssue[] = [];
  const schema: ValidationIssue[] = [];
  const diagnostic: ValidationIssue[] = [];
  const other: ValidationIssue[] = [];

  for (const w of warnings) {
    const g = warningGroup(w);
    if (!enabledGroups.has(g)) continue;
    if (g === GROUP_LIMITS) limits.push(w);
    else if (g === GROUP_OPTIMIZATION) optimization.push(w);
    else if (g === GROUP_STYLE) style.push(w);
    else if (g === GROUP_SEMANTIC) semantic.push(w);
    else if (g === GROUP_SCHEMA) schema.push(w);
    else if (g === GROUP_DIAGNOSTIC) diagnostic.push(w);
    else other.push(w);
  }

  return {
    limits,
    optimization,
    style,
    semantic,
    schema,
    diagnostic,
    other,
  };
}
