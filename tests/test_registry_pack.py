#!/usr/bin/env python3
"""Registry pack merge (YAML) integration."""
import os
import sys

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)

from spl_validator.core import validate
from spl_validator.src.registry import get_command, is_known_command
from spl_validator.src.registry.commands import reset_registry_packs
from spl_validator.src.registry.pack import load_registry_pack_file


def test_pack_registers_command_and_alias() -> None:
    reset_registry_packs()
    try:
        pack = os.path.join(_repo_root, "spl_validator", "registry_packs", "example_pack.yaml")
        load_registry_pack_file(pack)
        assert is_known_command("mycustomcmd")
        assert is_known_command("mcc")
        d = get_command("mcc")
        assert d is not None
        assert d.name == "mycustomcmd"
        assert d.type == "transforming"
        r = validate("index=_internal | mycustomcmd")
        assert r.is_valid
    finally:
        reset_registry_packs()


def test_reset_clears_pack() -> None:
    reset_registry_packs()
    try:
        pack = os.path.join(_repo_root, "spl_validator", "registry_packs", "example_pack.yaml")
        load_registry_pack_file(pack)
        assert is_known_command("mycustomcmd")
    finally:
        reset_registry_packs()
    assert not is_known_command("mycustomcmd")
