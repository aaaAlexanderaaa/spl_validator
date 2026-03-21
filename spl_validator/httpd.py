"""Minimal HTTP server: POST /validate with JSON body (stdlib only)."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

from .cli_config import argparse_defaults_from_config, discover_config_path, load_cli_defaults
from .core import validate
from .json_payload import build_cli_json_dict
from .src.debug.schema import load_field_schema
from .src.models.warning_groups import parse_warning_groups
from .src.registry.pack import load_registry_pack_file


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
    }


def _read_json_body(handler: BaseHTTPRequestHandler, limit: int) -> Optional[dict[str, Any]]:
    n = int(handler.headers.get("Content-Length", "0"))
    if n <= 0:
        return None
    if n > limit:
        raise ValueError(f"body too large (max {limit} bytes)")
    raw = handler.rfile.read(n)
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def make_handler_class(
    *,
    strict_default: bool = False,
    advice_default: str = "optimization",
    schema_path: Optional[str] = None,
    schema_missing: str = "error",
    max_body: int = 2_000_000,
):
    schema_fields: Optional[set[str]] = None
    if schema_path:
        schema = load_field_schema(schema_path)
        schema_fields = set(schema.fields)

    class ValidateHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:  # noqa: A003
            sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))

        def _send(self, code: int, body: bytes, content_type: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            for k, v in _cors_headers().items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            for k, v in _cors_headers().items():
                self.send_header(k, v)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/health"):
                msg = json.dumps({"ok": True, "service": "spl-validator-httpd"}).encode("utf-8")
                self._send(200, msg)
                return
            self._send(404, b'{"error":"not found"}')

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/validate":
                self._send(404, b'{"error":"not found"}')
                return
            try:
                doc = _read_json_body(self, max_body)
            except (ValueError, json.JSONDecodeError) as e:
                self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))
                return
            if not isinstance(doc, dict):
                self._send(400, b'{"error":"expected JSON object"}')
                return
            spl = doc.get("spl")
            if not isinstance(spl, str):
                self._send(400, b'{"error":"missing string field spl"}')
                return
            strict = bool(doc["strict"]) if "strict" in doc else strict_default
            advice = doc["advice"] if isinstance(doc.get("advice"), str) else advice_default
            try:
                parse_warning_groups(advice)
            except ValueError as e:
                self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))
                return

            result = validate(
                spl,
                strict=strict,
                schema_fields=schema_fields,
                schema_missing_severity=schema_missing,
            )
            out = build_cli_json_dict(result, warning_groups=advice)
            self._send(200, json.dumps(out).encode("utf-8"))

    return ValidateHandler


def main() -> None:
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

    parser = argparse.ArgumentParser(description="SPL Validator HTTP — POST /validate JSON {spl, ...}")
    if cfg_arg_defaults:
        parser.set_defaults(**cfg_arg_defaults)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", default=None)
    parser.add_argument("--strict", action="store_true", help="Default strict when request omits strict")
    parser.add_argument(
        "--advice",
        type=str,
        default="optimization",
        help="Default warning groups when request omits advice",
    )
    parser.add_argument("--schema", type=str, default=None)
    parser.add_argument(
        "--schema-missing",
        choices=["error", "warning"],
        default="error",
    )
    parser.add_argument("--registry-pack", action="append", default=[], metavar="PATH")
    parser.add_argument("--max-body", type=int, default=2_000_000)
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

    handler_cls = make_handler_class(
        strict_default=bool(args.strict),
        advice_default=str(args.advice),
        schema_path=args.schema,
        schema_missing=str(args.schema_missing),
        max_body=int(args.max_body),
    )
    httpd = HTTPServer((args.host, args.port), handler_cls)
    print(f"spl-validator-httpd listening on http://{args.host}:{args.port} (POST /validate)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)


if __name__ == "__main__":
    main()
