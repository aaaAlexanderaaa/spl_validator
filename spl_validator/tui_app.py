"""Multiline interactive TUI for SPL validation (requires optional `textual`)."""

from __future__ import annotations

import json
import sys


def run() -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Button, Footer, Header, RichLog, TextArea
    except ImportError:
        print(
            "The TUI requires Textual. Install with: pip install -e '.[tui]'",
            file=sys.stderr,
        )
        sys.exit(1)

    from .core import validate
    from .json_payload import build_validation_json_dict

    class SplValidatorTui(App[None]):
        CSS = """
        Screen { align: center middle; }
        #main { width: 100%; height: 100%; padding: 1 2; }
        #spl { height: 1fr; min-height: 6; border: tall $primary; }
        #out { height: 1fr; min-height: 8; border: tall $accent; }
        """

        BINDINGS = [("q", "quit", "Quit")]

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Vertical(id="main"):
                yield TextArea(id="spl")
                yield Horizontal(Button("Validate", id="go", variant="primary"))
                yield RichLog(id="out", auto_scroll=True, wrap=True)
            yield Footer()

        def on_mount(self) -> None:
            ta = self.query_one("#spl", TextArea)
            ta.text = "index=web | stats count BY host\n"

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id != "go":
                return
            spl = self.query_one("#spl", TextArea).text
            result = validate(spl)
            payload = build_validation_json_dict(result, warning_groups="all")
            log = self.query_one("#out", RichLog)
            log.clear()
            for line in json.dumps(payload, indent=2).splitlines():
                log.write(line)

    SplValidatorTui().run()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
