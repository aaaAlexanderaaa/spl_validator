"""Smoke tests for JSON output contract, CLI stdin/positional, and HTTP API."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_repo_root = Path(__file__).resolve().parent.parent


def test_json_output_contract_keys():
    from spl_validator.contract import OUTPUT_JSON_SCHEMA_VERSION
    from spl_validator.core import validate
    from spl_validator.json_payload import build_validation_json_dict

    result = validate("index=web | stats count BY host")
    payload = build_validation_json_dict(result, warning_groups="optimization")
    assert payload["output_schema_version"] == OUTPUT_JSON_SCHEMA_VERSION
    assert "package_version" in payload
    assert payload["valid"] is True
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["warnings"], list)


def test_cli_json_includes_schema_version():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "spl_validator",
            "--format=json",
            "--spl",
            "index=web | stats count BY host",
        ],
        cwd=_repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "output_schema_version" in data
    assert data["valid"] is True


def test_cli_positional_spl():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "spl_validator",
            "--format=json",
            "index=web | stats count BY host",
        ],
        cwd=_repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["valid"] is True


def test_cli_stdin_flag():
    proc = subprocess.run(
        [sys.executable, "-m", "spl_validator", "--stdin", "--format=json"],
        cwd=_repo_root,
        input="index=web | stats count BY host\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["valid"] is True


def test_cli_preset_security_content_sets_strict_and_advice():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "spl_validator",
            "--format=json",
            "--preset=security_content",
            "--spl",
            "| makeresults | totally_unknown_command_x",
        ],
        cwd=_repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["valid"] is False
    codes = {e["code"] for e in data["errors"]}
    assert "SPL013" in codes


@pytest.fixture()
def httpd_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()

    proc = subprocess.Popen(
        [sys.executable, "-m", "spl_validator.httpd", "--host", "127.0.0.1", "--port", str(port)],
        cwd=_repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 10.0
    last_err = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.2) as r:
                if r.status == 200:
                    break
        except (urllib.error.URLError, OSError) as e:
            last_err = str(e)
            time.sleep(0.05)
    else:
        proc.terminate()
        proc.wait(timeout=5)
        err = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"httpd did not start: {last_err}\n{err}")

    yield port

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_http_health_and_validate(httpd_server: int):
    port = httpd_server
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/validate",
        data=json.dumps({"spl": "index=web | stats count BY host", "strict": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        body = r.read().decode("utf-8")
        assert r.status == 200
    data = json.loads(body)
    assert data["valid"] is True
    assert "output_schema_version" in data


def test_http_validate_invalid_returns_422(httpd_server: int):
    port = httpd_server
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/validate",
        data=json.dumps({"spl": "| stats count", "strict": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as ei:
        urllib.request.urlopen(req, timeout=2)
    assert ei.value.code == 422


def test_http_options_cors_preflight(httpd_server: int):
    port = httpd_server
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/validate",
        method="OPTIONS",
        headers={"Origin": "chrome-extension://fake"},
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        assert r.status == 204
        assert r.headers.get("Access-Control-Allow-Origin")


def test_tui_app_import_does_not_require_textual_at_import_time():
    """`spl_validator.tui_app` should import even when Textual is not installed."""
    import spl_validator.tui_app  # noqa: F401


@pytest.mark.skipif(
    os.environ.get("RUN_TEXTUAL_SMOKE") != "1",
    reason="Set RUN_TEXTUAL_SMOKE=1 to run one-shot Textual smoke (requires textual and a TTY).",
)
def test_tui_headless_smoke():
    env = os.environ.copy()
    env["TEXTUAL_HEADLESS"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "spl_validator.tui_app"],
        cwd=_repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert proc.returncode == 0, proc.stderr
