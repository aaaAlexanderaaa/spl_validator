"""Function registry - SPL functions with arity and context (Splunk 10.0).

Based on official searchbnf.conf and KB documentation.
"""
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class FunctionDef:
    """Definition of an SPL function for validation."""
    name: str
    min_args: int
    max_args: Optional[int]  # None = unlimited
    context: str             # eval, stats, both


FUNCTIONS: dict[str, FunctionDef] = {
    # === EVAL: MATH FUNCTIONS ===
    "abs": FunctionDef("abs", 1, 1, "eval"),
    "ceil": FunctionDef("ceil", 1, 1, "eval"),
    "ceiling": FunctionDef("ceiling", 1, 1, "eval"),  # alias for ceil
    "floor": FunctionDef("floor", 1, 1, "eval"),
    "round": FunctionDef("round", 1, 2, "eval"),
    "sqrt": FunctionDef("sqrt", 1, 1, "eval"),
    "pow": FunctionDef("pow", 2, 2, "eval"),
    "exp": FunctionDef("exp", 1, 1, "eval"),
    "ln": FunctionDef("ln", 1, 1, "eval"),
    "log": FunctionDef("log", 1, 2, "eval"),
    "pi": FunctionDef("pi", 0, 0, "eval"),
    "random": FunctionDef("random", 0, 0, "eval"),
    "sigfig": FunctionDef("sigfig", 1, 1, "eval"),
    "exact": FunctionDef("exact", 1, 1, "eval"),
    
    # === EVAL: TRIGONOMETRIC FUNCTIONS ===
    "cos": FunctionDef("cos", 1, 1, "eval"),
    "sin": FunctionDef("sin", 1, 1, "eval"),
    "tan": FunctionDef("tan", 1, 1, "eval"),
    "acos": FunctionDef("acos", 1, 1, "eval"),
    "asin": FunctionDef("asin", 1, 1, "eval"),
    "atan": FunctionDef("atan", 1, 1, "eval"),
    "atan2": FunctionDef("atan2", 2, 2, "eval"),
    "cosh": FunctionDef("cosh", 1, 1, "eval"),
    "sinh": FunctionDef("sinh", 1, 1, "eval"),
    "tanh": FunctionDef("tanh", 1, 1, "eval"),
    "acosh": FunctionDef("acosh", 1, 1, "eval"),
    "asinh": FunctionDef("asinh", 1, 1, "eval"),
    "atanh": FunctionDef("atanh", 1, 1, "eval"),
    "hypot": FunctionDef("hypot", 2, 2, "eval"),
    
    # === EVAL: BITWISE FUNCTIONS ===
    "bit_and": FunctionDef("bit_and", 2, None, "eval"),
    "bit_or": FunctionDef("bit_or", 2, None, "eval"),
    "bit_xor": FunctionDef("bit_xor", 2, None, "eval"),
    "bit_not": FunctionDef("bit_not", 1, 2, "eval"),
    "bit_shift_left": FunctionDef("bit_shift_left", 2, 2, "eval"),
    "bit_shift_right": FunctionDef("bit_shift_right", 2, 2, "eval"),
    
    # === EVAL: STRING FUNCTIONS ===
    "len": FunctionDef("len", 1, 1, "eval"),
    "lower": FunctionDef("lower", 1, 1, "eval"),
    "upper": FunctionDef("upper", 1, 1, "eval"),
    "substr": FunctionDef("substr", 2, 3, "eval"),
    "trim": FunctionDef("trim", 1, 2, "eval"),
    "ltrim": FunctionDef("ltrim", 1, 2, "eval"),
    "rtrim": FunctionDef("rtrim", 1, 2, "eval"),
    "replace": FunctionDef("replace", 3, 3, "eval"),
    "urldecode": FunctionDef("urldecode", 1, 1, "eval"),
    "printf": FunctionDef("printf", 1, None, "eval"),
    
    # === EVAL: CONDITIONAL FUNCTIONS ===
    "if": FunctionDef("if", 3, 3, "eval"),
    "case": FunctionDef("case", 2, None, "eval"),
    "coalesce": FunctionDef("coalesce", 1, None, "eval"),
    "ifnull": FunctionDef("ifnull", 1, None, "eval"),  # alias for coalesce
    "nullif": FunctionDef("nullif", 2, 2, "eval"),
    "validate": FunctionDef("validate", 2, None, "eval"),
    "in": FunctionDef("in", 2, None, "eval"),
    "null": FunctionDef("null", 0, 0, "eval"),
    "true": FunctionDef("true", 0, 0, "eval"),
    "false": FunctionDef("false", 0, 0, "eval"),
    
    # === EVAL: CONVERSION FUNCTIONS ===
    "tonumber": FunctionDef("tonumber", 1, 2, "eval"),
    "tostring": FunctionDef("tostring", 1, 2, "eval"),
    "toint": FunctionDef("toint", 1, 2, "eval"),
    "todouble": FunctionDef("todouble", 1, 2, "eval"),
    "tobool": FunctionDef("tobool", 1, 1, "eval"),
    "tomv": FunctionDef("tomv", 1, 1, "eval"),
    "toarray": FunctionDef("toarray", 1, 1, "eval"),
    "toobject": FunctionDef("toobject", 1, 1, "eval"),
    "typeof": FunctionDef("typeof", 1, 1, "eval"),
    "ipmask": FunctionDef("ipmask", 2, 2, "eval"),
    
    # === EVAL: TYPE CHECK FUNCTIONS ===
    "isnull": FunctionDef("isnull", 1, 1, "eval"),
    "isnotnull": FunctionDef("isnotnull", 1, 1, "eval"),
    "isnum": FunctionDef("isnum", 1, 1, "eval"),
    "isstr": FunctionDef("isstr", 1, 1, "eval"),
    "isint": FunctionDef("isint", 1, 1, "eval"),
    "isdouble": FunctionDef("isdouble", 1, 1, "eval"),
    "isbool": FunctionDef("isbool", 1, 1, "eval"),
    "ismv": FunctionDef("ismv", 1, 1, "eval"),
    "isarray": FunctionDef("isarray", 1, 1, "eval"),
    "isobject": FunctionDef("isobject", 1, 1, "eval"),
    
    # === EVAL: PATTERN FUNCTIONS ===
    "like": FunctionDef("like", 2, 2, "eval"),
    "match": FunctionDef("match", 2, 2, "eval"),
    "cidrmatch": FunctionDef("cidrmatch", 2, 2, "eval"),
    "searchmatch": FunctionDef("searchmatch", 1, 1, "eval"),
    
    # === EVAL: CRYPTO FUNCTIONS ===
    "md5": FunctionDef("md5", 1, 1, "eval"),
    "sha1": FunctionDef("sha1", 1, 1, "eval"),
    "sha256": FunctionDef("sha256", 1, 1, "eval"),
    "sha512": FunctionDef("sha512", 1, 1, "eval"),
    
    # === EVAL: TIME FUNCTIONS ===
    "now": FunctionDef("now", 0, 0, "eval"),
    "time": FunctionDef("time", 0, 0, "eval"),
    "relative_time": FunctionDef("relative_time", 2, 2, "eval"),
    "strftime": FunctionDef("strftime", 2, 2, "eval"),
    "strptime": FunctionDef("strptime", 2, 2, "eval"),
    
    # === EVAL: MULTIVALUE FUNCTIONS ===
    "split": FunctionDef("split", 2, 2, "eval"),
    "mvjoin": FunctionDef("mvjoin", 2, 2, "eval"),
    "mvcount": FunctionDef("mvcount", 1, 1, "eval"),
    "mvindex": FunctionDef("mvindex", 2, 3, "eval"),
    "mvfind": FunctionDef("mvfind", 2, 2, "eval"),
    "mvsort": FunctionDef("mvsort", 1, 1, "eval"),
    "mvdedup": FunctionDef("mvdedup", 1, 1, "eval"),
    "mvfilter": FunctionDef("mvfilter", 1, 1, "eval"),
    "mvmap": FunctionDef("mvmap", 2, 3, "eval"),  # 3rd arg is optional replacement var
    "mvappend": FunctionDef("mvappend", 1, None, "eval"),  # Can take 1+ args
    "mvzip": FunctionDef("mvzip", 2, 3, "eval"),
    "mvrange": FunctionDef("mvrange", 2, 3, "eval"),
    "mvreverse": FunctionDef("mvreverse", 1, 1, "eval"),
    
    # === EVAL: JSON FUNCTIONS ===
    "json_object": FunctionDef("json_object", 0, None, "eval"),
    "json_array": FunctionDef("json_array", 0, None, "eval"),
    "json_extract": FunctionDef("json_extract", 2, None, "eval"),
    "json_extract_exact": FunctionDef("json_extract_exact", 2, 2, "eval"),
    "json_keys": FunctionDef("json_keys", 1, 1, "eval"),
    "json_entries": FunctionDef("json_entries", 1, 1, "eval"),
    "json_set": FunctionDef("json_set", 3, 3, "eval"),
    "json_set_exact": FunctionDef("json_set_exact", 3, 3, "eval"),
    "json_delete": FunctionDef("json_delete", 2, 2, "eval"),
    "json_append": FunctionDef("json_append", 3, 3, "eval"),
    "json_extend": FunctionDef("json_extend", 3, 3, "eval"),
    "json_valid": FunctionDef("json_valid", 1, 1, "eval"),
    "json": FunctionDef("json", 1, 1, "eval"),
    "json_has_key": FunctionDef("json_has_key", 2, 2, "eval"),
    "json_has_key_exact": FunctionDef("json_has_key_exact", 2, 2, "eval"),
    "json_array_to_mv": FunctionDef("json_array_to_mv", 1, 1, "eval"),
    "mv_to_json_array": FunctionDef("mv_to_json_array", 1, 1, "eval"),
    
    # === EVAL: UTILITY FUNCTIONS ===
    "commands": FunctionDef("commands", 1, 1, "eval"),
    "spath": FunctionDef("spath", 1, 2, "eval"),
    "lookup": FunctionDef("lookup", 3, 3, "eval"),  # Inline lookup function
    
    # === STATS: AGGREGATION FUNCTIONS ===
    "count": FunctionDef("count", 0, 1, "stats"),
    "dc": FunctionDef("dc", 1, 1, "stats"),
    "distinct_count": FunctionDef("distinct_count", 1, 1, "stats"),  # alias for dc
    "estdc": FunctionDef("estdc", 1, 1, "stats"),
    "estdc_error": FunctionDef("estdc_error", 1, 1, "stats"),
    "sum": FunctionDef("sum", 1, None, "both"),  # Can sum multiple fields in eval
    "avg": FunctionDef("avg", 1, None, "both"),  # Can average multiple fields in eval
    "mean": FunctionDef("mean", 1, 1, "stats"),
    "min": FunctionDef("min", 1, None, "both"),  # Can take multiple args in eval
    "max": FunctionDef("max", 1, None, "both"),  # Can take multiple args in eval
    "range": FunctionDef("range", 1, 1, "stats"),
    "mode": FunctionDef("mode", 1, 1, "stats"),
    "median": FunctionDef("median", 1, 1, "stats"),
    "stdev": FunctionDef("stdev", 1, 1, "stats"),
    "stdevp": FunctionDef("stdevp", 1, 1, "stats"),
    "var": FunctionDef("var", 1, 1, "stats"),
    "varp": FunctionDef("varp", 1, 1, "stats"),
    "sumsq": FunctionDef("sumsq", 1, 1, "stats"),
    "first": FunctionDef("first", 1, 1, "stats"),
    "last": FunctionDef("last", 1, 1, "stats"),
    "earliest": FunctionDef("earliest", 1, 1, "stats"),
    "latest": FunctionDef("latest", 1, 1, "stats"),
    "earliest_time": FunctionDef("earliest_time", 1, 1, "stats"),
    "latest_time": FunctionDef("latest_time", 1, 1, "stats"),
    "values": FunctionDef("values", 1, 1, "stats"),
    "list": FunctionDef("list", 1, 1, "stats"),
    "sparkline": FunctionDef("sparkline", 1, 2, "stats"),
    "rate": FunctionDef("rate", 1, 1, "stats"),
    "rate_avg": FunctionDef("rate_avg", 1, 1, "stats"),
    "rate_sum": FunctionDef("rate_sum", 1, 1, "stats"),
}


