import type { Command, Pipeline } from "../ast.js";
import type { Expression } from "../parser/expressionTypes.js";
import { getCommand } from "../registry.js";
import { addError, addWarning } from "../models/result.js";
import type { ValidationResult } from "../models/result.js";

const INITIAL_FIELDS = new Set([
  "_time",
  "_raw",
  "_indextime",
  "host",
  "source",
  "sourcetype",
  "index",
]);

export interface FieldFlowStage {
  index: number;
  command: string;
  known_in: boolean;
  known_out: boolean;
  fields_in: ReadonlySet<string>;
  fields_out: ReadonlySet<string>;
  referenced_fields: ReadonlySet<string>;
  added_fields: ReadonlySet<string>;
  removed_fields: ReadonlySet<string>;
  modified_fields: ReadonlySet<string>;
}

function collectFieldRefs(expr: Expression | null | undefined): Set<string> {
  if (!expr) return new Set();
  switch (expr.kind) {
    case "FieldRef":
      return new Set([expr.name]);
    case "Assignment":
      return collectFieldRefs(expr.value);
    case "BinaryOp":
      return new Set([...collectFieldRefs(expr.left), ...collectFieldRefs(expr.right)]);
    case "UnaryOp":
      return collectFieldRefs(expr.operand);
    case "FunctionCall": {
      const out = new Set<string>();
      for (const a of expr.args) {
        for (const x of collectFieldRefs(a)) out.add(x);
      }
      return out;
    }
    default:
      return new Set();
  }
}

function getReferencedFields(cmd: Command): Set<string> {
  const fields = new Set<string>();
  const cmdName = cmd.name.toLowerCase();

  if (cmdName === "sort") {
    for (const arg of cmd.args) {
      const v = arg.value;
      if (typeof v === "string") {
        const field = v.replace(/^[-+]+/, "");
        if (field) fields.add(field);
      }
    }
    for (const val of Object.values(cmd.options)) {
      if (typeof val === "string" && !val.startsWith("-") && !val.startsWith("+")) {
        fields.add(val);
      }
    }
  } else if (cmdName === "where") {
    for (const arg of cmd.args) {
      const v = arg.value;
      if (v && typeof v === "object" && "kind" in v) {
        for (const f of collectFieldRefs(v as Expression)) fields.add(f);
      }
    }
  } else if (cmdName === "eval") {
    for (const arg of cmd.args) {
      const v = arg.value;
      if (v && typeof v === "object" && "kind" in v && (v as Expression).kind === "Assignment") {
        const asg = v as import("../parser/expressionTypes.js").Assignment;
        for (const f of collectFieldRefs(asg.value)) fields.add(f);
      }
    }
  } else if (cmdName === "table") {
    for (const arg of cmd.args) {
      if (typeof arg.value === "string") fields.add(arg.value);
    }
  } else if (cmdName === "fields") {
    for (const arg of cmd.args) {
      if (typeof arg.value === "string") {
        const field = arg.value.replace(/^[-+]+/, "");
        if (field) fields.add(field);
      }
    }
  } else if (["stats", "chart", "timechart", "eventstats", "streamstats"].includes(cmdName)) {
    const by = cmd.clauses.BY;
    if (by?.fields) for (const f of by.fields) fields.add(f);
    const over = cmd.clauses.OVER;
    if (over?.fields) for (const f of over.fields) fields.add(f);
  } else if (cmdName === "top" || cmdName === "rare") {
    for (const arg of cmd.args) {
      if (typeof arg.value === "string") {
        const v = arg.value.trim();
        if (!v || ["BY", "OVER", "AS"].includes(v.toUpperCase())) continue;
        if (/^\d+$/.test(v)) continue;
        if (v.includes("=")) continue;
        fields.add(v.replace(/^[-+]+/, ""));
      }
    }
  } else if (cmdName === "bin") {
    for (const arg of cmd.args) {
      if (typeof arg.value === "string") {
        const v = arg.value.trim();
        if (v && !v.includes("=")) {
          fields.add(v.replace(/^[-+]+/, ""));
          break;
        }
      }
    }
  }

  return fields;
}

function applyFieldsCommand(cmd: Command, available: Set<string>): Set<string> {
  const raw: string[] = [];
  for (const arg of cmd.args) {
    if (typeof arg.value === "string") raw.push(arg.value);
  }
  const includes = raw.filter((v) => !v.startsWith("-")).map((v) => v.replace(/^\+/, ""));
  const excludes = raw.filter((v) => v.startsWith("-")).map((v) => v.slice(1));
  let out = new Set(available);
  if (includes.length) out = new Set(includes);
  for (const e of excludes) out.delete(e);
  return out;
}

