"""Load optional registry packs (YAML) to extend built-in command metadata."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from .commands import CommandDef, apply_command_pack

_OPTIONAL_ARG_TYPES: dict[str, type] = {
    "str": str,
    "int": int,
    "bool": bool,
    "float": float,
}


def _optional_args_from_mapping(raw: Any) -> dict[str, type]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("optional_args must be a mapping")
    out: dict[str, type] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            raise ValueError("optional_args keys must be strings")
        if isinstance(v, type):
            out[k] = v
        elif isinstance(v, str):
            out[k] = _OPTIONAL_ARG_TYPES.get(v, str)
        else:
            raise ValueError(f"optional_args.{k}: expected type name string, got {type(v).__name__}")
    return out


def command_def_from_dict(name: str, data: dict[str, Any]) -> CommandDef:
    """Build CommandDef from a YAML/JSON-like mapping."""
    ctype = data.get("type")
    if not isinstance(ctype, str) or not ctype.strip():
        raise ValueError(f"command {name!r}: missing or invalid type")
    req = data.get("required_args")
    if req is None:
        req = []
    if not isinstance(req, list) or not all(isinstance(x, str) for x in req):
        raise ValueError(f"command {name!r}: required_args must be a list of strings")
    clauses = data.get("clauses")
    if clauses is None:
        clauses = []
    if not isinstance(clauses, list) or not all(isinstance(x, str) for x in clauses):
        raise ValueError(f"command {name!r}: clauses must be a list of strings")
    limit_key = data.get("limit_key")
    if limit_key is not None and not isinstance(limit_key, str):
        raise ValueError(f"command {name!r}: limit_key must be a string or null")
    semantic_key = data.get("semantic_key")
    if semantic_key is not None and not isinstance(semantic_key, str):
        raise ValueError(f"command {name!r}: semantic_key must be a string or null")
    filters_events = bool(data.get("filters_events", False))
    return CommandDef(
        name=name,
        type=ctype,
        required_args=list(req),
        optional_args=_optional_args_from_mapping(data.get("optional_args")),
        clauses=list(clauses),
        limit_key=limit_key,
        semantic_key=semantic_key,
        filters_events=filters_events,
    )


def load_registry_pack_file(path: str | Path) -> None:
    """Parse a pack file and merge commands into the process-wide registry."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if doc is None:
        return
    if not isinstance(doc, dict):
        raise ValueError(f"{p}: pack root must be a mapping")
    ver = doc.get("version", 1)
    if ver != 1:
        raise ValueError(f"{p}: unsupported pack version {ver!r} (only 1 supported)")
    cmds_raw = doc.get("commands")
    if cmds_raw is None:
        cmds_raw = {}
    if not isinstance(cmds_raw, dict):
        raise ValueError(f"{p}: commands must be a mapping")
    commands: dict[str, CommandDef] = {}
    for raw_name, body in cmds_raw.items():
        if not isinstance(raw_name, str):
            raise ValueError(f"{p}: command keys must be strings")
        if not isinstance(body, dict):
            raise ValueError(f"{p}: command {raw_name!r} body must be a mapping")
        cname = raw_name.lower()
        commands[cname] = command_def_from_dict(cname, body)
    aliases_raw = doc.get("aliases")
    aliases: Optional[dict[str, str]] = None
    if aliases_raw is not None:
        if not isinstance(aliases_raw, dict):
            raise ValueError(f"{p}: aliases must be a mapping")
        aliases = {}
        for a, t in aliases_raw.items():
            if not isinstance(a, str) or not isinstance(t, str):
                raise ValueError(f"{p}: alias keys and targets must be strings")
            aliases[a.lower()] = t.lower()
    apply_command_pack(commands, aliases)


__all__ = ["load_registry_pack_file", "command_def_from_dict"]
