"""Schema loading for schema-aware validation and flow sketches.

This module is intentionally lightweight and dependency-free. It supports:
- JSON: {"fields": ["a", "b"], "name": "optional"}
- YAML: same shape (if PyYAML is installed)
- Plain list at top-level (JSON/YAML): ["a", "b"]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class FieldSchema:
    """A declared field universe for a dataset.

    This is treated as an exact starting field set when provided via CLI.
    """

    fields: frozenset[str]
    name: str | None = None


def load_field_schema(path: str | Path) -> FieldSchema:
    p = Path(path)
    raw_text = p.read_text(encoding="utf-8")

    data: Any
    if p.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("YAML schema requires PyYAML to be installed") from e
        data = yaml.safe_load(raw_text)
    else:
        data = json.loads(raw_text)

    name: str | None = None
    fields: list[str] | None = None

    if isinstance(data, list):
        fields = [str(x) for x in data]
    elif isinstance(data, dict):
        name_val = data.get("name")
        if isinstance(name_val, str) and name_val.strip():
            name = name_val.strip()
        if "fields" in data:
            if not isinstance(data["fields"], list):
                raise ValueError("schema 'fields' must be a list")
            fields = [str(x) for x in data["fields"]]
        elif "initial_fields" in data:
            if not isinstance(data["initial_fields"], list):
                raise ValueError("schema 'initial_fields' must be a list")
            fields = [str(x) for x in data["initial_fields"]]
    else:
        raise ValueError("schema must be a list or an object with a 'fields' list")

    if not fields:
        raise ValueError("schema must contain at least one field")

    normalized = []
    for f in fields:
        s = str(f).strip()
        if not s:
            continue
        normalized.append(s)

    if not normalized:
        raise ValueError("schema fields are empty after normalization")

    return FieldSchema(fields=frozenset(normalized), name=name)

