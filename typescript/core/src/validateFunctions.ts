import type { Pipeline } from "./ast.js";
import type { Expression, FunctionCall } from "./parser/expressionTypes.js";
import { addError } from "./models/result.js";
import type { ValidationResult } from "./models/result.js";
import {
  isKnownFunction,
  validateFunctionArity,
  validateFunctionContext,
} from "./registry.js";

function findFunctionCalls(expr: Expression | null | undefined): FunctionCall[] {
  if (!expr) return [];
  switch (expr.kind) {
    case "FunctionCall": {
      return [expr];
    }
    case "Assignment":
      return findFunctionCalls(expr.value);
    case "BinaryOp":
      return [...findFunctionCalls(expr.left), ...findFunctionCalls(expr.right)];
    case "UnaryOp":
      return findFunctionCalls(expr.operand);
    default:
      return [];
  }
}

function validateSingleFunction(funcCall: FunctionCall, context: string, result: ValidationResult): void {
  if (!isKnownFunction(funcCall.name)) {
    addError(
      result,
      "SPL023",
      `Unknown function '${funcCall.name}'`,
      funcCall.start,
      funcCall.end,
    );
  } else {
    const arityErr = validateFunctionArity(funcCall.name, funcCall.args.length, context);
    if (arityErr) {
      addError(result, "SPL020", arityErr, funcCall.start, funcCall.end);
    }
    const ctxErr = validateFunctionContext(funcCall.name, context);
    if (ctxErr) {
      addError(result, "SPL021", ctxErr, funcCall.start, funcCall.end);
    }
  }
  for (const arg of funcCall.args) {
    if (arg.kind === "FunctionCall") {
      validateSingleFunction(arg, context, result);
    }
  }
}

export function validateFunctions(pipeline: Pipeline, result: ValidationResult): void {
  for (const cmd of pipeline.commands) {
    const cmdName = cmd.name.toLowerCase();
    let context = "eval";
    if (["stats", "chart", "timechart", "eventstats", "streamstats", "top", "rare"].includes(cmdName)) {
      context = "stats";
    }

    for (const arg of cmd.args) {
      const expr = arg.value;
      if (!expr || typeof expr !== "object" || !("kind" in expr)) continue;
      for (const fc of findFunctionCalls(expr as Expression)) {
        validateSingleFunction(fc, context, result);
      }
    }
  }
}
