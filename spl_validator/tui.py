"""Optional Textual TUI for multiline SPL paste and validation."""
from __future__ import annotations

import argparse
import sys
from typing import Optional


def run_app(
    *,
    strict: bool = False,
    advice: str = "optimization",
    schema_path: Optional[str] = None,
    schema_missing: str = "error",
) -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Container, VerticalScroll
        from textual.widgets import Button, Footer, Header, RichLog, TextArea
    except ImportError:
        print(
            "Textual is not installed. Install with: pip install 'spl-validator[tui]'",
            file=sys.stderr,
        )
        sys.exit(1)

    from .core import validate
    from .src.debug.schema import load_field_schema
    from .src.models.warning_groups import group_warnings, parse_warning_groups

    schema_fields = None
    if schema_path:
        schema = load_field_schema(schema_path)
        schema_fields = set(schema.fields)

    class SPLValidatorTui(App[None]):
        CSS = """
        TextArea { min-height: 8; }
        RichLog { min-height: 10; border: solid $accent; }
        """

        def __init__(self) -> None:
            super().__init__()
            self._strict = strict
            self._advice = advice
            self._schema_fields = schema_fields
            self._schema_missing = schema_missing

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with VerticalScroll():
                yield TextArea(id="spl")
            yield Button("Validate", variant="primary", id="btn_validate")
            with Container():
                yield RichLog(id="out", wrap=True, highlight=True, markup=True)
            yield Footer()

        def on_mount(self) -> None:
            ta = self.query_one("#spl", TextArea)
            ta.focus()
            ta.text = "index=_internal | head 5\n| stats count"

        def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: N802
            if event.button.id != "btn_validate":
                return
            spl = self.query_one("#spl", TextArea).text
            log = self.query_one("#out", RichLog)
            log.clear()
            try:
                enabled = parse_warning_groups(self._advice)
            except ValueError as e:
                log.write(f"[red]Invalid advice:[/red] {e}")
                return
            result = validate(
                spl,
                strict=self._strict,
                schema_fields=self._schema_fields,
                schema_missing_severity=self._schema_missing,
            )
            if result.is_valid:
                log.write("[green]VALID[/green]")
            else:
                log.write("[red]INVALID[/red]")
            for e in result.errors:
                line = f"[red]{e.code}[/red] {e.message}"
                if e.suggestion:
                    line += f"\n  [dim]{e.suggestion}[/dim]"
                log.write(line)
            grouped = group_warnings(result.warnings, enabled_groups=enabled)
            filtered = (
                grouped.limits
                + grouped.optimization
                + grouped.style
                + grouped.semantic
                + grouped.schema
                + grouped.diagnostic
                + grouped.other
            )
            for w in filtered:
                line = f"[yellow]{w.code}[/yellow] {w.message}"
                if w.suggestion:
                    line += f"\n  [dim]{w.suggestion}[/dim]"
                log.write(line)

    SPLValidatorTui().run()


def main() -> None:
    from .cli_config import argparse_defaults_from_config, discover_config_path, load_cli_defaults
    from .src.models.warning_groups import parse_warning_groups
    from .src.registry.pack import load_registry_pack_file

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

    parser = argparse.ArgumentParser(description="SPL Validator Textual UI")
    if cfg_arg_defaults:
        parser.set_defaults(**cfg_arg_defaults)
    parser.add_argument("--config", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--advice", type=str, default="optimization")
    parser.add_argument("--schema", type=str, default=None)
    parser.add_argument("--schema-missing", choices=["error", "warning"], default="error")
    parser.add_argument("--registry-pack", action="append", default=[], metavar="PATH")
    args = parser.parse_args()

    try:
        parse_warning_groups(args.advice)
    except ValueError as e:
        parser.error(str(e))

    for pack_path in config_packs + (args.registry_pack or []):
        try:
            load_registry_pack_file(pack_path)
        except (OSError, ValueError) as e:
            print(f"Error loading registry pack {pack_path!r}: {e}", file=sys.stderr)
            sys.exit(1)

    run_app(
        strict=bool(args.strict),
        advice=str(args.advice),
        schema_path=args.schema,
        schema_missing=str(args.schema_missing),
    )


if __name__ == "__main__":
    main()
