import type { Command, Pipeline, Subsearch } from "../ast.js";
import { addError, addWarning } from "../models/result.js";
import type { ValidationResult } from "../models/result.js";
import { isGeneratingCommand } from "../registry.js";

export function validateSubsearch(
  parentCmd: Command,
  subsearch: Subsearch,
  result: ValidationResult,
): void {
  if (!subsearch.pipeline || !subsearch.pipeline.commands.length) {
    addError(
      result,
      "SPL022",
      "Empty subsearch - subsearch must contain at least one command",
      subsearch.start,
      subsearch.end,
    );
    return;
  }

  const parent = parentCmd.name.toLowerCase();
  if (parent === "appendpipe" || parent === "foreach") return;

  const firstCmd = subsearch.pipeline.commands[0]!;
  if (!isGeneratingCommand(firstCmd.name)) {
    addError(
      result,
      "SPL021",
      `Subsearch must start with a generating command (search, inputlookup, etc.), got '${firstCmd.name}'`,
      firstCmd.start,
      firstCmd.end,
      "Add 'search' at the beginning of the subsearch",
    );
  }

  const lastCmd = subsearch.pipeline.commands[subsearch.pipeline.commands.length - 1]!;
  const limiting = new Set(["return", "table", "fields", "format", "head"]);
  if (!limiting.has(lastCmd.name.toLowerCase())) {
    addWarning(
      result,
      "BEST010",
      "Subsearch should typically end with return, table, or fields to limit output",
      lastCmd.start,
      lastCmd.end,
      "Consider adding '| return 100 field' or '| table field' at the end",
    );
  }
}

export function validateAllSubsearches(pipeline: Pipeline, result: ValidationResult): void {
  for (const cmd of pipeline.commands) {
    if (cmd.subsearch) {
      validateSubsearch(cmd, cmd.subsearch, result);
    }
  }
}
