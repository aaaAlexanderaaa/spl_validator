import type { Pipeline } from "./ast.js";
import { addWarning } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";
import { getCommand } from "./registry.js";
import { getSemanticWarning } from "./analyzer/limitsSemantic.js";

export function validateSemantics(pipeline: Pipeline, result: ValidationResult): void {
  for (const cmd of pipeline.commands) {
    const cmdDef = getCommand(cmd.name);
    if (!cmdDef) continue;
    const cmdName = cmd.name.toLowerCase();

    if (cmdDef.semantic_key) {
      let skipWarning = false;
      if (cmdDef.semantic_key === "by_clause_excludes") {
        const by = cmd.clauses.BY;
        if (by?.fields?.length) skipWarning = true;
      }
      if (!skipWarning) {
        const w = getSemanticWarning(cmdDef.semantic_key);
        if (w) {
          addWarning(
            result,
            `SEM-${cmdName.slice(0, 3).toUpperCase()}`,
            `${cmd.name}: ${w.message}`,
            cmd.start,
            cmd.end,
            w.suggestion,
          );
        }
      }
    }

    if (["stats", "chart", "timechart", "eventstats", "streamstats"].includes(cmdName)) {
      const byClause = cmd.clauses.BY;
      if (byClause?.fields?.length) {
        const fieldsStr = byClause.fields.join(", ");
        addWarning(
          result,
          "SEM-BY",
          `${cmd.name} BY ${fieldsStr}: Events where '${fieldsStr}' is null/missing are EXCLUDED.`,
          cmd.start,
          cmd.end,
          `Use 'fillnull ${fieldsStr}' before ${cmd.name} to include missing values.`,
        );
      }
    }

    if (cmdDef.filters_events && !cmdDef.semantic_key) {
      addWarning(
        result,
        "SEM-FLT",
        `${cmd.name}: This command FILTERS (removes) events from results.`,
        cmd.start,
        cmd.end,
      );
    }
  }
}
