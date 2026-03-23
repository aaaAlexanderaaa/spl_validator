"""Best-practice and performance suggestions for SPL queries."""

from __future__ import annotations

from typing import Optional

from ..models.result import ValidationResult
from ..parser.ast import Command, Pipeline


_FILTERING_COMMANDS = {"where", "search", "regex"}
_EXTRACTION_COMMANDS = {"rex", "spath", "xmlkv", "multikv"}


def _first_int_arg(cmd: Command) -> Optional[int]:
    for a in cmd.args:
        v = getattr(a, "value", None)
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                continue
    return None


def _sort_limit(cmd: Command) -> Optional[int]:
    # sort supports `limit=<N>` or a leading positional number: `sort <N> - field`.
    if "limit" in cmd.options:
        v = cmd.options.get("limit")
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                # Unparseable limit value - return None rather than falling through
                return None
        # Non-int, non-string limit value - return None
        return None
    return _first_int_arg(cmd)


def _head_limit(cmd: Command) -> int:
    # head defaults to 10 if unspecified.
    if "limit" in cmd.options and isinstance(cmd.options["limit"], int):
        return cmd.options["limit"]
    if "count" in cmd.options and isinstance(cmd.options["count"], int):
        return cmd.options["count"]
    return _first_int_arg(cmd) or 10


def _find_consecutive_runs(lower_names: list[str], target: str) -> list[tuple[int, int]]:
    """Return (start_idx, end_idx) for every run of >=2 consecutive *target* commands."""
    runs: list[tuple[int, int]] = []
    run_start: Optional[int] = None
    for i, name in enumerate(lower_names):
        if name == target:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and i - run_start >= 2:
                runs.append((run_start, i - 1))
            run_start = None
    if run_start is not None and len(lower_names) - run_start >= 2:
        runs.append((run_start, len(lower_names) - 1))
    return runs


