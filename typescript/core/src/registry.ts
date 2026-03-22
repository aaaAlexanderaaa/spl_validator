import registryData from "./generated/registryData.js";

export interface CommandDefJson {
  name: string;
  type: string;
  required_args: string[];
  optional_args: Record<string, string>;
  clauses: string[];
  limit_key: string | null;
  semantic_key: string | null;
  filters_events: boolean;
}

export interface FunctionDefJson {
  name: string;
  min_args: number;
  max_args: number | null;
  context: string;
  category: string;
  syntax: string;
}

const data = registryData as unknown as {
  commands: Record<string, CommandDefJson>;
  commandAliases: Record<string, string>;
  generatingCommands: string[];
  functions: Record<string, FunctionDefJson>;
  statsArityOverrides: Record<string, FunctionDefJson>;
  evalExpressionCommands: string[];
  statsAggregationCommands: string[];
};

const GENERATING_SET = new Set(data.generatingCommands.map((s) => s.toLowerCase()));
const EVAL_EXPR_SET = new Set(data.evalExpressionCommands.map((s) => s.toLowerCase()));
const STATS_AGG_SET = new Set(data.statsAggregationCommands.map((s) => s.toLowerCase()));

/** Optional pack-registered commands (Python tests mutate these; TS keeps stub). */
const extraCommands: Record<string, CommandDefJson> = {};
const packAliases: Record<string, string> = {};

export function resetRegistryPacks(): void {
  for (const k of Object.keys(extraCommands)) delete extraCommands[k];
  for (const k of Object.keys(packAliases)) delete packAliases[k];
}

function canonicalCommandName(key: string): string {
  const k = key.toLowerCase();
  if (data.commandAliases[k]) return data.commandAliases[k]!;
  if (packAliases[k]) return packAliases[k]!;
  return k;
}

export function getCommand(name: string): CommandDefJson | undefined {
  const canonical = canonicalCommandName(name.toLowerCase());
  return data.commands[canonical] ?? extraCommands[canonical];
}

export function isGeneratingCommand(name: string): boolean {
  const cmd = getCommand(name);
  return cmd !== undefined && cmd.type === "generating";
}

export function isKnownCommand(name: string): boolean {
  const canonical = canonicalCommandName(name.toLowerCase());
  return canonical in data.commands || canonical in extraCommands;
}

const PERCENTILE_PATTERN = /^(perc|p|exactperc|upperperc)(\d+)$/i;

export function getFunction(name: string, context?: string): FunctionDefJson | undefined {
  const key = name.toLowerCase();

  if (context === "stats" && data.statsArityOverrides[key]) {
    return data.statsArityOverrides[key];
  }

  const func = data.functions[key];
  if (func) {
    if (context === "eval" && func.context !== "eval" && func.context !== "both") return undefined;
    if (context === "stats" && func.context !== "stats" && func.context !== "both") return undefined;
    return func;
  }

  if (context === undefined || context === "stats") {
    const m = PERCENTILE_PATTERN.exec(name);
    if (m) {
      const percentile = parseInt(m[2]!, 10);
      if (percentile >= 0 && percentile <= 100) {
        return {
          name: key,
          min_args: 1,
          max_args: 1,
          context: "stats",
          category: "statistical",
          syntax: `${m[1]!.toLowerCase()}<0-100>(<field>)`,
        };
      }
    }
  }

  return undefined;
}

export function isKnownFunction(name: string): boolean {
  return getFunction(name) !== undefined;
}

export function validateFunctionArity(
  name: string,
  argCount: number,
  context?: string,
): string | undefined {
  const anyCtx = getFunction(name);
  if (anyCtx === undefined) return undefined;
  const func = getFunction(name, context);
  if (func === undefined) return undefined;

  if (argCount < func.min_args) {
    if (func.min_args === func.max_args) {
      return `Function '${name}' requires exactly ${func.min_args} argument(s), got ${argCount}`;
    }
    return `Function '${name}' requires at least ${func.min_args} argument(s), got ${argCount}`;
  }
  if (func.max_args !== null && argCount > func.max_args) {
    return `Function '${name}' accepts at most ${func.max_args} argument(s), got ${argCount}`;
  }
  return undefined;
}

export function validateFunctionContext(name: string, context: string): string | undefined {
  if (getFunction(name) === undefined) return undefined;
  if (getFunction(name, context) === undefined) {
    return `Function '${name}' cannot be used in ${context} context`;
  }
  return undefined;
}

export function evalExpressionCommands(): ReadonlySet<string> {
  return EVAL_EXPR_SET;
}

export function statsAggregationCommands(): ReadonlySet<string> {
  return STATS_AGG_SET;
}

export function generatingCommandsSet(): ReadonlySet<string> {
  return GENERATING_SET;
}
