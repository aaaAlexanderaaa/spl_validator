"""HTTP API for SPL validation (browser extensions, CLI tooling, integrations)."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional
from urllib.parse import urlparse

from .cli_config import argparse_defaults_from_config, discover_config_path, load_cli_defaults
from .core import validate
from .json_payload import build_validation_json_dict, package_version
from .src.debug.schema import load_field_schema
from .src.models.warning_groups import parse_warning_groups
from .src.registry.pack import load_registry_pack_file
from .web_ui import WEB_UI_HTML


def _cors_headers(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    origin = handler.headers.get("Origin")
    if origin:
        return {
            "Access-Control-Allow-Origin": origin,
            "Vary": "Origin",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        }
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
        server_version = "spl-validator-httpd/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

        def _path(self) -> str:
            p = urlparse(self.path).path
            return p.rstrip("/") or "/"

        def _send_json(self, code: int, payload: Any) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            for k, v in _cors_headers(self).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            for k, v in _cors_headers(self).items():
                self.send_header(k, v)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _send_html(self, code: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = self._path()
            if path == "/health":
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "service": "spl-validator",
                        "package_version": package_version(),
                    },
                )
                return
            if path == "/":
                self._send_html(200, WEB_UI_HTML)
                return
            self._send_json(404, {"error": "not_found", "path": self.path})

        def do_POST(self) -> None:  # noqa: N802
            path = self._path()
            if path not in ("/validate", "/v1/validate"):
                self._send_json(404, {"error": "not_found", "path": self.path})
                return
            try:
                doc = _read_json_body(self, max_body)
            except (ValueError, json.JSONDecodeError) as e:
                self._send_json(400, {"error": "invalid_request", "message": str(e)})
                return
            if not isinstance(doc, dict):
                self._send_json(400, {"error": "invalid_request", "message": "expected JSON object"})
                return
            spl = doc.get("spl")
            if not isinstance(spl, str):
                self._send_json(400, {"error": "invalid_request", "message": "missing string field spl"})
                return
            strict = bool(doc["strict"]) if "strict" in doc else strict_default
            advice = doc["advice"] if isinstance(doc.get("advice"), str) else advice_default
            try:
                parse_warning_groups(advice)
            except ValueError as e:
                self._send_json(400, {"error": "invalid_request", "message": str(e)})
                return

            result = validate(
                spl,
                strict=strict,
                schema_fields=schema_fields,
                schema_missing_severity=schema_missing,
            )
            out = build_validation_json_dict(result, warning_groups=advice)
            code = 200 if result.is_valid else 422
            self._send_json(code, out)

    return ValidateHandler


def main(argv: Optional[list[str]] = None) -> None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", default=None)
    pre_ns, _ = pre.parse_known_args((argv if argv is not None else sys.argv[1:]))
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
        description="SPL Validator HTTP server — serves a web UI at GET /, a validation API at POST /validate, and a health endpoint at GET /health",
    )
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
    parser.add_argument(
        "--open",
        action="store_true",
        help="Auto-open the web UI in the default browser on startup",
    )
    args = parser.parse_args(argv)

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
    httpd = ThreadingHTTPServer((args.host, args.port), handler_cls)
    url = f"http://{args.host}:{args.port}"
    print(
        f"spl-validator-httpd listening on {url}\n"
        f"  Web UI:    {url}/\n"
        f"  API:       POST {url}/validate\n"
        f"  Health:    GET  {url}/health",
        file=sys.stderr,
    )
    if args.open:
        import webbrowser

        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
