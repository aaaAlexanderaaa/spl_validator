"""Subsearch validation - validates [...] subsearch blocks."""
from typing import Optional
from ..parser.ast import Pipeline, Command, Subsearch
from ..models.result import ValidationResult
from ..registry import is_generating_command


def validate_subsearch(parent_cmd: Command, subsearch: Subsearch, result: ValidationResult) -> None:
    """Validate a subsearch block.
    
    Rules:
    1. Subsearch must start with a generating command
    2. Subsearch should typically end with return, table, or fields
    """
    if subsearch.pipeline is None or not subsearch.pipeline.commands:
        result.add_error(
            "SPL022",
            "Empty subsearch - subsearch must contain at least one command",
            subsearch.start,
            subsearch.end
        )
        return

    parent = parent_cmd.name.lower()
    if parent in {"appendpipe", "foreach"}:
        return
    
    # Rule 1: Must start with generating command
    first_cmd = subsearch.pipeline.commands[0]
    if not is_generating_command(first_cmd.name):
        result.add_error(
            "SPL021",
            f"Subsearch must start with a generating command (search, inputlookup, etc.), "
            f"got '{first_cmd.name}'",
            first_cmd.start,
            first_cmd.end,
            suggestion="Add 'search' at the beginning of the subsearch"
        )
    
    # Rule 2: Should end with limiting command (warning, not error)
    last_cmd = subsearch.pipeline.commands[-1]
    limiting_commands = {"return", "table", "fields", "format", "head"}
    if last_cmd.name.lower() not in limiting_commands:
        result.add_warning(
            "BEST010",
            f"Subsearch should typically end with return, table, or fields to limit output",
            last_cmd.start,
            last_cmd.end,
            suggestion=f"Consider adding '| return 100 field' or '| table field' at the end"
        )


def validate_all_subsearches(pipeline: Pipeline, result: ValidationResult) -> None:
    """Find and validate all subsearches in a pipeline."""
    for cmd in pipeline.commands:
        if cmd.subsearch:
            validate_subsearch(cmd, cmd.subsearch, result)
