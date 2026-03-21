"""Shared JSON serialization for CLI, HTTP API, and integrations."""

from __future__ import annotations

import importlib.metadata
from typing import Any, Optional

from .contract import OUTPUT_JSON_SCHEMA_VERSION
from .src.models.warning_groups import group_warnings, parse_warning_groups


def package_version() -> str:
    try:
        return importlib.metadata.version("spl-validator")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def build_validation_json_dict(
    result,
    *,
    warning_groups: str = "optimization",
    debug_ast: Any = None,
    debug_flow: Any = None,
    debug_flow_format: str = "text",
    debug_flow_rendered: Optional[str] = None,
    ast_mode: str = "summary",
) -> dict[str, Any]:
    """Build the public JSON object for a validation result (stable keys)."""
    enabled = parse_warning_groups(warning_groups)
    grouped = group_warnings(result.warnings, enabled_groups=enabled)
    filtered_warnings = (
        grouped.limits
        + grouped.optimization
        + grouped.style
        + grouped.semantic
        + grouped.schema
        + grouped.diagnostic
        + grouped.other
    )
    output: dict[str, Any] = {
        "output_schema_version": OUTPUT_JSON_SCHEMA_VERSION,
        "package_version": package_version(),
        "valid": result.is_valid,
        "errors": [
            {
                "code": e.code,
                "message": e.message,
                "line": e.start.line,
                "column": e.start.column,
                "suggestion": e.suggestion,
            }
            for e in result.errors
        ],
        "warnings": [
            {
                "code": w.code,
                "message": w.message,
                "line": w.start.line,
                "column": w.start.column,
                "suggestion": w.suggestion,
            }
            for w in filtered_warnings
        ],
    }
    if debug_ast is not None or debug_flow is not None:
        dbg: dict[str, Any] = {}
        if debug_ast is not None:
            dbg["ast_mode"] = ast_mode
            dbg["ast"] = debug_ast
        if debug_flow is not None:
            dbg["flow_format"] = debug_flow_format
            if debug_flow_format == "json":
                dbg["flow"] = debug_flow
            else:
                dbg[f"flow_{debug_flow_format}"] = debug_flow_rendered
        output["debug"] = dbg
    return output
