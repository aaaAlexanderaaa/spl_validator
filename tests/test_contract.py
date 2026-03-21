#!/usr/bin/env python3
"""JSON output matches documented schema (portability contract)."""
import json
import os
import sys
from pathlib import Path

import jsonschema

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)

from spl_validator.core import validate
from spl_validator.json_payload import build_cli_json_dict


def _schema() -> dict:
    p = Path(_repo_root) / "docs" / "contract" / "cli-json-output.schema.json"
    return json.loads(p.read_text(encoding="utf-8"))


def test_cli_json_payload_matches_schema() -> None:
    result = validate("index=_internal | head 1")
    payload = build_cli_json_dict(result, warning_groups="all")
    jsonschema.validate(instance=payload, schema=_schema())


def test_invalid_query_still_matches_schema() -> None:
    result = validate("| stats count")
    payload = build_cli_json_dict(result, warning_groups="none")
    jsonschema.validate(instance=payload, schema=_schema())
