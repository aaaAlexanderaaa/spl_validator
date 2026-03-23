"""SPL Validator CLI - Entry point for validating SPL queries."""

# Guard: Detect direct execution and show helpful error
if __name__ == "__main__" and __package__ is None:
    import sys

    print("Error: Cannot run validator.py directly due to relative imports.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Use this command instead (from the repository root):", file=sys.stderr)
    print('  python3 -m spl_validator --spl="your SPL query"', file=sys.stderr)
    print("  python3 -m spl_validator < query.spl", file=sys.stderr)
    sys.exit(1)

import argparse
import json
import os
import sys
from typing import Optional

from .cli_config import argparse_defaults_from_config, discover_config_path, load_cli_defaults
from .core import validate
from .json_payload import build_validation_json_dict
from .src.models.warning_groups import group_warnings, parse_warning_groups
from .src.registry.pack import load_registry_pack_file


def _open_editor_for_spl() -> Optional[str]:
    """Open $EDITOR with a temp .spl file, return the contents (comments stripped)."""
    import tempfile

    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
    with tempfile.NamedTemporaryFile(
        suffix=".spl", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write("# Enter your SPL query below.\n")
        f.write("# Lines starting with # are comments and will be ignored.\n")
        f.write("# Save and close the editor to validate.\n\n")
        tmp_path = f.name
    try:
        ret = os.system(f'{editor} "{tmp_path}"')
        if ret != 0:
            print(f"Editor exited with code {ret}", file=sys.stderr)
            return None
        with open(tmp_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(line for line in lines if not line.lstrip().startswith("#"))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main():
    """CLI entry point."""
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    pre_ns, _ = pre.parse_known_args(sys.argv[1:])
    cfg_path = discover_config_path(pre_ns.config)
    cfg_arg_defaults: dict = {}
    config_packs: list[str] = []
    if cfg_path and cfg_path.is_file():
        try:
            raw = load_cli_defaults(cfg_path)
            cfg_arg_defaults, config_packs = argparse_defaults_from_config(raw)
        except ValueError as e:
            print(f"Error in config file {cfg_path}: {e}", file=sys.stderr)
            sys.exit(1)

    parser = argparse.ArgumentParser(
        description="SPL Validator - Validates Splunk SPL queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m spl_validator --spl="index=web | stats count BY host"
  python3 -m spl_validator "index=web | stats count BY host"
  python3 -m spl_validator 'index=web | stats count'
  echo 'index=web | stats count' | python3 -m spl_validator --stdin --format=json
  python3 -m spl_validator --file=query.spl
  python3 -m spl_validator --file=- < query.spl
  python3 -m spl_validator < query.spl
  cat query.spl | python3 -m spl_validator --format=json
  python3 -m spl_validator --preset=security_content --spl="index=web | stats count"
  python3 -m spl_validator --registry-pack=spl_validator/registry_packs/example_pack.yaml \\
      --spl "index=* | mycustomcmd"
        """,
    )
    if cfg_arg_defaults:
        parser.set_defaults(**cfg_arg_defaults)

    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="YAML defaults file (also: $SPL_VALIDATOR_CONFIG or ./.spl-validator.yaml)",
    )
    parser.add_argument(
        "spl_positional",
        nargs="?",
        metavar="SPL",
        help="SPL query (alternative to --spl or --file)",
    )
    parser.add_argument(
        "--spl",
        type=str,
        help="SPL query string to validate",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to file containing SPL query (use '-' for stdin)",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read SPL from standard input (same as --file=-)",
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        help="Open $EDITOR to compose the SPL query (avoids shell quoting for complex multiline queries)",
    )
    parser.add_argument(
        "--preset",
        choices=("default", "strict", "security_content"),
        default=None,
        help=(
            "Configuration preset: default (loose commands, optimization advice), "
            "strict (unknown commands are errors), "
            "security_content (strict + all advice groups; aligns with ESCU-style scanning)"
        ),
    )
    parser.add_argument(
        "--registry-pack",
        action="append",
        default=[],
        metavar="PATH",
        help="YAML registry pack to merge (repeatable); see spl_validator/registry_packs/",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat unknown commands as errors (macros still allowed)",
    )

    parser.add_argument(
        "--dump-ast",
        action="store_true",
        help="Dump parsed AST (summary/full) for debugging",
    )
    parser.add_argument(
        "--ast-mode",
        choices=["summary", "full"],
        default="summary",
        help="AST dump detail level (default: summary)",
    )
    parser.add_argument(
        "--dump-flow",
        action="store_true",
        help="Dump simulated data-flow sketch (fields/actions)",
    )
    parser.add_argument(
        "--flow-format",
        choices=["text", "json", "dot"],
        default="text",
        help="Flow dump output format (default: text)",
    )
    parser.add_argument(
        "--schema",
        type=str,
        help="Optional dataset schema file (JSON/YAML) to make missing-field checks strict when fields are known",
    )
    parser.add_argument(
        "--schema-missing",
        choices=["error", "warning"],
        default="error",
        help="When --schema is provided and fields are known, treat missing fields as error or warning (default: error)",
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

    if args.preset == "strict":
        args.strict = True
    elif args.preset == "security_content":
        args.strict = True
        args.advice = "all"

    try:
        parse_warning_groups(args.advice)
    except ValueError as e:
        parser.error(str(e))

    for pack_path in config_packs:
        try:
            load_registry_pack_file(pack_path)
        except (OSError, ValueError) as e:
            print(f"Error loading registry pack {pack_path!r}: {e}", file=sys.stderr)
            sys.exit(1)
    for pack_path in args.registry_pack or []:
        try:
            load_registry_pack_file(pack_path)
        except (OSError, ValueError) as e:
            print(f"Error loading registry pack {pack_path!r}: {e}", file=sys.stderr)
            sys.exit(1)

    stdin_requested = bool(args.stdin) or (args.file == "-")
    file_path_requested = bool(args.file) and args.file != "-"
    edit_requested = bool(args.edit)
    sources = (
        (1 if args.spl_positional is not None else 0)
        + (1 if args.spl else 0)
        + (1 if file_path_requested else 0)
        + (1 if stdin_requested else 0)
        + (1 if edit_requested else 0)
    )
    if sources > 1:
        parser.error("Use only one of: SPL positional argument, --spl, --file, --edit, or --stdin")

    spl: Optional[str] = None
    if args.spl_positional is not None:
        spl = args.spl_positional
    elif args.spl:
        spl = args.spl
    elif edit_requested:
        spl = _open_editor_for_spl()
        if not spl or not spl.strip():
            print("No SPL provided. Aborting.", file=sys.stderr)
            sys.exit(1)
    elif stdin_requested:
        spl = sys.stdin.read()
    elif args.file:
        try:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                spl = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        spl = sys.stdin.read()
    else:
        parser.print_help()
        print(
            "\nProvide SPL via --spl, --file, --edit, a positional argument, --stdin, or pipe on stdin.\n"
            "TIP: For complex multiline queries, use --file=query.spl or --edit to open your editor.",
            file=sys.stderr,
        )
        sys.exit(1)

    schema_fields = None
    if args.schema:
        from .src.debug.schema import load_field_schema

        schema = load_field_schema(args.schema)
        schema_fields = set(schema.fields)

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
        from .src.debug.flow import build_flow, flow_to_dot, flow_to_text

        debug_flow = build_flow(result.ast, schema_fields=schema_fields)
        if args.flow_format == "text":
            debug_flow_rendered = flow_to_text(debug_flow)
        elif args.flow_format == "dot":
            debug_flow_rendered = flow_to_dot(debug_flow)
        else:
            debug_flow_rendered = None

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
    if result.is_valid:
        print("✅ VALID SPL\n")
    else:
        print("❌ INVALID SPL\n")

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

    if verbose and result.ast:
        print(f"📊 Pipeline: {len(result.ast.commands)} commands")
        for i, cmd in enumerate(result.ast.commands):
            print(f"  {i + 1}. {cmd.name}")

    if debug_ast is not None and result.ast is not None:
        print()
        print(f"🌳 AST ({ast_mode}):")
        if ast_mode == "summary":
            cmds = debug_ast.get("commands") if isinstance(debug_ast, dict) else None
            if isinstance(cmds, list):
                for i, c in enumerate(cmds):
                    name = c.get("name", "")
                    options = c.get("options", [])
                    clauses = c.get("clauses", [])
                    args_count = c.get("args_count", 0)
                    has_sub = c.get("has_subsearch", False)
                    print(
                        f"  {i + 1}. {name} options={options} clauses={clauses} args={args_count} subsearch={has_sub}"
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
    output = build_validation_json_dict(
        result,
        warning_groups=warning_groups,
        debug_ast=debug_ast,
        debug_flow=debug_flow,
        debug_flow_format=debug_flow_format,
        debug_flow_rendered=debug_flow_rendered,
        ast_mode=ast_mode,
    )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
