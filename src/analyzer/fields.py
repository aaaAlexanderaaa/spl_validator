"""Field availability tracking across the pipeline.

This module serves two purposes:
- Emit field-missing diagnostics (warnings by default; optionally errors when schema-locked).
- Provide lightweight per-command field-flow stages for debug/visualization.
"""

from dataclasses import dataclass
from typing import Optional, Set
import re
from ..parser.ast import Pipeline, Command
from ..models.result import ValidationResult, Severity
from ..lexer.tokens import Position


# Built-in fields always available at start
INITIAL_FIELDS = {"_time", "_raw", "_indextime", "host", "source", "sourcetype", "index"}


@dataclass(frozen=True)
class FieldFlowStage:
    """A best-effort per-command view of fields and how they change."""

    index: int
    command: str
    known_in: bool
    known_out: bool
    fields_in: frozenset[str]
    fields_out: frozenset[str]
    referenced_fields: frozenset[str]
    added_fields: frozenset[str]
    removed_fields: frozenset[str]
    modified_fields: frozenset[str]


def compute_field_flow(
    pipeline: Pipeline,
    *,
    schema_fields: Optional[set[str]] = None,
    conservative_unknown: bool = True,
) -> list[FieldFlowStage]:
    """Compute best-effort field flow stages (does not emit issues)."""
    from ..registry import get_command

    available_fields: set[str] = INITIAL_FIELDS.copy()
    known = schema_fields is not None
    if schema_fields:
        available_fields = available_fields.union(schema_fields)

    stages: list[FieldFlowStage] = []

    for idx, cmd in enumerate(pipeline.commands):
        cmd_name = cmd.name.lower()
        cmd_def = get_command(cmd_name)

        referenced = _get_referenced_fields(cmd)
        known_in = known
        fields_in = set(available_fields)

        added: set[str] = set()
        removed: set[str] = set()
        modified: set[str] = set()

        # Update available fields based on command output
        if cmd_name in ("stats", "chart", "timechart", "top", "rare"):
            new_fields = _get_stats_output_fields(cmd)
            removed = set(available_fields).difference(new_fields)
            added = set(new_fields).difference(available_fields)
            available_fields = new_fields
            known = True

        elif cmd_name in ("eventstats", "streamstats"):
            new_fields = _get_stats_output_fields(cmd)
            added = set(new_fields).difference(available_fields)
            available_fields = available_fields.union(new_fields)
            # eventstats/streamstats keep the existing structure; knowledge does not improve.

        elif cmd_name == "eval":
            created = _get_eval_created_fields(cmd)
            for f in created:
                if f in available_fields:
                    modified.add(f)  # add-or-modify in SPL
                else:
                    added.add(f)
            available_fields = available_fields.union(created)

        elif cmd_name == "fields":
            # `fields` can either select fields (making the set exact) or modify it (+/-).
            raw: list[str] = []
            for arg in cmd.args:
                if hasattr(arg, "value") and isinstance(arg.value, str):
                    raw.append(arg.value)
            has_wildcard = any("*" in v for v in raw)
            includes = [v.lstrip("+") for v in raw if not v.startswith("-")]
            excludes = [v[1:] for v in raw if v.startswith("-")]

            before = set(available_fields)
            available_fields = _apply_fields_command(cmd, available_fields)
            removed = before.difference(available_fields)
            added = available_fields.difference(before)

            if includes and not any(v.startswith("+") for v in raw):
                known = (not has_wildcard)
            else:
                # fields +foo / fields -bar doesn't define a full field universe if we don't already know it
                known = known and (not has_wildcard)

        elif cmd_name == "table":
            before = set(available_fields)
            available_fields = _apply_table_command(cmd)
            removed = before.difference(available_fields)
            added = available_fields.difference(before)
            has_wildcard = any("*" in f for f in available_fields)
            known = (not has_wildcard)

        elif cmd_name == "rename":
            before = set(available_fields)
            pairs = _get_rename_pairs(cmd)
            for old, new in pairs:
                if old in available_fields:
                    available_fields.discard(old)
                    available_fields.add(new)
                    removed.add(old)
                    added.add(new)
                else:
                    # Old field missing; still note that the new field may appear.
                    available_fields.add(new)
                    added.add(new)
            # Renames do not improve knowledge.
            _ = before

        elif cmd_name == "rex":
            created = _get_rex_created_fields(cmd)
            added = set(created).difference(available_fields)
            available_fields = available_fields.union(created)

        elif cmd_name == "lookup":
            # Lookups can add fields (OUTPUT/OUTPUTNEW) in ways we don't fully model.
            if conservative_unknown and known:
                known = False

        elif cmd_def is None or cmd_name == "macro":
            # Unknown commands and macros may arbitrarily change fields.
            if conservative_unknown and known:
                known = False

        known_out = known
        fields_out = set(available_fields)

        stages.append(
            FieldFlowStage(
                index=idx,
                command=cmd.name,
                known_in=known_in,
                known_out=known_out,
                fields_in=frozenset(fields_in),
                fields_out=frozenset(fields_out),
                referenced_fields=frozenset(referenced),
                added_fields=frozenset(added),
                removed_fields=frozenset(removed),
                modified_fields=frozenset(modified),
            )
        )

    return stages


