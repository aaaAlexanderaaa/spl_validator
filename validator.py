"""SPL Validator CLI - Entry point for validating SPL queries."""

# Guard: Detect direct execution and show helpful error
if __name__ == "__main__" and __package__ is None:
    import sys
    print("Error: Cannot run validator.py directly due to relative imports.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Use this command instead (from the repository root):", file=sys.stderr)
    print("  python3 -m validator --spl=\"your SPL query\"", file=sys.stderr)
    sys.exit(1)

import argparse
import sys
import json
from typing import Optional

from .core import validate
from .src.models import Severity
from .src.models.warning_groups import group_warnings, parse_warning_groups


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SPL Validator - Validates Splunk SPL queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m validator --spl="index=web | stats count BY host"
  python3 -m validator --spl="| stats count" --format=json
  python3 -m validator --file=query.spl
  python3 -m validator --strict --spl="index=web | `my_macro(arg)` | stats count"
        """
    )
    
    parser.add_argument(
        "--spl",
        type=str,
        help="SPL query string to validate"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to file containing SPL query"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat unknown commands as errors (macros still allowed)"
    )

    parser.add_argument(
        "--dump-ast",
        action="store_true",
        help="Dump parsed AST (summary/full) for debugging"
    )
    parser.add_argument(
        "--ast-mode",
        choices=["summary", "full"],
        default="summary",
        help="AST dump detail level (default: summary)"
    )
    parser.add_argument(
        "--dump-flow",
        action="store_true",
        help="Dump simulated data-flow sketch (fields/actions)"
    )
    parser.add_argument(
        "--flow-format",
        choices=["text", "json", "dot"],
        default="text",
        help="Flow dump output format (default: text)"
    )
    parser.add_argument(
        "--schema",
        type=str,
        help="Optional dataset schema file (JSON/YAML) to make missing-field checks strict when fields are known"
    )
    parser.add_argument(
        "--schema-missing",
        choices=["error", "warning"],
        default="error",
        help="When --schema is provided and fields are known, treat missing fields as error or warning (default: error)"
    )
    parser.add_argument(
        "--advice",
        type=str,
        default="optimization",
        help=(
            "Which warning groups to output (default: optimization). "
            "Values: optimization (limits+optimization), all, none, or a comma-separated list: "
            "limits,optimization,style,semantic,schema,diagnostic,other"
        ),
    )
    
    args = parser.parse_args()

    # Validate --advice early so typos produce an argparse-style error message.
    try:
        parse_warning_groups(args.advice)
    except ValueError as e:
        parser.error(str(e))
    
    # Get SPL from args or file
    spl: Optional[str] = None
    if args.spl:
        spl = args.spl
    elif args.file:
        try:
            with open(args.file, "r") as f:
                spl = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    schema_fields = None
    if args.schema:
        from .src.debug.schema import load_field_schema
        schema = load_field_schema(args.schema)
        schema_fields = set(schema.fields)

    # Validate
    result = validate(
        spl,
        strict=args.strict,
        schema_fields=schema_fields,
        schema_missing_severity=args.schema_missing,
    )

    debug_ast = None
    if args.dump_ast:
        from .src.debug.ast_dump import dump_ast
        debug_ast = dump_ast(result.ast, mode=args.ast_mode)

    debug_flow = None
    debug_flow_rendered = None
    if args.dump_flow and result.ast is not None:
        from .src.debug.flow import build_flow, flow_to_text, flow_to_dot
        debug_flow = build_flow(result.ast, schema_fields=schema_fields)
        if args.flow_format == "text":
            debug_flow_rendered = flow_to_text(debug_flow)
        elif args.flow_format == "dot":
            debug_flow_rendered = flow_to_dot(debug_flow)
        else:
            debug_flow_rendered = None
    
    # Output
    if args.format == "json":
        output_json(
            result,
            warning_groups=args.advice,
            debug_ast=debug_ast,
            debug_flow=debug_flow,
            debug_flow_format=args.flow_format,
            debug_flow_rendered=debug_flow_rendered,
            ast_mode=args.ast_mode,
        )
    else:
        output_text(
            result,
            verbose=args.verbose,
            warning_groups=args.advice,
            debug_ast=debug_ast,
            debug_flow=debug_flow,
            debug_flow_format=args.flow_format,
            debug_flow_rendered=debug_flow_rendered,
            ast_mode=args.ast_mode,
        )
    
    # Exit code
    sys.exit(0 if result.is_valid else 1)


def output_text(
    result,
    verbose: bool = False,
    *,
    warning_groups: str = "optimization",
    debug_ast=None,
    debug_flow=None,
    debug_flow_format: str = "text",
    debug_flow_rendered: Optional[str] = None,
    ast_mode: str = "summary",
):
    """Output validation result as text."""
    # Header
    if result.is_valid:
        print("✅ VALID SPL\n")
    else:
        print("❌ INVALID SPL\n")
    
    # Errors
    if result.errors:
        print("Errors:")
        for err in result.errors:
            print(f"  • [{err.code}] {err.message}")
            if verbose:
                print(f"    at {err.start}")
            if err.suggestion:
                print(f"    💡 {err.suggestion}")
        print()
    
    enabled = parse_warning_groups(warning_groups)
    grouped = group_warnings(result.warnings, enabled_groups=enabled)
    
    if grouped.limits:
        print("📋 Limitations (from limits.conf):")
        for warn in grouped.limits:
            print(f"  • {warn.message}")
        print()
    
    if grouped.optimization:
        print("⚡ Optimization Suggestions:")
        for warn in grouped.optimization:
            print(f"  • {warn.message}")
            if warn.suggestion:
                print(f"    💡 {warn.suggestion}")
        print()

    other = (
        grouped.style
        + grouped.semantic
        + grouped.schema
        + grouped.diagnostic
        + grouped.other
    )
    if other:
        print("ℹ️  Other Warnings:")
        for warn in other:
            print(f"  • [{warn.code}] {warn.message}")
            if warn.suggestion:
                print(f"    💡 {warn.suggestion}")
        print()
    
    # Verbose: show AST summary
    if verbose and result.ast:
        print(f"📊 Pipeline: {len(result.ast.commands)} commands")
        for i, cmd in enumerate(result.ast.commands):
            print(f"  {i+1}. {cmd.name}")

    if debug_ast is not None and result.ast is not None:
        print()
        print(f"🌳 AST ({ast_mode}):")
        if ast_mode == "summary":
            # Render a human-friendly view in summary mode.
            cmds = debug_ast.get("commands") if isinstance(debug_ast, dict) else None
            if isinstance(cmds, list):
                for i, c in enumerate(cmds):
                    name = c.get("name", "")
                    options = c.get("options", [])
                    clauses = c.get("clauses", [])
                    args_count = c.get("args_count", 0)
                    has_sub = c.get("has_subsearch", False)
                    print(
                        f"  {i+1}. {name} options={options} clauses={clauses} args={args_count} subsearch={has_sub}"
                    )
            else:
                print(json.dumps(debug_ast, indent=2))
        else:
            print(json.dumps(debug_ast, indent=2))

    if debug_flow is not None:
        print()
        if debug_flow_format == "dot":
            print("🔁 Flow (dot):")
            if debug_flow_rendered:
                print(debug_flow_rendered.rstrip())
        elif debug_flow_format == "json":
            print("🔁 Flow (json):")
            print(json.dumps(debug_flow, indent=2))
        else:
            print("🔁 Flow (text):")
            if debug_flow_rendered:
                print(debug_flow_rendered.rstrip())


def output_json(
    result,
    *,
    warning_groups: str = "optimization",
    debug_ast=None,
    debug_flow=None,
    debug_flow_format: str = "text",
    debug_flow_rendered: Optional[str] = None,
    ast_mode: str = "summary",
):
    """Output validation result as JSON."""
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
    output = {
        "valid": result.is_valid,
        "errors": [
            {
                "code": e.code,
                "message": e.message,
                "line": e.start.line,
                "column": e.start.column,
                "suggestion": e.suggestion
            }
            for e in result.errors
        ],
        "warnings": [
            {
                "code": w.code,
                "message": w.message,
                "line": w.start.line,
                "column": w.start.column,
                "suggestion": w.suggestion
            }
            for w in filtered_warnings
        ]
    }
    if debug_ast is not None or debug_flow is not None:
        dbg = {}
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
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
