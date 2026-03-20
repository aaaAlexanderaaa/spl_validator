"""Function registry - SPL functions with arity, context, and Splunk reference metadata (10.0).

Sources aligned with Splunk Enterprise / Splunk Cloud Search Reference (10.0.x), e.g.:
- https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/introduction/welcome-to-the-search-reference
- https://help.splunk.com/en/release-notes-and-updates/using-the-help-portal

Context (validator):
- ``eval``: evaluation functions usable in ``eval``, ``where``, and (per Splunk) ``fieldformat``
  format strings, and inside ``eval(...)`` nested within stats-style commands.
- ``stats``: statistical / charting aggregation functions at the top level of ``stats``,
  ``chart``, ``timechart``, ``eventstats``, ``streamstats``, ``top``, and ``rare``.
- ``both``: functions with different arity in eval vs stats aggregation (``sum``, ``avg``,
  ``min``, ``max``); see ``_STATS_ARITY_OVERRIDES``.

The validator currently walks function calls in parsed ``eval`` / ``where`` AST nodes and
in stats aggregation positions; ``fieldformat`` values are stored as literal strings and
are not re-parsed for nested functions.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import FrozenSet, Optional


# --- Splunk Search Reference chapter labels (for tests and tooling) ---
SPLUNK_REF_EVALUATION = "Evaluation functions"
SPLUNK_REF_STATISTICAL_AND_CHARTING = "Statistical and charting functions"

# Commands that accept *evaluation* expressions (Splunk Search Reference).
EVAL_EXPRESSION_COMMANDS: FrozenSet[str] = frozenset({"eval", "where", "fieldformat"})

# Commands where our validator applies *stats aggregation* function rules at top level.
STATS_AGGREGATION_COMMANDS: FrozenSet[str] = frozenset(
    {"stats", "chart", "timechart", "eventstats", "streamstats", "top", "rare"}
)


@dataclass(frozen=True)
class FunctionDef:
    """Definition of an SPL function for validation and documentation."""

    name: str
    min_args: int
    max_args: Optional[int]  # None = unlimited
    context: str  # eval, stats, both
    category: str  # evaluation | statistical | evaluation_and_statistical | statistical_charting
    syntax: str  # Splunk-style signature, e.g. mvindex(<mv>,<start>,<end>)

    def splunk_reference_chapter(self) -> str:
        """Primary Search Reference chapter for this function."""
        if self.category in ("statistical", "statistical_charting"):
            return SPLUNK_REF_STATISTICAL_AND_CHARTING
        if self.category == "evaluation_and_statistical":
            return f"{SPLUNK_REF_EVALUATION} / {SPLUNK_REF_STATISTICAL_AND_CHARTING}"
        return SPLUNK_REF_EVALUATION

    def allows_eval_expression_commands(self) -> bool:
        """True if the function may appear in eval / where / fieldformat expressions."""
        return self.context in ("eval", "both")

    def allows_stats_aggregation_position(self) -> bool:
        """True if the function may appear as a top-level stats-style aggregation."""
        return self.context in ("stats", "both")

    def command_usage_summary(self) -> str:
        """Short note on where Splunk allows this function (validator-oriented)."""
        parts: list[str] = []
        if self.allows_eval_expression_commands():
            parts.append(
                "eval, where, fieldformat; nested inside stats/chart/timechart/eventstats/"
                "streamstats/top/rare via eval(<expression>)"
            )
        if self.allows_stats_aggregation_position():
            parts.append("top-level aggregation in stats, chart, timechart, eventstats, streamstats, top, rare")
        return "; ".join(parts)


def _row(
    name: str,
    min_a: int,
    max_a: Optional[int],
    ctx: str,
    category: str,
    syntax: str,
) -> tuple[str, FunctionDef]:
    return (name, FunctionDef(name, min_a, max_a, ctx, category, syntax))


_FUNCTION_ROWS: list[tuple[str, FunctionDef]] = [
    # === Evaluation: math ===
    _row("abs", 1, 1, "eval", "evaluation", "abs(<num>)"),
    _row("ceil", 1, 1, "eval", "evaluation", "ceil(<num>)"),
    _row("ceiling", 1, 1, "eval", "evaluation", "ceiling(<num>)"),
    _row("floor", 1, 1, "eval", "evaluation", "floor(<num>)"),
    _row("round", 1, 2, "eval", "evaluation", "round(<num>,<precision>)"),
    _row("sqrt", 1, 1, "eval", "evaluation", "sqrt(<num>)"),
    _row("pow", 2, 2, "eval", "evaluation", "pow(<num>,<num>)"),
    _row("exp", 1, 1, "eval", "evaluation", "exp(<num>)"),
    _row("ln", 1, 1, "eval", "evaluation", "ln(<num>)"),
    _row("log", 1, 2, "eval", "evaluation", "log(<num>,<base>)"),
    _row("pi", 0, 0, "eval", "evaluation", "pi()"),
    _row("random", 0, 0, "eval", "evaluation", "random()"),
    _row("sigfig", 1, 1, "eval", "evaluation", "sigfig(<num>)"),
    _row("exact", 1, 1, "eval", "evaluation", "exact(<expr>)"),
    # === Evaluation: trigonometric ===
    _row("cos", 1, 1, "eval", "evaluation", "cos(<num>)"),
    _row("sin", 1, 1, "eval", "evaluation", "sin(<num>)"),
    _row("tan", 1, 1, "eval", "evaluation", "tan(<num>)"),
    _row("acos", 1, 1, "eval", "evaluation", "acos(<num>)"),
    _row("asin", 1, 1, "eval", "evaluation", "asin(<num>)"),
    _row("atan", 1, 1, "eval", "evaluation", "atan(<num>)"),
    _row("atan2", 2, 2, "eval", "evaluation", "atan2(<num>,<num>)"),
    _row("cosh", 1, 1, "eval", "evaluation", "cosh(<num>)"),
    _row("sinh", 1, 1, "eval", "evaluation", "sinh(<num>)"),
    _row("tanh", 1, 1, "eval", "evaluation", "tanh(<num>)"),
    _row("acosh", 1, 1, "eval", "evaluation", "acosh(<num>)"),
    _row("asinh", 1, 1, "eval", "evaluation", "asinh(<num>)"),
    _row("atanh", 1, 1, "eval", "evaluation", "atanh(<num>)"),
    _row("hypot", 2, 2, "eval", "evaluation", "hypot(<num>,<num>)"),
    # === Evaluation: bitwise ===
    _row("bit_and", 2, None, "eval", "evaluation", "bit_and(<num>,<num>,...)"),
    _row("bit_or", 2, None, "eval", "evaluation", "bit_or(<num>,<num>,...)"),
    _row("bit_xor", 2, None, "eval", "evaluation", "bit_xor(<num>,<num>,...)"),
    _row("bit_not", 1, 2, "eval", "evaluation", "bit_not(<num>,<bitwidth>)"),
    _row("bit_shift_left", 2, 2, "eval", "evaluation", "bit_shift_left(<num>,<bits>)"),
    _row("bit_shift_right", 2, 2, "eval", "evaluation", "bit_shift_right(<num>,<bits>)"),
    # === Evaluation: string ===
    _row("len", 1, 1, "eval", "evaluation", "len(<str>)"),
    _row("lower", 1, 1, "eval", "evaluation", "lower(<str>)"),
    _row("upper", 1, 1, "eval", "evaluation", "upper(<str>)"),
    _row("substr", 2, 3, "eval", "evaluation", "substr(<str>,<start>,<length>)"),
    _row("trim", 1, 2, "eval", "evaluation", "trim(<str>,<chars>)"),
    _row("ltrim", 1, 2, "eval", "evaluation", "ltrim(<str>,<chars>)"),
    _row("rtrim", 1, 2, "eval", "evaluation", "rtrim(<str>,<chars>)"),
    _row("replace", 3, 3, "eval", "evaluation", "replace(<str>,<pattern>,<replacement>)"),
    _row("urldecode", 1, 1, "eval", "evaluation", "urldecode(<str>)"),
    _row("printf", 1, None, "eval", "evaluation", "printf(<format>,<values>,...)"),
    # === Evaluation: conditional ===
    _row("if", 3, 3, "eval", "evaluation", "if(<predicate>,<then>,<else>)"),
    _row("case", 2, None, "eval", "evaluation", "case(<cond>,<val>,...,<default>)"),
    _row("coalesce", 1, None, "eval", "evaluation", "coalesce(<field>,...)"),
    _row("ifnull", 1, None, "eval", "evaluation", "ifnull(<field>,...)"),
    _row("nullif", 2, 2, "eval", "evaluation", "nullif(<field1>,<field2>)"),
    _row("validate", 2, None, "eval", "evaluation", "validate(<condition>,<msg>,...)"),
    _row("in", 2, None, "eval", "evaluation", "in(<field>,<val>,...)"),
    _row("null", 0, 0, "eval", "evaluation", "null()"),
    _row("true", 0, 0, "eval", "evaluation", "true()"),
    _row("false", 0, 0, "eval", "evaluation", "false()"),
    # === Evaluation: conversion ===
    _row("tonumber", 1, 2, "eval", "evaluation", "tonumber(<str>,<base>)"),
    _row("tostring", 1, 2, "eval", "evaluation", "tostring(<field>,<format>)"),
    _row("toint", 1, 2, "eval", "evaluation", "toint(<field>,<base>)"),
    _row("todouble", 1, 2, "eval", "evaluation", "todouble(<field>,<base>)"),
    _row("tobool", 1, 1, "eval", "evaluation", "tobool(<field>)"),
    _row("tomv", 1, 1, "eval", "evaluation", "tomv(<field>)"),
    _row("toarray", 1, 1, "eval", "evaluation", "toarray(<field>)"),
    _row("toobject", 1, 1, "eval", "evaluation", "toobject(<field>)"),
    _row("typeof", 1, 1, "eval", "evaluation", "typeof(<field>)"),
    _row("ipmask", 2, 2, "eval", "evaluation", "ipmask(<ip>,<mask>)"),
    # === Evaluation: type check ===
    _row("isnull", 1, 1, "eval", "evaluation", "isnull(<field>)"),
    _row("isnotnull", 1, 1, "eval", "evaluation", "isnotnull(<field>)"),
    _row("isnum", 1, 1, "eval", "evaluation", "isnum(<field>)"),
    _row("isstr", 1, 1, "eval", "evaluation", "isstr(<field>)"),
    _row("isint", 1, 1, "eval", "evaluation", "isint(<field>)"),
    _row("isdouble", 1, 1, "eval", "evaluation", "isdouble(<field>)"),
    _row("isbool", 1, 1, "eval", "evaluation", "isbool(<field>)"),
    _row("ismv", 1, 1, "eval", "evaluation", "ismv(<field>)"),
    _row("isarray", 1, 1, "eval", "evaluation", "isarray(<field>)"),
    _row("isobject", 1, 1, "eval", "evaluation", "isobject(<field>)"),
    # === Evaluation: pattern ===
    _row("like", 2, 2, "eval", "evaluation", "like(<str>,<pattern>)"),
    _row("match", 2, 2, "eval", "evaluation", "match(<str>,<regex>)"),
    _row("cidrmatch", 2, 2, "eval", "evaluation", "cidrmatch(<cidr>,<ip>)"),
    _row("searchmatch", 1, 1, "eval", "evaluation", "searchmatch(<search-string>)"),
    # === Evaluation: crypto ===
    _row("md5", 1, 1, "eval", "evaluation", "md5(<str>)"),
    _row("sha1", 1, 1, "eval", "evaluation", "sha1(<str>)"),
    _row("sha256", 1, 1, "eval", "evaluation", "sha256(<str>)"),
    _row("sha512", 1, 1, "eval", "evaluation", "sha512(<str>)"),
    # === Evaluation: time ===
    _row("now", 0, 0, "eval", "evaluation", "now()"),
    _row("time", 0, 0, "eval", "evaluation", "time()"),
    _row("relative_time", 2, 2, "eval", "evaluation", "relative_time(<time>,<relative-spec>)"),
    _row("strftime", 2, 2, "eval", "evaluation", "strftime(<time>,<format>)"),
    _row("strptime", 2, 2, "eval", "evaluation", "strptime(<str>,<format>)"),
    # === Evaluation: multivalue ===
    _row("split", 2, 2, "eval", "evaluation", "split(<str>,<delim>)"),
    _row("mvjoin", 2, 2, "eval", "evaluation", "mvjoin(<mv>,<delim>)"),
    _row("mvcount", 1, 1, "eval", "evaluation", "mvcount(<mv>)"),
    _row("mvindex", 2, 3, "eval", "evaluation", "mvindex(<mv>,<start>,<end>)"),
    _row("mvfind", 2, 2, "eval", "evaluation", "mvfind(<mv>,<regex>)"),
    _row("mvsort", 1, 1, "eval", "evaluation", "mvsort(<mv>)"),
    _row("mvdedup", 1, 1, "eval", "evaluation", "mvdedup(<mv>)"),
    _row("mvfilter", 1, 1, "eval", "evaluation", "mvfilter(<predicate-expr>)"),
    _row("mvmap", 2, 3, "eval", "evaluation", "mvmap(<mv>,<expr>,<var>)"),
    _row("mvappend", 1, None, "eval", "evaluation", "mvappend(<field>,...)"),
    _row("mvzip", 2, 3, "eval", "evaluation", "mvzip(<mv1>,<mv2>,<delim>)"),
    _row("mvrange", 2, 3, "eval", "evaluation", "mvrange(<start>,<end>,<step>)"),
    _row("mvreverse", 1, 1, "eval", "evaluation", "mvreverse(<mv>)"),
    # === Evaluation: JSON ===
    _row("json_object", 0, None, "eval", "evaluation", "json_object(<key>,<val>,...)"),
    _row("json_array", 0, None, "eval", "evaluation", "json_array(<val>,...)"),
    _row("json_extract", 2, None, "eval", "evaluation", "json_extract(<json>,<path>,...)"),
    _row("json_extract_exact", 2, 2, "eval", "evaluation", "json_extract_exact(<json>,<path>)"),
    _row("json_keys", 1, 1, "eval", "evaluation", "json_keys(<json>)"),
    _row("json_entries", 1, 1, "eval", "evaluation", "json_entries(<json>)"),
    _row("json_set", 3, 3, "eval", "evaluation", "json_set(<json>,<path>,<val>)"),
    _row("json_set_exact", 3, 3, "eval", "evaluation", "json_set_exact(<json>,<path>,<val>)"),
    _row("json_delete", 2, 2, "eval", "evaluation", "json_delete(<json>,<path>)"),
    _row("json_append", 3, 3, "eval", "evaluation", "json_append(<json>,<path>,<val>)"),
    _row("json_extend", 3, 3, "eval", "evaluation", "json_extend(<json>,<path>,<val>)"),
    _row("json_valid", 1, 1, "eval", "evaluation", "json_valid(<json>)"),
    _row("json", 1, 1, "eval", "evaluation", "json(<str>)"),
    _row("json_has_key", 2, 2, "eval", "evaluation", "json_has_key(<json>,<path>)"),
    _row("json_has_key_exact", 2, 2, "eval", "evaluation", "json_has_key_exact(<json>,<path>)"),
    _row("json_array_to_mv", 1, 1, "eval", "evaluation", "json_array_to_mv(<json-array>)"),
    _row("mv_to_json_array", 1, 1, "eval", "evaluation", "mv_to_json_array(<mv>)"),
    # === Evaluation: utility ===
    _row("commands", 1, 1, "eval", "evaluation", "commands(<str>)"),
    _row("spath", 1, 2, "eval", "evaluation", "spath(<field>,<path>)"),
    _row("lookup", 3, 3, "eval", "evaluation", "lookup(<table>,<lookup-field>,<event-field>)"),
    # === Statistical: aggregations (stats position only) ===
    _row("count", 0, 1, "stats", "statistical", "count(<field>)"),
    _row("dc", 1, 1, "stats", "statistical", "dc(<field>)"),
    _row("distinct_count", 1, 1, "stats", "statistical", "distinct_count(<field>)"),
    _row("estdc", 1, 1, "stats", "statistical", "estdc(<field>)"),
    _row("estdc_error", 1, 1, "stats", "statistical", "estdc_error(<field>)"),
    _row("sum", 1, None, "both", "evaluation_and_statistical", "sum(<field>|eval(<expr>),...)"),
    _row("avg", 1, None, "both", "evaluation_and_statistical", "avg(<field>|eval(<expr>),...)"),
    _row("mean", 1, 1, "stats", "statistical", "mean(<field>)"),
    _row("min", 1, None, "both", "evaluation_and_statistical", "min(<field>|eval(<expr>),...)"),
    _row("max", 1, None, "both", "evaluation_and_statistical", "max(<field>|eval(<expr>),...)"),
    _row("range", 1, 1, "stats", "statistical", "range(<field>)"),
    _row("mode", 1, 1, "stats", "statistical", "mode(<field>)"),
    _row("median", 1, 1, "stats", "statistical", "median(<field>)"),
    _row("stdev", 1, 1, "stats", "statistical", "stdev(<field>)"),
    _row("stdevp", 1, 1, "stats", "statistical", "stdevp(<field>)"),
    _row("var", 1, 1, "stats", "statistical", "var(<field>)"),
    _row("varp", 1, 1, "stats", "statistical", "varp(<field>)"),
    _row("sumsq", 1, 1, "stats", "statistical", "sumsq(<field>)"),
    _row("first", 1, 1, "stats", "statistical", "first(<field>)"),
    _row("last", 1, 1, "stats", "statistical", "last(<field>)"),
    _row("earliest", 1, 1, "stats", "statistical", "earliest(<field>)"),
    _row("latest", 1, 1, "stats", "statistical", "latest(<field>)"),
    _row("earliest_time", 1, 1, "stats", "statistical", "earliest_time(<field>)"),
    _row("latest_time", 1, 1, "stats", "statistical", "latest_time(<field>)"),
    _row("values", 1, 1, "stats", "statistical", "values(<field>)"),
    _row("list", 1, 1, "stats", "statistical", "list(<field>)"),
    _row(
        "sparkline",
        0,
        2,
        "stats",
        "statistical_charting",
        "sparkline | sparkline(<agg-expr>,<span>)",
    ),
    _row("rate", 1, 1, "stats", "statistical", "rate(<field>)"),
    _row("rate_avg", 1, 1, "stats", "statistical", "rate_avg(<field>)"),
    _row("rate_sum", 1, 1, "stats", "statistical", "rate_sum(<field>)"),
]

FUNCTIONS: dict[str, FunctionDef] = dict(_FUNCTION_ROWS)


# Pattern for percentile functions: perc<N>, p<N>, exactperc<N>, upperperc<N>
PERCENTILE_PATTERN = re.compile(r"^(perc|p|exactperc|upperperc)(\d+)$", re.IGNORECASE)

_STATS_ARITY_OVERRIDES: dict[str, FunctionDef] = {
    "sum": FunctionDef(
        "sum",
        1,
        1,
        "stats",
        "evaluation_and_statistical",
        "sum(<field>|eval(<expr>))",
    ),
    "avg": FunctionDef(
        "avg",
        1,
        1,
        "stats",
        "evaluation_and_statistical",
        "avg(<field>|eval(<expr>))",
    ),
    "min": FunctionDef(
        "min",
        1,
        1,
        "stats",
        "evaluation_and_statistical",
        "min(<field>|eval(<expr>))",
    ),
    "max": FunctionDef(
        "max",
        1,
        1,
        "stats",
        "evaluation_and_statistical",
        "max(<field>|eval(<expr>))",
    ),
}


def get_function(name: str, context: Optional[str] = None) -> Optional[FunctionDef]:
    """Get function definition by name (case-insensitive).

    Args:
        name: Function name.
        context: Optional usage context ('eval' or 'stats'). When provided, this
            enforces context-specific allowlists and arity overrides.

    Notes:
        - Dynamic percentile functions (perc50, p95, exactperc99) are stats-only.
        - Some names exist in both contexts with different arity in stats
          aggregations; those are handled via overrides.
    """
    key = name.lower()

    if context == "stats" and key in _STATS_ARITY_OVERRIDES:
        return _STATS_ARITY_OVERRIDES[key]

    func = FUNCTIONS.get(key)
    if func:
        if context == "eval" and func.context not in ("eval", "both"):
            return None
        if context == "stats" and func.context not in ("stats", "both"):
            return None
        return func

    if context in (None, "stats"):
        match = PERCENTILE_PATTERN.match(name)
        if match:
            percentile = int(match.group(2))
            if 0 <= percentile <= 100:
                prefix = match.group(1).lower()
                return FunctionDef(
                    key,
                    1,
                    1,
                    "stats",
                    "statistical",
                    f"{prefix}<0-100>(<field>)",
                )

    return None


def is_known_function(name: str) -> bool:
    """Check if function is known to the validator."""
    return get_function(name) is not None


def validate_function_arity(name: str, arg_count: int, context: Optional[str] = None) -> Optional[str]:
    """Validate function argument count.

    Returns error message if invalid, None if valid.
    """
    any_context = get_function(name)
    if any_context is None:
        return f"Unknown function '{name}'"

    func = get_function(name, context=context)
    if func is None:
        return None

    if arg_count < func.min_args:
        if func.min_args == func.max_args:
            return f"Function '{name}' requires exactly {func.min_args} argument(s), got {arg_count}"
        return f"Function '{name}' requires at least {func.min_args} argument(s), got {arg_count}"

    if func.max_args is not None and arg_count > func.max_args:
        return f"Function '{name}' accepts at most {func.max_args} argument(s), got {arg_count}"

    return None


def validate_function_context(name: str, context: str) -> Optional[str]:
    """Validate function is used in correct context (eval vs stats).

    Returns error message if invalid, None if valid.
    """
    if get_function(name) is None:
        return None

    if get_function(name, context=context) is None:
        return f"Function '{name}' cannot be used in {context} context"

    return None


def iter_percentile_examples() -> list[str]:
    """Example percentile function names for tests (not exhaustive)."""
    return ["perc50", "p95", "exactperc99", "upperperc75"]