def track_fields(
    pipeline: Pipeline,
    result: ValidationResult,
    *,
    schema_fields: Optional[set[str]] = None,
    missing_field_severity: Severity = Severity.WARNING,
    conservative_unknown: bool = True,
) -> None:
    """Track which fields are available at each point in the pipeline.
    
    Warns when a field is used but may not exist; when schema_fields is provided
    and the field set is known at that stage, this can be upgraded to an error.
    """
    stages = compute_field_flow(
        pipeline, schema_fields=schema_fields, conservative_unknown=conservative_unknown
    )

    # Emit issues based on fields-in at each stage.
    strict_missing = schema_fields is not None
    for stage in stages:
        cmd = pipeline.commands[stage.index]

        # Preserve historical behavior: without schema, skip first command (usually generating search).
        if not strict_missing and stage.index == 0:
            continue

        available = stage.fields_in
        referenced = stage.referenced_fields
        for field in referenced:
            if field.startswith("_") or "*" in field:
                continue
            if field in available:
                continue

            if strict_missing and stage.known_in and missing_field_severity == Severity.ERROR:
                result.add_error(
                    "FLD001",
                    f"Field '{field}' does not exist in the current dataset/schema.",
                    cmd.start,
                    cmd.end,
                    suggestion=f"Available fields include: {', '.join(sorted(list(available)[:5]))}...",
                )
            else:
                result.add_warning(
                    "FLD001",
                    f"Field '{field}' may not exist. Check spelling.",
                    cmd.start,
                    cmd.end,
                    suggestion=f"Available fields include: {', '.join(sorted(list(available)[:5]))}...",
                )


