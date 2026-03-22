import type { Command, Pipeline } from "./ast.js";
import { addWarning } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";
import { getCommand } from "./registry.js";
import { getLimit } from "./analyzer/limitsSemantic.js";

export function validateLimits(pipeline: Pipeline, result: ValidationResult): void {
  for (const cmd of pipeline.commands) {
    const cmdDef = getCommand(cmd.name);
    if (!cmdDef?.limit_key) continue;
    const cname = cmd.name.toLowerCase();

    if (cname === "head" || cname === "tail") {
      let hasCount = false;
      if ("limit" in cmd.options || "count" in cmd.options) hasCount = true;
      else {
        for (const a of cmd.args) {
          if (typeof a.value === "string") {
            const n = parseInt(a.value, 10);
            if (!Number.isNaN(n)) {
              hasCount = true;
              break;
            }
          }
        }
      }
      if (hasCount) continue;
    }

    if (cname === "sort") {
      if ("limit" in cmd.options) continue;
      if (cmd.args.length) {
        const a0 = cmd.args[0]!;
        if (typeof a0.value === "string") {
          const n = parseInt(a0.value, 10);
          if (!Number.isNaN(n)) continue;
        }
      }
    }

    if (cname === "transaction" && "maxevents" in cmd.options) continue;
    if (cname === "join" && "max" in cmd.options) continue;
    if ((cname === "append" || cname === "appendcols") && "maxout" in cmd.options) continue;

    const limit = getLimit(cmdDef.limit_key);
    if (limit) {
      const code = `LIM${cmdDef.limit_key.toUpperCase().slice(0, 3)}`;
      addWarning(result, code, `${cmd.name}: ${limit.message}`, cmd.start, cmd.end);
    }
  }
}
