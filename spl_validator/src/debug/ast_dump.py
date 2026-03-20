"""AST dumping helpers (summarized or full) for debugging and tooling."""

from __future__ import annotations

from dataclasses import is_dataclass, fields as dataclass_fields
from typing import Any


def dump_ast(node: Any, *, mode: str = "summary", max_depth: int = 20, max_list: int = 200) -> Any:
    """Dump AST as a JSON-serializable structure.

    mode:
      - summary: pipeline + per-command shallow summary
      - full: recursive dataclass serialization
    """
    if node is None:
        return None

    mode = mode.lower().strip()
    if mode not in {"summary", "full"}:
        raise ValueError("mode must be 'summary' or 'full'")

    if mode == "summary":
        return _dump_summary(node, max_list=max_list)

    return _dump_full(node, depth=0, max_depth=max_depth, max_list=max_list)


def _pos(p: Any) -> dict[str, int] | None:
    if p is None:
        return None
    line = getattr(p, "line", None)
    column = getattr(p, "column", None)
    offset = getattr(p, "offset", None)
    if isinstance(line, int) and isinstance(column, int) and isinstance(offset, int):
        return {"line": line, "column": column, "offset": offset}
    return None


def _dump_summary(pipeline: Any, *, max_list: int) -> Any:
    commands = getattr(pipeline, "commands", None)
    if not isinstance(commands, list):
        return {"type": pipeline.__class__.__name__}

    out_cmds: list[dict[str, Any]] = []
    for cmd in commands[:max_list]:
        out_cmds.append(
            {
                "name": getattr(cmd, "name", ""),
                "start": _pos(getattr(cmd, "start", None)),
                "end": _pos(getattr(cmd, "end", None)),
                "options": sorted(list(getattr(cmd, "options", {}).keys()))
                if isinstance(getattr(cmd, "options", None), dict)
                else [],
                "clauses": sorted(list(getattr(cmd, "clauses", {}).keys()))
                if isinstance(getattr(cmd, "clauses", None), dict)
                else [],
                "args_count": len(getattr(cmd, "args", []) or []),
                "has_subsearch": getattr(cmd, "subsearch", None) is not None,
            }
        )

    return {
        "type": pipeline.__class__.__name__,
        "start": _pos(getattr(pipeline, "start", None)),
        "end": _pos(getattr(pipeline, "end", None)),
        "commands": out_cmds,
        "truncated": len(commands) > max_list,
    }


def _dump_full(obj: Any, *, depth: int, max_depth: int, max_list: int) -> Any:
    if depth > max_depth:
        return {"type": "...", "truncated": True}

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, list):
        items = obj[:max_list]
        return {
            "type": "list",
            "items": [_dump_full(x, depth=depth + 1, max_depth=max_depth, max_list=max_list) for x in items],
            "truncated": len(obj) > max_list,
        }

    if isinstance(obj, dict):
        # Keep keys stable and stringified
        keys = list(obj.keys())[:max_list]
        return {
            "type": "dict",
            "items": {
                str(k): _dump_full(obj[k], depth=depth + 1, max_depth=max_depth, max_list=max_list) for k in keys
            },
            "truncated": len(obj) > max_list,
        }

    # Position-like
    p = _pos(obj)
    if p is not None and obj.__class__.__name__ == "Position":
        return {"type": "Position", **p}

    if is_dataclass(obj):
        out: dict[str, Any] = {"type": obj.__class__.__name__}
        for f in dataclass_fields(obj):
            name = f.name
            value = getattr(obj, name)
            if name in ("start", "end"):
                out[name] = _pos(value)
            else:
                out[name] = _dump_full(value, depth=depth + 1, max_depth=max_depth, max_list=max_list)
        return out

    # Fallback: string repr
    return {"type": obj.__class__.__name__, "repr": repr(obj)}