# Pattern for percentile functions: perc<N>, p<N>, exactperc<N>, upperperc<N>
# From searchbnf.conf: syntax = (perc|p|exactperc|upperperc)<num>
PERCENTILE_PATTERN = re.compile(r'^(perc|p|exactperc|upperperc)(\d+)$', re.IGNORECASE)

_STATS_ARITY_OVERRIDES: dict[str, FunctionDef] = {
    # Functions that exist in both eval and stats contexts but have different
    # arity rules in stats aggregation usage (e.g. `stats sum(field)`).
    #
    # Splunk 10.0 (searchbnf.conf):
    # - Eval: sum(x, y, ...), avg(x, y, ...), min(x, y, ...), max(x, y, ...)
    # - Stats: sum(field|eval(...)), avg(...), min(...), max(...)  (single top-level arg)
    "sum": FunctionDef("sum", 1, 1, "stats"),
    "avg": FunctionDef("avg", 1, 1, "stats"),
    "min": FunctionDef("min", 1, 1, "stats"),
    "max": FunctionDef("max", 1, 1, "stats"),
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

    # Stats-only arity overrides for shared names (sum/avg/min/max).
    if context == "stats" and key in _STATS_ARITY_OVERRIDES:
        return _STATS_ARITY_OVERRIDES[key]

    # Check static functions first
    func = FUNCTIONS.get(key)
    if func:
        if context == "eval" and func.context not in ("eval", "both"):
            return None
        if context == "stats" and func.context not in ("stats", "both"):
            return None
        return func

    # Check for percentile function pattern (stats-only)
    if context in (None, "stats"):
        match = PERCENTILE_PATTERN.match(name)
        if match:
            percentile = int(match.group(2))
            if 0 <= percentile <= 100:
                return FunctionDef(key, 1, 1, "stats")

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
        # Function exists, but isn't valid in this context; context validator will report.
        return None
    
    if arg_count < func.min_args:
        if func.min_args == func.max_args:
            return f"Function '{name}' requires exactly {func.min_args} argument(s), got {arg_count}"
        else:
            return f"Function '{name}' requires at least {func.min_args} argument(s), got {arg_count}"
    
    if func.max_args is not None and arg_count > func.max_args:
        return f"Function '{name}' accepts at most {func.max_args} argument(s), got {arg_count}"
    
    return None


def validate_function_context(name: str, context: str) -> Optional[str]:
    """Validate function is used in correct context (eval vs stats).
    
    Returns error message if invalid, None if valid.
    """
    if get_function(name) is None:
        return None  # Unknown function - separate error

    if get_function(name, context=context) is None:
        return f"Function '{name}' cannot be used in {context} context"

    return None
