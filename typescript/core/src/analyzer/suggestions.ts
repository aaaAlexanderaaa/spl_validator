import type { Command, Pipeline } from "../ast.js";
import { addWarning } from "../models/result.js";
import type { ValidationResult } from "../models/result.js";

const FILTERING_COMMANDS = new Set(["where", "search", "regex"]);
const EXTRACTION_COMMANDS = new Set(["rex", "spath", "xmlkv", "multikv"]);

function firstIntArg(cmd: Command): number | null {
  for (const a of cmd.args) {
    const v = a.value;
    if (typeof v === "number" && Number.isInteger(v)) return v;
    if (typeof v === "string") {
      const n = parseInt(v, 10);
      if (!Number.isNaN(n)) return n;
    }
  }
  return null;
}

function sortLimit(cmd: Command): number | null {
  if ("limit" in cmd.options) {
    const v = cmd.options["limit"];
    if (typeof v === "number") return v;
    if (typeof v === "string") {
      const n = parseInt(v, 10);
      return Number.isNaN(n) ? null : n;
    }
    return null;
  }
  return firstIntArg(cmd);
}

function headLimit(cmd: Command): number {
  const lim = cmd.options["limit"];
  if (typeof lim === "number") return lim;
  const cnt = cmd.options["count"];
  if (typeof cnt === "number") return cnt;
  return firstIntArg(cmd) ?? 10;
}

function findConsecutiveRuns(lowerNames: string[], target: string): [number, number][] {
  const runs: [number, number][] = [];
  let runStart: number | null = null;
  for (let i = 0; i < lowerNames.length; i++) {
    if (lowerNames[i] === target) {
      if (runStart === null) runStart = i;
    } else {
      if (runStart !== null && i - runStart >= 2) runs.push([runStart, i - 1]);
      runStart = null;
    }
  }
  if (runStart !== null && lowerNames.length - runStart >= 2) runs.push([runStart, lowerNames.length - 1]);
  return runs;
}