function applyTableCommand(cmd: Command): Set<string> {
  const fields = new Set<string>();
  for (const arg of cmd.args) {
    if (typeof arg.value === "string") {
      fields.add(arg.value.replace(/^[-+]+/, ""));
    }
  }
  return fields;
}

function getStatsOutputFields(cmd: Command): Set<string> {
  const fields = new Set<string>();
  const by = cmd.clauses.BY;
  if (by?.fields) for (const f of by.fields) fields.add(f);
  const over = cmd.clauses.OVER;
  if (over?.fields) for (const f of over.fields) fields.add(f);
  if (cmd.name.toLowerCase() === "timechart") fields.add("_time");

  if (cmd.aggregations.length) {
    for (const agg of cmd.aggregations) {
      if (agg.alias) {
        fields.add(agg.alias);
        continue;
      }
      if (agg.agg_field) {
        fields.add(`${agg.function}(${agg.agg_field})`);
      } else {
        fields.add(agg.function);
      }
    }
  } else {
    for (let i = 0; i < cmd.args.length; i++) {
      const val = cmd.args[i]!.value;
      if (typeof val === "string" && val.toUpperCase() === "AS" && i + 1 < cmd.args.length) {
        const nxt = cmd.args[i + 1]!.value;
        if (typeof nxt === "string") fields.add(nxt);
      }
    }
  }

  for (const [key, val] of Object.entries(cmd.options)) {
    if (key.toUpperCase() === "AS" && typeof val === "string") fields.add(val);
  }

  if (cmd.name.toLowerCase() === "top" || cmd.name.toLowerCase() === "rare") {
    fields.add("count");
    fields.add("percent");
    for (const arg of cmd.args) {
      if (typeof arg.value === "string") {
        const v = arg.value.trim();
        if (!v || /^\d+$/.test(v) || v.includes("=")) continue;
        fields.add(v.replace(/^[-+]+/, ""));
      }
    }
  }

  return fields;
}

function getEvalCreatedFields(cmd: Command): Set<string> {
  const fields = new Set<string>();
  for (const arg of cmd.args) {
    const v = arg.value;
    if (v && typeof v === "object" && "kind" in v && (v as Expression).kind === "Assignment") {
      const fn = (v as import("../parser/expressionTypes.js").Assignment).field_name;
      if (fn && !fn.startsWith("_")) fields.add(fn);
    }
  }
  for (const key of Object.keys(cmd.options)) {
    if (!key.startsWith("_")) fields.add(key);
  }
  return fields;
}

