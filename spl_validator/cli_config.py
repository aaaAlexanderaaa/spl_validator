"""Optional defaults from `.spl-validator.yaml` or `--config` / SPL_VALIDATOR_CONFIG."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml


def discover_config_path(explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("SPL_VALIDATOR_CONFIG")
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None
    local = Path.cwd() / ".spl-validator.yaml"
    return local if local.is_file() else None


def load_cli_defaults(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be a mapping")
    return data


def argparse_defaults_from_config(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Split config into argparse set_defaults keys and registry pack paths."""
    packs: list[str] = []
    if "registry_pack" in raw:
        rp = raw["registry_pack"]
        if isinstance(rp, str):
            packs.append(rp)
        elif isinstance(rp, list):
            for p in rp:
                if isinstance(p, str):
                    packs.append(p)
                else:
                    raise ValueError("registry_pack list entries must be strings")
        else:
            raise ValueError("registry_pack must be a string or list of strings")
    keys = (
        "strict",
        "format",
        "advice",
        "verbose",
        "schema",
        "schema_missing",
        "ast_mode",
        "flow_format",
    )
    defaults = {k: raw[k] for k in keys if k in raw}
    return defaults, packs
