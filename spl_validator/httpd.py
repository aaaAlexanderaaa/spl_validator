"""Minimal HTTP API for SPL validation (browser extensions and integrations)."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .core import validate
from .json_payload import build_validation_json_dict, package_version


def _json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, indent=2).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    server_version = "spl-validator-httpd/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def _send_cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        else:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, code: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def _path(self) -> str:
        p = urlparse(self.path).path
        return p.rstrip("/") or "/"

    def do_GET(self) -> None:
        path = self._path()
        if path in ("/", "/health"):
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "spl-validator",
                    "package_version": package_version(),
                },
            )
            return
        self._send_json(404, {"error": "not_found", "path": self.path})

    def do_POST(self) -> None:
        path = self._path()
        if path not in ("/validate", "/v1/validate"):
            self._send_json(404, {"error": "not_found", "path": self.path})
            return

        length_raw = self.headers.get("Content-Length", "0")
        try:
            length = int(length_raw)
        except ValueError:
            self._send_json(400, {"error": "bad_request", "message": "Invalid Content-Length"})
            return
        if length < 0 or length > 8 * 1024 * 1024:
            self._send_json(413, {"error": "payload_too_large", "max_bytes": 8 * 1024 * 1024})
            return

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self._send_json(400, {"error": "invalid_json", "message": str(e)})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "invalid_json", "message": "JSON object required"})
            return

        spl = payload.get("spl")
        if not isinstance(spl, str):
            self._send_json(400, {"error": "invalid_request", "message": "Field 'spl' (string) is required"})
            return

        strict = bool(payload.get("strict", False))
        advice = payload.get("advice", "optimization")
        if not isinstance(advice, str):
            self._send_json(400, {"error": "invalid_request", "message": "Field 'advice' must be a string when provided"})
            return

        result = validate(spl, strict=strict)
        out = build_validation_json_dict(result, warning_groups=advice)
        code = 200 if result.is_valid else 422
        self._send_json(code, out)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="HTTP API for spl-validator (POST /validate)")
    p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="TCP port (default: 8765)")
    args = p.parse_args(argv)

    httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
    sys.stderr.write(
        f"spl-validator httpd listening on http://{args.host}:{args.port} "
        f"(POST /validate, GET /health)\n"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\nShutting down.\n")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