def check_suggestions(pipeline: Pipeline, result: ValidationResult) -> None:
    """Add best-practice and optimization warnings based on common SPL patterns."""
    cmds = pipeline.commands
    lower_names = [c.name.lower() for c in cmds]
    stats_count = sum(1 for n in lower_names if n == "stats")

    # BEST008: consecutive evals — emit one warning per run, not per pair
    for run_start, run_end in _find_consecutive_runs(lower_names, "eval"):
        count = run_end - run_start + 1
        first, last = cmds[run_start], cmds[run_end]
        result.add_warning(
            "BEST008",
            f"{count} consecutive eval commands (lines {first.start.line}\u2013{last.start.line}) could be combined into one",
            first.start,
            last.end,
            suggestion="Use: `| eval field1=..., field2=..., field3=...` (comma-separated assignments).",
        )

    for i, cmd in enumerate(cmds):
        cmd_name = lower_names[i]
        prev_cmd = lower_names[i - 1] if i > 0 else ""
        next_cmd = lower_names[i + 1] if i + 1 < len(lower_names) else ""

        # BEST001: dedup without sort (non-deterministic)
        if cmd_name == "dedup" and i > 0 and prev_cmd != "sort":
            result.add_warning(
                "BEST001",
                "dedup without a preceding sort may give non-deterministic results",
                cmd.start,
                cmd.end,
                suggestion="Add `| sort -_time` (or another stable ordering) before `| dedup ...`.",
            )

        # BEST002: join type= should be explicit (style warning, separate from BEST015 performance warning)
        if cmd_name == "join" and "type" not in cmd.options:
            result.add_warning(
                "BEST002",
                "join without explicit type= defaults to an inner join",
                cmd.start,
                cmd.end,
                suggestion="Specify `type=inner` or `type=left` explicitly for clarity.",
            )

        # BEST003: transaction should be bounded (memory safety)
        if cmd_name == "transaction":
            has_bounds = any(k in cmd.options for k in ("maxspan", "maxpause", "maxevents"))
            if not has_bounds:
                result.add_warning(
                    "BEST003",
                    "transaction without maxspan/maxpause/maxevents may consume excessive memory",
                    cmd.start,
                    cmd.end,
                    suggestion="Add bounds like `maxspan=30m` and/or `maxevents=<N>` to cap work.",
                )

        # BEST004: multiple stats can often be combined
        if cmd_name == "stats" and stats_count > 1 and cmd == cmds[-1]:
            result.add_warning(
                "BEST004",
                "Multiple stats commands in one pipeline may be inefficient",
                cmd.start,
                cmd.end,
                suggestion="Consider combining aggregations into a single `stats` when possible.",
            )

        # BEST005: sort followed by head should use a limited sort
        if cmd_name == "sort" and next_cmd == "head":
            sort_n = _sort_limit(cmd)
            head_n = _head_limit(cmds[i + 1])
            if sort_n is None:
                result.add_warning(
                    "BEST005",
                    "sort followed by head may sort far more data than needed",
                    cmd.start,
                    cmd.end,
                    suggestion=f"Use a limited sort: `| sort {head_n} - <field>` (or `limit={head_n}`) before `| head {head_n}`.",
                )

        # BEST006: unlimited or unbounded sort is often expensive
        if cmd_name == "sort":
            sort_n = _sort_limit(cmd)
            if sort_n == 0:
                result.add_warning(
                    "BEST006",
                    "sort limit=0 requests an unlimited sort, which can be very expensive",
                    cmd.start,
                    cmd.end,
                    suggestion="Avoid unlimited sorts; aggregate first, or use a small `sort <N>` for top-N use cases.",
                )
            elif sort_n is None and next_cmd != "head":
                result.add_warning(
                    "BEST006",
                    "sort without an explicit limit can be expensive on large result sets",
                    cmd.start,
                    cmd.end,
                    suggestion="Prefer `sort <N> ...`, or aggregate first (stats/timechart), then sort the smaller dataset.",
                )

        # BEST007: table * is usually a performance and usability anti-pattern
        if cmd_name == "table":
            if any(getattr(a, "value", None) == "*" for a in cmd.args):
                result.add_warning(
                    "BEST007",
                    "table * returns every field and can waste CPU/memory/network",
                    cmd.start,
                    cmd.end,
                    suggestion="Use `fields <needed_fields>` early, and `table <needed_fields>` only at the end.",
                )

        # BEST009: extraction/parsing before filtering tends to be costly
        if cmd_name in _EXTRACTION_COMMANDS:
            later_filter = any(n in _FILTERING_COMMANDS for n in lower_names[i + 1 :])
            if later_filter:
                result.add_warning(
                    "BEST009",
                    f"{cmd.name} before filtering may do expensive per-event work on more data than necessary",
                    cmd.start,
                    cmd.end,
                    suggestion="If your later filters don't depend on extracted fields, move filtering earlier (base search or `where`) before running extractions.",
                )

        # BEST013: mvexpand can multiply event count
        if cmd_name == "mvexpand":
            result.add_warning(
                "BEST013",
                "mvexpand can multiply event count and memory usage",
                cmd.start,
                cmd.end,
                suggestion="Filter and reduce fields first; avoid mvexpand unless you truly need 1 event per MV value.",
            )

        # BEST014: spath can be expensive on large event sets
        if cmd_name == "spath":
            result.add_warning(
                "BEST014",
                "spath can be expensive on large event sets (JSON parsing per event)",
                cmd.start,
                cmd.end,
                suggestion="Filter early and extract only the paths you need (use `path=`/`output=`).",
            )

        # BEST010: join is often slower than lookup/stats-based correlation (performance warning)
        if cmd_name == "join":
            result.add_warning(
                "BEST010",
                "join is often resource-intensive and can hit subsearch limits",
                cmd.start,
                cmd.end,
                suggestion="Prefer `lookup` for enrichment or `stats`-based correlation when possible; keep subsearch output small (fields/table/return/head).",
            )

        # BEST016: wildcard *foo* is hard to optimize
        if cmd_name == "search":
            for a in cmd.args:
                v = getattr(a, "value", None)
                if not isinstance(v, str):
                    continue
                if len(v) > 2 and v.startswith("*") and v.endswith("*"):
                    result.add_warning(
                        "BEST016",
                        "Wildcard terms like *foo* can be slow because they are hard to optimize",
                        cmd.start,
                        cmd.end,
                        suggestion="Prefer exact terms or left-anchored patterns when possible; filter with indexed fields early.",
                    )
                    break
