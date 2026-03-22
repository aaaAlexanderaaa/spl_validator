import type { Position } from "../tokens.js";

export interface ExpressionBase {
  start: Position;
  end: Position;
}

export interface BinaryOp extends ExpressionBase {
  kind: "BinaryOp";
  left: Expression;
  operator: string;
  right: Expression;
}

export interface UnaryOp extends ExpressionBase {
  kind: "UnaryOp";
  operator: string;
  operand: Expression;
}

export interface FunctionCall extends ExpressionBase {
  kind: "FunctionCall";
  name: string;
  args: Expression[];
}

export interface FieldRef extends ExpressionBase {
  kind: "FieldRef";
  name: string;
}

export interface Literal extends ExpressionBase {
  kind: "Literal";
  value: unknown;
  type: string;
}

export interface Assignment extends ExpressionBase {
  kind: "Assignment";
  field_name: string;
  value: Expression;
}

export type Expression =
  | BinaryOp
  | UnaryOp
  | FunctionCall
  | FieldRef
  | Literal
  | Assignment;
