import type { Command, Pipeline } from "../ast.js";
import { addError } from "../models/result.js";
import type { ValidationResult } from "../models/result.js";
import { pos } from "../tokens.js";

export enum DataState {
  NONE = "no_data",
  EVENTS = "events",
  AGGREGATED = "aggregated",
  ANY = "any",
}

const COMMAND_DATA_FLOW: Record<string, [DataState, DataState]> = {
  search: [DataState.NONE, DataState.ANY],
  makeresults: [DataState.NONE, DataState.EVENTS],
  inputlookup: [DataState.NONE, DataState.EVENTS],
  rest: [DataState.NONE, DataState.EVENTS],
  tstats: [DataState.NONE, DataState.AGGREGATED],
  metadata: [DataState.NONE, DataState.EVENTS],
  datamodel: [DataState.NONE, DataState.EVENTS],
  dbinspect: [DataState.NONE, DataState.EVENTS],
  macro: [DataState.NONE, DataState.ANY],
  eval: [DataState.ANY, DataState.ANY],
  where: [DataState.ANY, DataState.ANY],
  fields: [DataState.ANY, DataState.ANY],
  rename: [DataState.ANY, DataState.ANY],
  rex: [DataState.ANY, DataState.ANY],
  regex: [DataState.ANY, DataState.ANY],
  lookup: [DataState.ANY, DataState.ANY],
  dedup: [DataState.ANY, DataState.ANY],
  head: [DataState.ANY, DataState.ANY],
  tail: [DataState.ANY, DataState.ANY],
  sort: [DataState.ANY, DataState.ANY],
  table: [DataState.ANY, DataState.ANY],
  bin: [DataState.ANY, DataState.ANY],
  eventstats: [DataState.ANY, DataState.ANY],
  streamstats: [DataState.ANY, DataState.ANY],
  spath: [DataState.ANY, DataState.ANY],
  makemv: [DataState.ANY, DataState.ANY],
  mvexpand: [DataState.ANY, DataState.ANY],
  mvcombine: [DataState.ANY, DataState.ANY],
  fillnull: [DataState.ANY, DataState.ANY],
  outputlookup: [DataState.ANY, DataState.ANY],
  collect: [DataState.ANY, DataState.ANY],
  sendemail: [DataState.ANY, DataState.ANY],
  format: [DataState.ANY, DataState.ANY],
  return: [DataState.ANY, DataState.ANY],
  addinfo: [DataState.ANY, DataState.ANY],
  convert: [DataState.ANY, DataState.ANY],
  fieldformat: [DataState.ANY, DataState.ANY],
  replace: [DataState.ANY, DataState.ANY],
  reverse: [DataState.ANY, DataState.ANY],
  xmlkv: [DataState.EVENTS, DataState.EVENTS],
  multikv: [DataState.EVENTS, DataState.EVENTS],
  abstract: [DataState.EVENTS, DataState.EVENTS],
  highlight: [DataState.ANY, DataState.ANY],
  stats: [DataState.ANY, DataState.AGGREGATED],
  chart: [DataState.ANY, DataState.AGGREGATED],
  timechart: [DataState.EVENTS, DataState.AGGREGATED],
  top: [DataState.ANY, DataState.AGGREGATED],
  rare: [DataState.ANY, DataState.AGGREGATED],
  transaction: [DataState.ANY, DataState.ANY],
  untable: [DataState.ANY, DataState.ANY],
  xyseries: [DataState.ANY, DataState.ANY],
  join: [DataState.ANY, DataState.ANY],
  append: [DataState.ANY, DataState.ANY],
  appendcols: [DataState.ANY, DataState.ANY],
  map: [DataState.ANY, DataState.ANY],
};