def _get_referenced_fields(cmd: Command) -> set[str]:
    """Get fields referenced by a command (in options, args, etc.)."""
    from ..parser.ast import Assignment, Expression
    fields = set()
    cmd_name = cmd.name.lower()
    
    # For sort, the args are field names
    if cmd_name == "sort":
        for arg in cmd.args:
            if hasattr(arg, 'value') and isinstance(arg.value, str):
                # Remove sort modifiers like -, +, num(), str()
                field = arg.value.lstrip('-+')
                if field:
                    fields.add(field)
        # Also check options for field-like identifiers
        for key, val in cmd.options.items():
            if isinstance(val, str) and not val.startswith(('-', '+')):
                fields.add(val)
    
    # For where, fields are in the expression
    elif cmd_name == "where":
        for arg in cmd.args:
            if hasattr(arg, "value") and isinstance(arg.value, Expression):
                fields.update(_collect_fieldrefs(arg.value))

    # For eval, fields are referenced inside assignment expressions
    elif cmd_name == "eval":
        for arg in cmd.args:
            if not hasattr(arg, "value"):
                continue
            val = arg.value
            if isinstance(val, Assignment) and val.value is not None:
                fields.update(_collect_fieldrefs(val.value))
    
    # For table, fields are listed
    elif cmd_name == "table":
        for arg in cmd.args:
            if hasattr(arg, 'value') and isinstance(arg.value, str):
                fields.add(arg.value)
    
    # For fields command
    elif cmd_name == "fields":
        for arg in cmd.args:
            if hasattr(arg, 'value') and isinstance(arg.value, str):
                # Skip + and - modifiers
                field = arg.value.lstrip('-+')
                if field:
                    fields.add(field)

    # For stats-like commands: BY/OVER fields are required input fields
    elif cmd_name in ("stats", "chart", "timechart", "eventstats", "streamstats"):
        by_clause = cmd.clauses.get("BY") if hasattr(cmd, "clauses") else None
        if by_clause and getattr(by_clause, "fields", None):
            fields.update(set(by_clause.fields))
        over_clause = cmd.clauses.get("OVER") if hasattr(cmd, "clauses") else None
        if over_clause and getattr(over_clause, "fields", None):
            fields.update(set(over_clause.fields))

    elif cmd_name in ("top", "rare"):
        for arg in cmd.args:
            if hasattr(arg, "value") and isinstance(arg.value, str):
                v = arg.value.strip()
                if not v or v.upper() in ("BY", "OVER", "AS"):
                    continue
                if v.isdigit():
                    continue
                if "=" in v:
                    continue
                fields.add(v.lstrip("+-"))

    elif cmd_name == "bin":
        for arg in cmd.args:
            if hasattr(arg, "value") and isinstance(arg.value, str):
                v = arg.value.strip()
                if v and "=" not in v:
                    fields.add(v.lstrip("+-"))
                    break
    
    return fields


def _collect_fieldrefs(expr) -> set[str]:
    """Collect FieldRef names within an expression AST."""
    from ..parser.ast import FieldRef, BinaryOp, UnaryOp, FunctionCall, Assignment

    if expr is None:
        return set()

    if isinstance(expr, FieldRef):
        return {expr.name}

    if isinstance(expr, Assignment):
        return _collect_fieldrefs(expr.value)

    if isinstance(expr, BinaryOp):
        return _collect_fieldrefs(expr.left).union(_collect_fieldrefs(expr.right))

    if isinstance(expr, UnaryOp):
        return _collect_fieldrefs(expr.operand)

    if isinstance(expr, FunctionCall):
        out: set[str] = set()
        for a in expr.args:
            out.update(_collect_fieldrefs(a))
        return out

    return set()


def _apply_fields_command(cmd: Command, available_fields: set[str]) -> set[str]:
    """Apply `fields` command effects to the available field set."""
    raw: list[str] = []
    for arg in cmd.args:
        if hasattr(arg, "value") and isinstance(arg.value, str):
            raw.append(arg.value)

    includes = [v.lstrip("+") for v in raw if not v.startswith("-")]
    excludes = [v[1:] for v in raw if v.startswith("-")]

    out = set(available_fields)
    if includes:
        out = set(includes)

    out.difference_update(excludes)
    return out


def _apply_table_command(cmd: Command) -> set[str]:
    """Apply `table` command effects: output contains only the listed fields."""
    fields: set[str] = set()
    for arg in cmd.args:
        if hasattr(arg, "value") and isinstance(arg.value, str):
            fields.add(arg.value.lstrip("+-"))
    return fields


