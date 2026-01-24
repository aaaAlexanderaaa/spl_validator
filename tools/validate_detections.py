"""Validate SPL searches embedded in ./detections YAML files.

Designed for large corpora: streams files in deterministic order and exits on the
first invalid SPL search. YAML parsing errors are reported and skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

import yaml

from ..core import validate


REPO_ROOT = Path(__file__).resolve().parents[2]


def _iter_yaml_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if not (name.endswith(".yml") or name.endswith(".yaml")):
                continue
            yield Path(dirpath) / name


def _normalize_start_after(value: str) -> Path:
    p = Path(value)
    if p.is_absolute():
        try:
            return p.resolve().relative_to(REPO_ROOT)
        except Exception:
            return p
    return (REPO_ROOT / p).resolve().relative_to(REPO_ROOT)


def _result_to_json(result) -> dict[str, Any]:
    return {
        "valid": result.is_valid,
        "errors": [
            {
                "code": e.code,
                "message": e.message,
                "line": e.start.line,
                "column": e.start.column,
                "suggestion": e.suggestion,
            }
            for e in result.errors
        ],
        "warnings": [
            {
                "code": w.code,
                "message": w.message,
                "line": w.start.line,
                "column": w.start.column,
                "suggestion": w.suggestion,
            }
            for w in result.warnings
        ],
    }


def _extract_search(doc: Any) -> Optional[str]:
    if not isinstance(doc, dict):
        return None
    search = doc.get("search")
    if search is None:
        return None
    if isinstance(search, str):
        return search
    return None


@dataclass
class RunStats:
    scanned_files: int = 0
    yaml_errors: int = 0
    missing_search: int = 0
    validated_searches: int = 0
    skipped_files: int = 0


def run(
    *,
    detections_dir: Path,
    start_after: Optional[Path],
    output_format: str,
    max_yaml_error_logs: int,
    skip_files: set[Path],
) -> int:
    stats = RunStats()

    found_start_after = start_after is None
    yaml_error_logs = 0

    for path in _iter_yaml_files(detections_dir):
        rel = path.resolve().relative_to(REPO_ROOT)

        if not found_start_after:
            if rel == start_after:
                found_start_after = True
            continue

        if rel in skip_files:
            stats.skipped_files += 1
            continue

        stats.scanned_files += 1
        try:
            with path.open("r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
        except Exception as e:
            stats.yaml_errors += 1
            if yaml_error_logs < max_yaml_error_logs:
                print(f"[YAML-SKIP] {rel}: {e}", file=sys.stderr)
                yaml_error_logs += 1
            continue

        search = _extract_search(doc)
        if search is None:
            stats.missing_search += 1
            continue

        stats.validated_searches += 1
        result = validate(search, strict=False)
        if result.is_valid:
            continue

        payload = {
            "file": str(rel),
            "search": search,
            "result": _result_to_json(result),
            "stats": {
                "scanned_files": stats.scanned_files,
                "skipped_files": stats.skipped_files,
                "yaml_errors": stats.yaml_errors,
                "missing_search": stats.missing_search,
                "validated_searches": stats.validated_searches,
            },
        }
        if output_format == "json":
            print(json.dumps(payload, indent=2))
        else:
            print("INVALID DETECTION SEARCH\n")
            print(f"file: {payload['file']}")
            print("\nsearch:\n")
            print(search.rstrip())
            print("\nerrors:\n")
            for err in payload["result"]["errors"]:
                line = err.get("line")
                col = err.get("column")
                print(f"- [{err['code']}] {err['message']} ({line}:{col})")
                if err.get("suggestion"):
                    print(f"  suggestion: {err['suggestion']}")
        return 2

    if start_after is not None and not found_start_after:
        print(f"Error: --start-after not found: {start_after}", file=sys.stderr)
        return 3

    summary = {
        "ok": True,
        "stats": {
            "scanned_files": stats.scanned_files,
            "skipped_files": stats.skipped_files,
            "yaml_errors": stats.yaml_errors,
            "missing_search": stats.missing_search,
            "validated_searches": stats.validated_searches,
        },
    }
    if output_format == "json":
        print(json.dumps(summary, indent=2))
    else:
        print("No invalid detection searches found.")
        print(
            f"scanned_files={stats.scanned_files} validated_searches={stats.validated_searches} "
            f"yaml_errors={stats.yaml_errors} missing_search={stats.missing_search}"
        )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate YAML 'search' fields under ./detections (streaming, stop on first invalid)."
    )
    parser.add_argument(
        "--detections-dir",
        default=str(REPO_ROOT / "detections"),
        help="Root directory containing detection YAML files (default: ./detections)",
    )
    parser.add_argument(
        "--start-after",
        default=None,
        help="Resume after this repo-relative path (e.g. detections/network/foo.yml).",
    )
    parser.add_argument(
        "--skip-file",
        default=None,
        help="Path to a newline-delimited file of repo-relative detection paths to skip.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format on stop/finish (default: text).",
    )
    parser.add_argument(
        "--max-yaml-error-logs",
        type=int,
        default=20,
        help="Max YAML parse errors to print to stderr before suppressing (default: 20).",
    )
    args = parser.parse_args(argv)

    detections_dir = Path(args.detections_dir)
    if not detections_dir.is_absolute():
        detections_dir = (REPO_ROOT / detections_dir).resolve()

    start_after_path: Optional[Path] = None
    if args.start_after:
        start_after_path = _normalize_start_after(args.start_after)

    skip_files: set[Path] = set()
    if args.skip_file:
        skip_path = Path(args.skip_file)
        if not skip_path.is_absolute():
            skip_path = (REPO_ROOT / skip_path).resolve()
        try:
            for line in skip_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                skip_files.add(_normalize_start_after(stripped))
        except FileNotFoundError:
            print(f"Error: --skip-file not found: {skip_path}", file=sys.stderr)
            return 4

    return run(
        detections_dir=detections_dir,
        start_after=start_after_path,
        output_format=args.format,
        max_yaml_error_logs=args.max_yaml_error_logs,
        skip_files=skip_files,
    )


if __name__ == "__main__":
    raise SystemExit(main())
