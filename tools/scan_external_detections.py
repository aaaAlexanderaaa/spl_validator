#!/usr/bin/env python3
"""Scan YAML detection files (e.g. splunk/security_content) and validate embedded `search` SPL.

By default uses ``validate(..., strict=True)`` so **unknown SPL commands** (SPL013) invalidate
a search, matching registry coverage for real-world corpora. Use ``--loose`` for the legacy
behavior where unknown commands are warnings only.

Usage:
  SECURITY_CONTENT_ROOT=/path/to/security_content python3 tools/scan_external_detections.py
  python3 tools/scan_external_detections.py --root /path/to/security_content/detections

Exit code 0 if the scan completed (invalid SPL does not fail the process unless --fail-on-invalid).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import yaml

# Repo root (parent of tools/)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spl_validator.core import validate  # noqa: E402


def _iter_detection_yml(root: Path):
    for path in sorted(root.rglob("*.yml")):
        yield path
    for path in sorted(root.rglob("*.yaml")):
        yield path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=os.environ.get("SECURITY_CONTENT_ROOT", ""),
        help="Directory containing detection YAML (e.g. .../security_content/detections). "
        "Default: $SECURITY_CONTENT_ROOT.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--loose",
        action="store_true",
        help="Unknown commands are warnings only (strict=False). Default: strict=True (unknown command = invalid).",
    )
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Exit 1 if any search is invalid (default: exit 0 after reporting).",
    )
    parser.add_argument(
        "--max-invalid-print",
        type=int,
        default=50,
        help="Max invalid searches to print in text mode (default: 50).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"Error: not a directory: {root}", file=sys.stderr)
        return 2

    strict_mode = not args.loose
    stats: dict = {
        "root": str(root),
        "strict": strict_mode,
        "yaml_files": 0,
        "with_search": 0,
        "valid": 0,
        "invalid": 0,
        "invalid_by_code": Counter(),
    }
    invalid_items: list[dict] = []

    for path in _iter_detection_yml(root):
        stats["yaml_files"] += 1
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:
            invalid_items.append(
                {
                    "file": str(path.relative_to(root)),
                    "yaml_error": str(e),
                }
            )
            continue
        if not isinstance(doc, dict):
            continue
        search = doc.get("search")
        if not isinstance(search, str) or not search.strip():
            continue
        stats["with_search"] += 1
        result = validate(search.strip(), strict=strict_mode)
        if result.is_valid:
            stats["valid"] += 1
            continue
        stats["invalid"] += 1
        codes = [e.code for e in result.errors]
        for c in codes:
            stats["invalid_by_code"][c] += 1
        invalid_items.append(
            {
                "file": str(path.relative_to(root)),
                "codes": codes,
                "errors": [(e.code, e.message) for e in result.errors],
            }
        )

    stats["invalid_by_code"] = dict(stats["invalid_by_code"].most_common())

    if args.format == "json":
        out = dict(stats)
        out["invalid_items"] = invalid_items
        print(json.dumps(out, indent=2))
    else:
        print(f"Root: {root}")
        print(f"strict={strict_mode} (use --loose for unknown-command warnings only)")
        print(f"YAML files scanned: {stats['yaml_files']}")
        print(f"Searches validated: {stats['with_search']}")
        print(f"Valid: {stats['valid']}  Invalid: {stats['invalid']}")
        if stats["invalid_by_code"]:
            print("Error code counts (may overlap per search):")
            for code, n in stats["invalid_by_code"].items():
                print(f"  {code}: {n}")
        shown = 0
        for item in invalid_items:
            if "yaml_error" in item:
                print(f"\n[YAML] {item['file']}: {item['yaml_error']}")
                shown += 1
                continue
            if shown >= args.max_invalid_print:
                break
            print(f"\n--- {item['file']} ---")
            for code, msg in item["errors"]:
                print(f"  [{code}] {msg}")
            shown += 1
        if len(invalid_items) > args.max_invalid_print:
            print(f"\n... ({len(invalid_items) - args.max_invalid_print} more invalid entries truncated)")

    if args.fail_on_invalid and stats["invalid"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
