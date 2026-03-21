#!/usr/bin/env python3
"""CLI input paths: stdin and positional query."""
import json
import os
import subprocess
import sys

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(args: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "spl_validator", *args],
        input=stdin,
        text=True,
        capture_output=True,
        cwd=_repo_root,
    )


def test_stdin_pipe_json() -> None:
    r = _run(["--format", "json"], stdin="index=_internal | head 1\n")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["valid"] is True
    assert "errors" in data and "warnings" in data


def test_positional_query() -> None:
    r = _run(["--format", "json", "index=_internal | head 1"])
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["valid"] is True