export function checkSuggestions(pipeline: Pipeline, result: ValidationResult): void {
  const cmds = pipeline.commands;
  const lowerNames = cmds.map((c) => c.name.toLowerCase());
  const statsCount = lowerNames.filter((n) => n === "stats").length;

  for (const [runStart, runEnd] of findConsecutiveRuns(lowerNames, "eval")) {
    const count = runEnd - runStart + 1;
    const first = cmds[runStart]!;
    const last = cmds[runEnd]!;
    addWarning(
      result,
      "BEST008",
      `${count} consecutive eval commands (lines ${first.start.line}\u2013${last.start.line}) could be combined into one`,
      first.start,
      last.end,
      "Use: `| eval field1=..., field2=..., field3=...` (comma-separated assignments).",
    );
  }

  for (let i = 0; i < cmds.length; i++) {
    const cmd = cmds[i]!;
    const cmdName = lowerNames[i]!;
    const prevCmd = i > 0 ? lowerNames[i - 1]! : "";
    const nextCmd = i + 1 < lowerNames.length ? lowerNames[i + 1]! : "";

    if (cmdName === "dedup" && i > 0 && prevCmd !== "sort") {
      addWarning(
        result,
        "BEST001",
        "dedup without a preceding sort may give non-deterministic results",
        cmd.start,
        cmd.end,
        "Add `| sort -_time` (or another stable ordering) before `| dedup ...`.",
      );
    }

    if (cmdName === "join" && !("type" in cmd.options)) {
      addWarning(
        result,
        "BEST002",
        "join without explicit type= defaults to an inner join",
        cmd.start,
        cmd.end,
        "Specify `type=inner` or `type=left` explicitly for clarity.",
      );
    }

    if (cmdName === "transaction") {
      const hasBounds = ["maxspan", "maxpause", "maxevents"].some((k) => k in cmd.options);
      if (!hasBounds) {
        addWarning(
          result,
          "BEST003",
          "transaction without maxspan/maxpause/maxevents may consume excessive memory",
          cmd.start,
          cmd.end,
          "Add bounds like `maxspan=30m` and/or `maxevents=<N>` to cap work.",
        );
      }
    }

    if (cmdName === "stats" && statsCount > 1 && cmd === cmds[cmds.length - 1]) {
      addWarning(
        result,
        "BEST004",
        "Multiple stats commands in one pipeline may be inefficient",
        cmd.start,
        cmd.end,
        "Consider combining aggregations into a single `stats` when possible.",
      );
    }

    if (cmdName === "sort" && nextCmd === "head") {
      const sortN = sortLimit(cmd);
      const headN = headLimit(cmds[i + 1]!);
      if (sortN === null) {
        addWarning(
          result,
          "BEST005",
          "sort followed by head may sort far more data than needed",
          cmd.start,
          cmd.end,
          `Use a limited sort: \`| sort ${headN} - <field>\` (or \`limit=${headN}\`) before \`| head ${headN}\`.`,
        );
      }
    }

    if (cmdName === "sort") {
      const sortN = sortLimit(cmd);
      if (sortN === 0) {
        addWarning(
          result,
          "BEST006",
          "sort limit=0 requests an unlimited sort, which can be very expensive",
          cmd.start,
          cmd.end,
          "Avoid unlimited sorts; aggregate first, or use a small `sort <N>` for top-N use cases.",
        );
      } else if (sortN === null && nextCmd !== "head") {
        addWarning(
          result,
          "BEST006",
          "sort without an explicit limit can be expensive on large result sets",
          cmd.start,
          cmd.end,
          "Prefer `sort <N> ...`, or aggregate first (stats/timechart), then sort the smaller dataset.",
        );
      }
    }

    if (cmdName === "table") {
      if (cmd.args.some((a) => a.value === "*")) {
        addWarning(
          result,
          "BEST007",
          "table * returns every field and can waste CPU/memory/network",
          cmd.start,
          cmd.end,
          "Use `fields <needed_fields>` early, and `table <needed_fields>` only at the end.",
        );
      }
    }

    if (EXTRACTION_COMMANDS.has(cmdName)) {
      const laterFilter = lowerNames.slice(i + 1).some((n) => FILTERING_COMMANDS.has(n));
      if (laterFilter) {
        addWarning(
          result,
          "BEST009",
          `${cmd.name} before filtering may do expensive per-event work on more data than necessary`,
          cmd.start,
          cmd.end,
          "If your later filters don't depend on extracted fields, move filtering earlier (base search or `where`) before running extractions.",
        );
      }
    }

    if (cmdName === "mvexpand") {
      addWarning(
        result,
        "BEST013",
        "mvexpand can multiply event count and memory usage",
        cmd.start,
        cmd.end,
        "Filter and reduce fields first; avoid mvexpand unless you truly need 1 event per MV value.",
      );
    }

    if (cmdName === "spath") {
      addWarning(
        result,
        "BEST014",
        "spath can be expensive on large event sets (JSON parsing per event)",
        cmd.start,
        cmd.end,
        "Filter early and extract only the paths you need (use `path=`/`output=`).",
      );
    }

    if (cmdName === "join") {
      addWarning(
        result,
        "BEST010",
        "join is often resource-intensive and can hit subsearch limits",
        cmd.start,
        cmd.end,
        "Prefer `lookup` for enrichment or `stats`-based correlation when possible; keep subsearch output small (fields/table/return/head).",
      );
    }

    if (cmdName === "search") {
      for (const a of cmd.args) {
        const v = a.value;
        if (typeof v === "string" && v.length > 2 && v.startsWith("*") && v.endsWith("*")) {
          addWarning(
            result,
            "BEST016",
            "Wildcard terms like *foo* can be slow because they are hard to optimize",
            cmd.start,
            cmd.end,
            "Prefer exact terms or left-anchored patterns when possible; filter with indexed fields early.",
          );
          break;
        }
      }
    }
  }
}
