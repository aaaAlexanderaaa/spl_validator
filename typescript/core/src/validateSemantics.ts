import type { Command, Pipeline } from "./ast.js";
import { addWarning } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";
import { getCommand } from "./registry.js";
import { getSemanticWarning } from "./analyzer/limitsSemantic.js";

const AGG_COMMANDS = new Set(["stats", "chart", "timechart", "eventstats", "streamstats"]);

export function validateSemantics(pipeline: Pipeline, result: ValidationResult): void {
  const byClauses: { cmd: Command; fieldsStr: string }[] = [];
  const filterCmds: Command[] = [];
  const semKeyHits = new Map<string, { cmd: Command; msg: string; sug?: string }[]>();

  for (const cmd of pipeline.commands) {
    const cmdDef = getCommand(cmd.name);
    if (!cmdDef) continue;
    const cmdName = cmd.name.toLowerCase();

    if (AGG_COMMANDS.has(cmdName)) {
      const by = cmd.clauses.BY;
      if (by?.fields?.length) {
        byClauses.push({ cmd, fieldsStr: by.fields.join(", ") });
      }
    }

    if (cmdDef.semantic_key) {
      let skip = false;
      if (cmdDef.semantic_key === "by_clause_excludes") {
        const by = cmd.clauses.BY;
        if (by?.fields?.length) skip = true;
      }
      if (!skip) {
        const w = getSemanticWarning(cmdDef.semantic_key);
        if (w) {
          const code = `SEM-${cmdName.slice(0, 3).toUpperCase()}`;
          if (!semKeyHits.has(code)) semKeyHits.set(code, []);
          semKeyHits.get(code)!.push({ cmd, msg: w.message, sug: w.suggestion });
        }
      }
    }

    if (cmdDef.filters_events && !cmdDef.semantic_key) {
      filterCmds.push(cmd);
    }
  }

  if (byClauses.length === 1) {
    const { cmd, fieldsStr } = byClauses[0]!;
    addWarning(
      result, "SEM-BY",
      `${cmd.name} BY ${fieldsStr}: Events where '${fieldsStr}' is null/missing are EXCLUDED.`,
      cmd.start, cmd.end,
      `Use 'fillnull ${fieldsStr}' before ${cmd.name} to include missing values.`,
    );
  } else if (byClauses.length > 1) {
    const parts = byClauses.map((b) => `${b.cmd.name} BY ${b.fieldsStr} (line ${b.cmd.start.line})`);
    const allFields = [...new Map(byClauses.flatMap((b) => b.fieldsStr.split(", ").map((f) => [f, f] as [string, string]))).keys()];
    addWarning(
      result, "SEM-BY",
      `${byClauses.length} aggregation commands use BY clauses \u2014 events with null BY fields are excluded: ${parts.join("; ")}`,
      byClauses[0]!.cmd.start, byClauses[byClauses.length - 1]!.cmd.end,
      `Use 'fillnull ${allFields.slice(0, 5).join(", ")}' before aggregations to include missing values.`,
    );
  }

  for (const [code, hits] of semKeyHits) {
    if (hits.length === 1) {
      const { cmd, msg, sug } = hits[0]!;
      addWarning(result, code, `${cmd.name}: ${msg}`, cmd.start, cmd.end, sug);
    } else {
      const names = hits.map((h) => `${h.cmd.name} (line ${h.cmd.start.line})`).join(", ");
      const { msg, sug } = hits[0]!;
      addWarning(result, code, `${hits.length} commands: ${msg} \u2014 at ${names}`, hits[0]!.cmd.start, hits[hits.length - 1]!.cmd.end, sug);
    }
  }

  if (filterCmds.length === 1) {
    const cmd = filterCmds[0]!;
    addWarning(result, "SEM-FLT", `${cmd.name}: This command FILTERS (removes) events from results.`, cmd.start, cmd.end);
  } else if (filterCmds.length > 1) {
    const names = filterCmds.map((c) => `${c.name} (line ${c.start.line})`).join(", ");
    addWarning(result, "SEM-FLT", `${filterCmds.length} commands filter/remove events: ${names}`, filterCmds[0]!.start, filterCmds[filterCmds.length - 1]!.end);
  }
}