def _get_stats_output_fields(cmd: Command) -> set[str]:
    """Get fields created by a stats-like command (BY fields + aggregation aliases)."""
    fields = set()
    
    # BY clause fields are preserved
    by_clause = cmd.clauses.get("BY")
    if by_clause and hasattr(by_clause, 'fields') and by_clause.fields:
        fields.update(by_clause.fields)
    
    # OVER clause for chart
    over_clause = cmd.clauses.get("OVER")
    if over_clause and hasattr(over_clause, 'fields') and over_clause.fields:
        fields.update(over_clause.fields)

    # timechart always outputs _time as the x-axis field
    if cmd.name.lower() == "timechart":
        fields.add("_time")

    # Prefer parsed aggregations (available for stats/chart/timechart/eventstats/streamstats)
    aggs = getattr(cmd, "aggregations", None)
    if isinstance(aggs, list) and aggs:
        for agg in aggs:
            alias = getattr(agg, "alias", None)
            if isinstance(alias, str) and alias:
                fields.add(alias)
                continue
            default_name = getattr(agg, "default_name", None)
            if isinstance(default_name, str) and default_name:
                fields.add(default_name)
            else:
                fn = getattr(agg, "function", None)
                if isinstance(fn, str) and fn:
                    fields.add(fn)
    else:
        # Fallback: Parse aggregation aliases from raw args (legacy path)
        # Look for patterns like: ... AS alias
        for i, arg in enumerate(cmd.args):
            if hasattr(arg, 'value'):
                val = arg.value
                if isinstance(val, str):
                    if val.upper() == "AS" and i + 1 < len(cmd.args):
                        next_arg = cmd.args[i + 1]
                        if hasattr(next_arg, 'value') and isinstance(next_arg.value, str):
                            fields.add(next_arg.value)
    
    # Also check options for aliases
    for key, val in cmd.options.items():
        if key.upper() == "AS" and isinstance(val, str):
            fields.add(val)
    
    # If no explicit aliases found, add common aggregation names
    # This is a fallback for when parsing doesn't capture aliases
    cmd_name = cmd.name.lower()
    if cmd_name in ("top", "rare"):
        fields.add("count")
        fields.add("percent")
        # top/rare also preserve the field list they operate on
        for arg in cmd.args:
            if hasattr(arg, "value") and isinstance(arg.value, str):
                v = arg.value.strip()
                if not v:
                    continue
                # Skip numeric limit and option-like tokens
                if v.isdigit():
                    continue
                if "=" in v:
                    continue
                fields.add(v.lstrip("+-"))
    
    return fields


def _get_eval_created_fields(cmd: Command) -> set[str]:
    """Get fields created by eval command."""
    fields = set()
    
    # Prefer parsed assignments in args (when available)
    for arg in cmd.args:
        if hasattr(arg, "value") and hasattr(arg.value, "field_name"):
            field_name = getattr(arg.value, "field_name", None)
            if isinstance(field_name, str) and field_name and not field_name.startswith("_"):
                fields.add(field_name)

    # Fallback: In options, keys are field names being set (legacy parsing path)
    for key in cmd.options:
        if not key.startswith('_'):
            fields.add(key)
    
    return fields


def _get_rex_created_fields(cmd: Command) -> set[str]:
    """Get fields extracted by rex command from named capture groups."""
    fields = set()
    
    # Look for regex patterns with named groups: (?<fieldname>...)
    for arg in cmd.args:
        if hasattr(arg, 'value') and isinstance(arg.value, str):
            # Find named capture groups
            matches = re.findall(r'\(\?<([^>]+)>', arg.value)
            fields.update(matches)
    
    return fields


def _get_rename_pairs(cmd: Command) -> list[tuple[str, str]]:
    """Best-effort extraction of rename pairs from raw args: old AS new."""
    raw: list[str] = []
    for arg in cmd.args:
        if hasattr(arg, "value") and isinstance(arg.value, str):
            raw.append(arg.value)

    out: list[tuple[str, str]] = []
    i = 0
    while i + 2 < len(raw):
        old = raw[i]
        mid = raw[i + 1]
        new = raw[i + 2]
        if mid.upper() == "AS":
            out.append((old, new))
            i += 3
        else:
            i += 1
    return out


def get_available_fields_after(cmd_name: str, current_fields: set[str]) -> set[str]:
    """Get available fields after a command executes."""
    cmd_name = cmd_name.lower()
    
    if cmd_name in ("stats", "chart", "timechart", "top", "rare"):
        # Transforming commands reset available fields
        return set()  # Would be populated with BY fields + aggregations
    
    return current_fields.copy()
