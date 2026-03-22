import type { Command, Pipeline } from "./ast.js";
import { addError, addWarning } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";
import { getCommand } from "./registry.js";
import { validateSearchTerms } from "./validateSearch.js";

function hasMeaningfulPositionalArgs(cmd: Command): boolean {
  for (const arg of cmd.args) {
    const value = arg.value;
    if (typeof value !== "string") return true;
    const s = value.trim();
    if (!s) continue;
    if ([...s].every((ch) => !/[a-z0-9*_]/i.test(ch))) continue;
    return true;
  }
  return false;
}

function validateRequiredArguments(cmd: Command, cmdDef: NonNullable<ReturnType<typeof getCommand>>, result: ValidationResult): void {
  const cmdName = cmd.name.toLowerCase();

  if (cmdName === "fieldformat") {
    if (Object.keys(cmd.options).length) return;
    addError(
      result,
      "SPL014",
      `${cmd.name} is missing required arguments (at least one field="format" assignment)`,
      cmd.start,
      cmd.end,
      'Example: | fieldformat total="%$,.2f"',
    );
    return;
  }

  if (!cmdDef.required_args?.length) return;

  if (["eval", "where", "bin"].includes(cmdName)) return;

  if (cmdName === "regex") {
    if (hasMeaningfulPositionalArgs(cmd)) return;
    for (const arg of cmd.args) {
      const v = arg.value;
      if (typeof v === "string" && v.trim()) return;
    }
    if (Object.keys(cmd.options).some((k) => k !== "field")) return;
    addError(
      result,
      "SPL014",
      `${cmd.name} is missing required arguments (${cmdDef.required_args.join(", ")})`,
      cmd.start,
      cmd.end,
    );
    return;
  }

  if (["join", "append", "appendcols"].includes(cmdName) && cmd.subsearch === null) {
    addError(
      result,
      "SPL014",
      `${cmd.name} requires a subsearch in brackets: [...]`,
      cmd.start,
      cmd.end,
      `Example: | ${cmd.name} <fields> [ search index=... ]`,
    );
    return;
  }

  if (hasMeaningfulPositionalArgs(cmd)) return;

  for (const req of cmdDef.required_args) {
    if (req in cmd.options) return;
  }

  addError(
    result,
    "SPL014",
    `${cmd.name} is missing required arguments (${cmdDef.required_args.join(", ")})`,
    cmd.start,
    cmd.end,
  );
}

export function validateCommands(pipeline: Pipeline, result: ValidationResult, strict: boolean): void {
  for (let idx = 0; idx < pipeline.commands.length; idx++) {
    const cmd = pipeline.commands[idx]!;
    const cmdDef = getCommand(cmd.name);

    if (!cmdDef) {
      if (strict) {
        addError(result, "SPL013", `Unknown command '${cmd.name}'`, cmd.start, cmd.end);
      } else {
        addWarning(
          result,
          "SPL006",
          `Unknown command '${cmd.name}' - validation skipped`,
          cmd.start,
          cmd.end,
        );
      }
      continue;
    }

    validateRequiredArguments(cmd, cmdDef, result);
    if (cmd.name.toLowerCase() === "search") {
      validateSearchTerms(cmd, result, idx === 0);
    }
  }
}
