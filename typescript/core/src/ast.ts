import type { Position } from "./tokens.js";
import type { Expression } from "./parser/expressionTypes.js";

// re-export for consumers
export type { Expression } from "./parser/expressionTypes.js";

export interface Pipeline {
  start: Position;
  end: Position;
  commands: Command[];
}

export interface Subsearch {
  start: Position;
  end: Position;
  pipeline: Pipeline | null;
}

export interface Command {
  start: Position;
  end: Position;
  name: string;
  args: Argument[];
  options: Record<string, unknown>;
  clauses: Record<string, Clause>;
  aggregations: Aggregation[];
  subsearch: Subsearch | null;
}

export interface Argument {
  start: Position;
  end: Position;
  value: unknown;
}

export interface Clause {
  start: Position;
  end: Position;
  keyword: string;
  fields: string[];
  condition?: Expression;
}

export interface Aggregation {
  start: Position;
  end: Position;
  function: string;
  agg_field: string | null;
  args: Expression[];
  alias: string | null;
}

export interface RenamePair {
  start: Position;
  end: Position;
  old_name: string;
  new_name: string;
}