function getRexCreatedFields(cmd: Command): Set<string> {
  const fields = new Set<string>();
  const re = /\(\?<([^>]+)>/g;
  for (const arg of cmd.args) {
    if (typeof arg.value === "string") {
      let m: RegExpExecArray | null;
      while ((m = re.exec(arg.value)) !== null) {
        fields.add(m[1]!);
      }
    }
  }
  return fields;
}

function getRenamePairs(cmd: Command): [string, string][] {
  const raw: string[] = [];
  for (const arg of cmd.args) {
    if (typeof arg.value === "string") raw.push(arg.value);
  }
  const out: [string, string][] = [];
  let i = 0;
  while (i + 2 < raw.length) {
    const old = raw[i]!;
    const mid = raw[i + 1]!;
    const newName = raw[i + 2]!;
    if (mid.toUpperCase() === "AS") {
      out.push([old, newName]);
      i += 3;
    } else {
      i += 1;
    }
  }
  return out;
}

export function computeFieldFlow(
  pipeline: Pipeline,
  schemaFields?: Set<string> | null,
  conservativeUnknown = true,
): FieldFlowStage[] {
  let availableFields = new Set(INITIAL_FIELDS);
  let known = schemaFields != null;
  if (schemaFields) {
    for (const f of schemaFields) availableFields.add(f);
  }

  const stages: FieldFlowStage[] = [];

  for (let idx = 0; idx < pipeline.commands.length; idx++) {
    const cmd = pipeline.commands[idx]!;
    const cmdName = cmd.name.toLowerCase();
    const cmdDef = getCommand(cmdName);
    const referenced = getReferencedFields(cmd);
    const knownIn = known;
    const fieldsIn = new Set(availableFields);
    const added = new Set<string>();
    const removed = new Set<string>();
    const modified = new Set<string>();

    if (["stats", "chart", "timechart", "top", "rare"].includes(cmdName)) {
      const newFields = getStatsOutputFields(cmd);
      for (const f of availableFields) {
        if (!newFields.has(f)) removed.add(f);
      }
      for (const f of newFields) {
        if (!availableFields.has(f)) added.add(f);
      }
      availableFields = newFields;
      known = true;
    } else if (cmdName === "eventstats" || cmdName === "streamstats") {
      const newFields = getStatsOutputFields(cmd);
      for (const f of newFields) {
        if (!availableFields.has(f)) added.add(f);
      }
      availableFields = new Set([...availableFields, ...newFields]);
    } else if (cmdName === "eval") {
      const created = getEvalCreatedFields(cmd);
      for (const f of created) {
        if (availableFields.has(f)) modified.add(f);
        else added.add(f);
      }
      availableFields = new Set([...availableFields, ...created]);
    } else if (cmdName === "fields") {
      const raw: string[] = [];
      for (const arg of cmd.args) {
        if (typeof arg.value === "string") raw.push(arg.value);
      }
      const hasWildcard = raw.some((v) => v.includes("*"));
      const includes = raw.filter((v) => !v.startsWith("-")).map((v) => v.replace(/^\+/, ""));
      const before = new Set(availableFields);
      availableFields = applyFieldsCommand(cmd, availableFields);
      for (const f of before) {
        if (!availableFields.has(f)) removed.add(f);
      }
      for (const f of availableFields) {
        if (!before.has(f)) added.add(f);
      }
      if (includes.length && !raw.some((v) => v.startsWith("+"))) {
        known = !hasWildcard;
      } else {
        known = known && !hasWildcard;
      }
    } else if (cmdName === "table") {
      const before = new Set(availableFields);
      availableFields = applyTableCommand(cmd);
      for (const f of before) {
        if (!availableFields.has(f)) removed.add(f);
      }
      for (const f of availableFields) {
        if (!before.has(f)) added.add(f);
      }
      const hasWildcard = [...availableFields].some((f) => f.includes("*"));
      known = !hasWildcard;
    } else if (cmdName === "rename") {
      const pairs = getRenamePairs(cmd);
      for (const [old, newName] of pairs) {
        if (availableFields.has(old)) {
          availableFields.delete(old);
          availableFields.add(newName);
          removed.add(old);
          added.add(newName);
        } else {
          availableFields.add(newName);
          added.add(newName);
        }
      }
    } else if (cmdName === "rex") {
      const created = getRexCreatedFields(cmd);
      for (const f of created) {
        if (!availableFields.has(f)) added.add(f);
      }
      for (const f of created) availableFields.add(f);
    } else if (cmdName === "lookup") {
      if (conservativeUnknown && known) known = false;
    } else if (cmdDef === undefined || cmdName === "macro") {
      if (conservativeUnknown && known) known = false;
    }

    const knownOut = known;
    const fieldsOut = new Set(availableFields);

    stages.push({
      index: idx,
      command: cmd.name,
      known_in: knownIn,
      known_out: knownOut,
      fields_in: fieldsIn,
      fields_out: fieldsOut,
      referenced_fields: referenced,
      added_fields: added,
      removed_fields: removed,
      modified_fields: modified,
    });
  }

  return stages;
}

export function trackFields(
  pipeline: Pipeline,
  result: ValidationResult,
  options?: {
    schemaFields?: Set<string> | null;
    schemaMissingSeverity?: "error" | "warning";
    conservativeUnknown?: boolean;
  },
): void {
  const schemaFields = options?.schemaFields;
  let missingSev = options?.schemaMissingSeverity ?? "error";
  if (missingSev !== "error" && missingSev !== "warning") missingSev = "error";
  const conservative = options?.conservativeUnknown ?? true;

  const stages = computeFieldFlow(pipeline, schemaFields, conservative);
  const strictMissing = schemaFields != null;

  for (const stage of stages) {
    const cmd = pipeline.commands[stage.index]!;
    if (!strictMissing && stage.index === 0) continue;

    const available = stage.fields_in;
    for (const field of stage.referenced_fields) {
      if (field.startsWith("_") || field.includes("*")) continue;
      if (available.has(field)) continue;

      const sug = `Available fields include: ${[...available].sort().slice(0, 5).join(", ")}...`;
      if (strictMissing && stage.known_in && missingSev === "error") {
        addError(result, "FLD001", `Field '${field}' does not exist in the current dataset/schema.`, cmd.start, cmd.end, sug);
      } else {
        addWarning(result, "FLD001", `Field '${field}' may not exist. Check spelling.`, cmd.start, cmd.end, sug);
      }
    }
  }
}