export function validateSequence(pipeline: Pipeline, result: ValidationResult): void {
  if (!pipeline.commands.length) {
    addError(result, "SPL005", "Empty pipeline - add a search command", pos(1, 1, 0), pos(1, 1, 0));
    return;
  }

  let state = DataState.NONE;
  let lastAggregationCmd: Command | null = null;
  let mutatedSinceAggregation = false;

  for (let i = 0; i < pipeline.commands.length; i++) {
    const cmd = pipeline.commands[i]!;
    const cmdName = cmd.name.toLowerCase();
    const knownFlow = cmdName in COMMAND_DATA_FLOW;
    const flow = COMMAND_DATA_FLOW[cmdName] ?? [DataState.ANY, DataState.ANY];
    const [required, produces] = flow;

    if (i === 0 && required !== DataState.NONE && required !== DataState.ANY) {
      addError(
        result,
        "SPL001",
        `'${cmd.name}' is not a generating command and cannot start a pipeline. Pipeline must start with search, makeresults, inputlookup, or implicit search terms.`,
        cmd.start,
        cmd.end,
      );
    } else if (i === 0 && required === DataState.ANY && knownFlow) {
      addError(
        result,
        "SPL001",
        `'${cmd.name}' requires input data. Pipeline must start with search, makeresults, inputlookup, or similar generating command.`,
        cmd.start,
        cmd.end,
      );
    }

    if (required === DataState.EVENTS && state === DataState.AGGREGATED) {
      if (cmdName !== "bin") {
        addError(
          result,
          "SPL010",
          `'${cmd.name}' requires event data but pipeline is already aggregated. Original event fields are gone after transforming commands.`,
          cmd.start,
          cmd.end,
        );
      }
    }

    if (cmdName === "bin" && state === DataState.AGGREGATED) {
      let targetField: string | null = null;
      for (const a of cmd.args) {
        const v = (a as { value?: unknown }).value;
        if (typeof v === "string") {
          targetField = v;
          break;
        }
      }
      if (!targetField) {
        addError(
          result,
          "SPL011",
          "'bin' requires a target field (commonly _time), but pipeline is already aggregated.",
          cmd.start,
          cmd.end,
        );
      } else if (lastAggregationCmd) {
        const lastName = lastAggregationCmd.name.toLowerCase();
        let available = false;
        if (lastName === "timechart") {
          available = targetField === "_time";
        } else {
          const byClause = lastAggregationCmd.clauses.BY;
          const overClause = lastAggregationCmd.clauses.OVER;
          if (byClause?.fields?.includes(targetField)) available = true;
          if (overClause?.fields?.includes(targetField)) available = true;
        }
        if (!available && !mutatedSinceAggregation) {
          addError(
            result,
            "SPL011",
            `'bin' target field '${targetField}' may not be available after '${lastAggregationCmd.name}'.`,
            cmd.start,
            cmd.end,
          );
        }
      }
    }

    if (cmdName === "rex" && state === DataState.AGGREGATED) {
      const fieldOpt = cmd.options["field"];
      if (!fieldOpt || fieldOpt === "_raw") {
        addError(
          result,
          "SPL010",
          "'rex' requires raw event data with _raw field, but pipeline is already aggregated. _raw and original fields are not available after stats/chart/timechart.",
          cmd.start,
          cmd.end,
        );
      }
    }

    if (cmdName === "spath" && state === DataState.AGGREGATED) {
      const inputOpt = cmd.options["input"];
      if (!inputOpt || inputOpt === "_raw") {
        addError(
          result,
          "SPL010",
          "'spath' requires raw event data with _raw field unless input=<field> is provided, but pipeline is already aggregated.",
          cmd.start,
          cmd.end,
        );
      }
    }

    if (cmdName === "regex" && state === DataState.AGGREGATED) {
      const fieldOpt = cmd.options["field"];
      const hasFieldMatch =
        Object.keys(cmd.options).some((k) => k !== "field") || (fieldOpt && fieldOpt !== "_raw");
      if (!hasFieldMatch) {
        addError(
          result,
          "SPL010",
          "'regex' requires raw event data with _raw field unless a target field is provided, but pipeline is already aggregated.",
          cmd.start,
          cmd.end,
        );
      }
    }

    if (produces !== DataState.ANY) {
      state = produces;
      if (produces === DataState.AGGREGATED) {
        lastAggregationCmd = cmd;
        mutatedSinceAggregation = false;
      } else if (produces === DataState.EVENTS) {
        lastAggregationCmd = null;
        mutatedSinceAggregation = false;
      }
    } else if (state === DataState.NONE) {
      state = DataState.EVENTS;
    }

    if (
      state === DataState.AGGREGATED &&
      ["eval", "rename", "lookup", "rex", "regex", "spath"].includes(cmdName)
    ) {
      mutatedSinceAggregation = true;
    }
  }
}
