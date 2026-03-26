"""Full-featured TUI for SPL validation — optimized for complex, multiline queries.

Launch:
    spl-validator-tui                     # interactive editor
    spl-validator-tui --file query.spl    # pre-load query from file
    spl-validator-tui --strict            # enable strict mode

Inside the TUI:
    F5          Validate the current query
    Ctrl+L      Clear the editor and results
    Ctrl+O      Open an SPL file
    Ctrl+S      Save validation results (JSON) to file
    q           Quit (when not typing in the editor)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def run_app(
    *,
    strict: bool = False,
    advice: str = "optimization",
    schema_path: Optional[str] = None,
    schema_missing: str = "error",
    preload_file: Optional[str] = None,
) -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical
        from textual.screen import ModalScreen
        from textual.widgets import (
            Button,
            Checkbox,
            Footer,
            Header,
            Input,
            Label,
            RichLog,
            Select,
            Static,
            TabbedContent,
            TabPane,
            TextArea,
        )
    except ImportError:
        print(
            "Textual is not installed. Install with: pip install 'spl-validator[tui]'",
            file=sys.stderr,
        )
        sys.exit(1)

    from .core import validate
    from .json_payload import build_validation_json_dict
    from .src.models.warning_groups import group_warnings, parse_warning_groups

    schema_fields: Optional[set[str]] = None
    if schema_path:
        from .src.debug.schema import load_field_schema

        schema = load_field_schema(schema_path)
        schema_fields = set(schema.fields)

    preload_text = ""
    if preload_file:
        try:
            preload_text = Path(preload_file).read_text(
                encoding="utf-8", errors="replace"
            )
        except (OSError, FileNotFoundError) as e:
            print(f"Warning: Could not read file {preload_file}: {e}", file=sys.stderr)

    ADVICE_CHOICES: list[tuple[str, str]] = [
        ("optimization", "optimization"),
        ("all", "all"),
        ("none", "none"),
        ("limits", "limits"),
        ("style", "style"),
        ("semantic", "semantic"),
        ("diagnostic", "diagnostic"),
    ]

    class FileOpenScreen(ModalScreen[Optional[str]]):
        """Modal dialog for entering a file path to load."""

        CSS = """
        FileOpenScreen { align: center middle; }
        #file-dialog {
            width: 70;
            height: auto;
            padding: 1 2;
            border: thick $accent;
            background: $surface;
        }
        #file-dialog Label { margin-bottom: 1; }
        #file-dialog Input { margin-bottom: 1; }
        #file-buttons { height: auto; align: right middle; }
        #file-buttons Button { margin-left: 1; }
        """

        BINDINGS = [Binding("escape", "cancel", "Cancel")]

        def compose(self) -> ComposeResult:
            with Vertical(id="file-dialog"):
                yield Label("Open SPL file — enter the path below:")
                yield Input(
                    id="file_path",
                    placeholder="/path/to/query.spl",
                )
                with Horizontal(id="file-buttons"):
                    yield Button("Cancel", id="btn_cancel")
                    yield Button("Open", variant="primary", id="btn_open")

        def on_mount(self) -> None:
            self.query_one("#file_path", Input).focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn_open":
                self.dismiss(self.query_one("#file_path", Input).value)
            else:
                self.dismiss(None)

        def on_input_submitted(self, event: Input.Submitted) -> None:
            self.dismiss(event.value)

        def action_cancel(self) -> None:
            self.dismiss(None)

    class SPLValidatorApp(App[None]):
        CSS = """
        #spl-label {
            height: 1;
            padding: 0 1;
            color: $text-muted;
        }
        #input-section {
            height: 1fr;
            min-height: 8;
            max-height: 60%;
        }
        #spl {
            height: 1fr;
            min-height: 6;
        }
        #controls {
            height: 3;
            padding: 0 1;
            layout: horizontal;
            align: left middle;
        }
        #controls Checkbox { width: auto; margin: 0 2 0 0; }
        #controls Label { width: auto; margin: 0 1 0 0; }
        #controls Select { width: 22; margin: 0 2 0 0; }
        #controls Button { margin: 0 1 0 0; }
        #output-section {
            height: 1fr;
            min-height: 10;
        }
        #summary-log { height: 1fr; }
        #json-output { height: 1fr; }
        """

        BINDINGS = [
            Binding("f5", "validate", "Validate", show=True),
            Binding("ctrl+l", "clear_all", "Clear", show=True),
            Binding("ctrl+o", "open_file", "Open File", show=True),
            Binding("ctrl+s", "save_results", "Save JSON", show=True),
            Binding("q", "quit", "Quit", show=True),
        ]

        TITLE = "SPL Validator"

        def __init__(self) -> None:
            super().__init__()
            self._strict = strict
            self._advice = advice
            self._schema_fields = schema_fields
            self._schema_missing = schema_missing
            self._last_json: Optional[str] = None

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Vertical(id="input-section"):
                yield Static(
                    "SPL Query — paste directly or load with [bold]Ctrl+O[/bold]",
                    id="spl-label",
                )
                yield TextArea(id="spl")
            with Horizontal(id="controls"):
                yield Checkbox("Strict", id="chk_strict", value=self._strict)
                yield Label("Advice:")
                yield Select(
                    ADVICE_CHOICES,
                    id="sel_advice",
                    value=self._advice,
                    allow_blank=False,
                )
                yield Button("Validate (F5)", variant="primary", id="btn_validate")
                yield Button("Clear", id="btn_clear")
                yield Button("Open File", id="btn_open")
            with Vertical(id="output-section"):
                with TabbedContent():
                    with TabPane("Summary", id="tab-summary"):
                        yield RichLog(
                            id="summary-log",
                            wrap=True,
                            highlight=True,
                            markup=True,
                        )
                    with TabPane("JSON", id="tab-json"):
                        yield TextArea(id="json-output", read_only=True)
            yield Footer()

        def on_mount(self) -> None:
            ta = self.query_one("#spl", TextArea)
            if preload_text:
                ta.text = preload_text
            else:
                ta.text = (
                    "index=_internal | head 5\n"
                    "| stats count by sourcetype\n"
                )
            ta.focus()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "btn_validate":
                self.action_validate()
            elif event.button.id == "btn_clear":
                self.action_clear_all()
            elif event.button.id == "btn_open":
                self.action_open_file()

        def action_clear_all(self) -> None:
            """Clear the editor, results, and JSON output."""
            self.query_one("#spl", TextArea).text = ""
            self.query_one("#summary-log", RichLog).clear()
            self.query_one("#json-output", TextArea).text = ""
            self._last_json = None
            self.query_one("#spl", TextArea).focus()

        def action_validate(self) -> None:
            spl = self.query_one("#spl", TextArea).text.strip()
            if not spl:
                log = self.query_one("#summary-log", RichLog)
                log.clear()
                log.write(
                    "[yellow]No SPL to validate. Paste a query or open a file.[/yellow]"
                )
                return

            strict_val = self.query_one("#chk_strict", Checkbox).value
            advice_val = str(self.query_one("#sel_advice", Select).value)

            try:
                enabled = parse_warning_groups(advice_val)
            except ValueError as e:
                log = self.query_one("#summary-log", RichLog)
                log.clear()
                log.write(f"[red]Invalid advice value:[/red] {e}")
                return

            result = validate(
                spl,
                strict=strict_val,
                schema_fields=self._schema_fields,
                schema_missing_severity=self._schema_missing,
            )

            log = self.query_one("#summary-log", RichLog)
            log.clear()

            if result.is_valid:
                log.write("[bold green]✅ VALID SPL[/bold green]\n")
            else:
                log.write("[bold red]❌ INVALID SPL[/bold red]\n")

            if result.errors:
                log.write("[bold red]Errors:[/bold red]")
                for err in result.errors:
                    log.write(f"  [red]•[/red] [bold]{err.code}[/bold] {err.message}")
                    if err.suggestion:
                        log.write(f"    [dim]💡 {err.suggestion}[/dim]")
                log.write("")

            grouped = group_warnings(result.warnings, enabled_groups=enabled)

            if grouped.limits:
                log.write("[bold yellow]📋 Limitations (from limits.conf):[/bold yellow]")
                for w in grouped.limits:
                    log.write(f"  [yellow]•[/yellow] {w.message}")
                log.write("")

            if grouped.optimization:
                log.write("[bold cyan]⚡ Optimization Suggestions:[/bold cyan]")
                for w in grouped.optimization:
                    log.write(f"  [cyan]•[/cyan] {w.message}")
                    if w.suggestion:
                        log.write(f"    [dim]💡 {w.suggestion}[/dim]")
                log.write("")

            other = (
                grouped.style
                + grouped.semantic
                + grouped.schema
                + grouped.diagnostic
                + grouped.other
            )
            if other:
                log.write("[bold]ℹ️  Other Warnings:[/bold]")
                for w in other:
                    log.write(
                        f"  [yellow]•[/yellow] [bold]{w.code}[/bold] {w.message}"
                    )
                    if w.suggestion:
                        log.write(f"    [dim]💡 {w.suggestion}[/dim]")
                log.write("")

            if result.ast:
                log.write(
                    f"[dim]📊 Pipeline: {len(result.ast.commands)} command(s)[/dim]"
                )
                for i, cmd in enumerate(result.ast.commands):
                    log.write(f"  [dim]{i + 1}. {cmd.name}[/dim]")

            payload = build_validation_json_dict(result, warning_groups=advice_val)
            json_str = json.dumps(payload, indent=2)
            self._last_json = json_str
            self.query_one("#json-output", TextArea).text = json_str

        def action_open_file(self) -> None:
            def _on_result(path: Optional[str]) -> None:
                if not path:
                    return
                path = path.strip()
                if not path:
                    return
                p = Path(path).expanduser()
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    self.query_one("#spl", TextArea).text = content
                    log = self.query_one("#summary-log", RichLog)
                    log.clear()
                    log.write(f"[green]Loaded {p}[/green]")
                except (OSError, FileNotFoundError) as e:
                    log = self.query_one("#summary-log", RichLog)
                    log.clear()
                    log.write(f"[red]Error reading file: {e}[/red]")

            self.push_screen(FileOpenScreen(), _on_result)

        def action_save_results(self) -> None:
            if not self._last_json:
                log = self.query_one("#summary-log", RichLog)
                log.write(
                    "[yellow]No results to save. Run validation first.[/yellow]"
                )
                return
            out = Path("spl_validation_result.json")
            out.write_text(self._last_json, encoding="utf-8")
            log = self.query_one("#summary-log", RichLog)
            log.write(f"\n[green]Results saved to {out.resolve()}[/green]")

    SPLValidatorApp().run()


def main() -> None:
    from .cli_config import (
        argparse_defaults_from_config,
        discover_config_path,
        load_cli_defaults,
    )
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

    parser = argparse.ArgumentParser(
        description=(
            "SPL Validator — interactive TUI for complex, multiline SPL queries. "
            "Paste long queries directly, or load from a file with --file."
        ),
    )
    if cfg_arg_defaults:
        parser.set_defaults(**cfg_arg_defaults)
    parser.add_argument("--config", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--advice", type=str, default="optimization")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        metavar="PATH",
        help="Pre-load SPL from a file into the editor",
    )
    parser.add_argument("--schema", type=str, default=None)
    parser.add_argument(
        "--schema-missing", choices=["error", "warning"], default="error"
    )
    parser.add_argument(
        "--registry-pack", action="append", default=[], metavar="PATH"
    )
    args = parser.parse_args()

    try:
        parse_warning_groups(args.advice)
    except ValueError as e:
        parser.error(str(e))

    for pack_path in config_packs + (args.registry_pack or []):
        try:
            load_registry_pack_file(pack_path)
        except (OSError, ValueError) as e:
            print(
                f"Error loading registry pack {pack_path!r}: {e}", file=sys.stderr
            )
            sys.exit(1)

    run_app(
        strict=bool(args.strict),
        advice=str(args.advice),
        schema_path=args.schema,
        schema_missing=str(args.schema_missing),
        preload_file=args.file,
    )


if __name__ == "__main__":
    main()
