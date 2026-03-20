"""Optional integration scan of splunk/security_content (or compatible) detection trees."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from spl_validator.core import validate  # noqa: E402


def _detections_root() -> Path | None:
    raw = os.environ.get("SECURITY_CONTENT_ROOT", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.is_dir() else None


pytestmark = pytest.mark.skipif(
    _detections_root() is None,
    reason="Set SECURITY_CONTENT_ROOT to .../security_content/detections to run",
)


def test_security_content_scan_completes_with_sane_counts() -> None:
    """Scan all YAML searches; do not require 100% valid (upstream has known YAML/SPL edge cases)."""
    root = _detections_root()
    assert root is not None

    with_search = 0
    valid = 0
    invalid = 0
    for path in sorted(root.rglob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        search = doc.get("search")
        if not isinstance(search, str) or not search.strip():
            continue
        with_search += 1
        if validate(search.strip(), strict=False).is_valid:
            valid += 1
        else:
            invalid += 1

    assert with_search >= 1500, "expected a full security_content detections tree"
    assert valid >= with_search * 0.95, (
        f"unexpected regression: valid {valid}/{with_search} "
        f"(see docs/security_content_validation.md)"
    )
