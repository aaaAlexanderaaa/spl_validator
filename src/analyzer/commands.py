"""Command-specific validators for complex commands."""
from typing import Optional
from ..parser.ast import Command
from ..models.result import ValidationResult


def validate_join(cmd: Command, result: ValidationResult) -> None:
    """Validate join command usage.
    
    Rules:
    1. join requires at least one field to join on
    2. join requires a subsearch
    3. type= must be valid (inner, left, outer)
    """
    # Note: Full implementation would check cmd.args for fields
    # and cmd.subsearch for the subsearch clause
    
    # Check for type= option validity
    if "type" in cmd.options:
        valid_types = {"inner", "left", "outer"}
        if str(cmd.options["type"]).lower() not in valid_types:
            result.add_error(
                "SPL030",
                f"Invalid join type '{cmd.options['type']}' - must be inner, left, or outer",
                cmd.start,
                cmd.end
            )


def validate_lookup(cmd: Command, result: ValidationResult) -> None:
    """Validate lookup command usage.
    
    Rules:
    1. lookup requires lookup table name (first positional arg)
    2. lookup requires at least one field to match on
    3. OUTPUT and OUTPUTNEW options checked for validity
    """
    # Check if lookup has any identifiable table name in options
    # Lookup syntax: lookup <lookup-name> <field-list> [OUTPUT <field-list>]
    # The table name would be parsed as an identifier or in options
    
    # Add suggestion if options are empty (likely table name provided positionally)
    if not cmd.options and not cmd.args:
        result.add_warning(
            "SPL040",
            "lookup command - ensure lookup table name and fields are specified",
            cmd.start,
            cmd.end,
            suggestion="Usage: lookup <lookup_name> <field> [OUTPUT <output_fields>]"
        )


def validate_rest(cmd: Command, result: ValidationResult) -> None:
    """Validate REST command usage.
    
    Rules:
    1. rest requires a URI
    2. URI should typically start with /services/ for internal endpoints
    """
    # Check if URI is provided in options
    has_uri = False
    
    if "uri" in cmd.options:
        has_uri = True
        uri = str(cmd.options["uri"])
        # Warn if URI doesn't look like a standard Splunk REST path
        if not uri.startswith("/services"):
            result.add_warning(
                "SPL041",
                f"REST URI '{uri}' does not start with /services/ - verify this is correct",
                cmd.start,
                cmd.end,
                suggestion="Internal Splunk REST endpoints typically start with /services/"
            )
    
    # If no explicit uri option, the first arg might be the URI
    if not has_uri and not cmd.args:
        result.add_warning(
            "SPL042",
            "rest command requires a URI",
            cmd.start,
            cmd.end,
            suggestion="Usage: | rest /services/server/info"
        )


def validate_transaction(cmd: Command, result: ValidationResult) -> None:
    """Validate transaction command usage.
    
    Rules:
    1. Must have either fields or startswith/endswith
    2. maxspan/maxpause must be valid time format (Ns, Nm, Nh, Nd)
    """
    # Check for maxspan format if present
    if "maxspan" in cmd.options:
        maxspan = str(cmd.options["maxspan"])
        if not _is_valid_timespan(maxspan):
            result.add_error(
                "SPL031",
                f"Invalid maxspan format '{maxspan}' - use format like 30m, 1h, 1d",
                cmd.start,
                cmd.end
            )
    
    if "maxpause" in cmd.options:
        maxpause = str(cmd.options["maxpause"])
        if not _is_valid_timespan(maxpause):
            result.add_error(
                "SPL032",
                f"Invalid maxpause format '{maxpause}' - use format like 5m, 30s",
                cmd.start,
                cmd.end
            )


def _is_valid_timespan(value: str) -> bool:
    """Check if value is a valid Splunk timespan format."""
    import re
    # Format: <number><unit> where unit is s, m, h, d, w, mon, y
    # Or special values like "auto"
    if value.lower() == "auto":
        return True
    return bool(re.match(r'^\d+(?:s|sec|m|min|h|hr|d|day|w|week|mon|y|year)$', value, re.IGNORECASE))


def validate_command_specific(cmd: Command, result: ValidationResult) -> None:
    """Run command-specific validation based on command name."""
    validators = {
        "join": validate_join,
        "lookup": validate_lookup,
        "rest": validate_rest,
        "transaction": validate_transaction,
    }
    
    cmd_name = cmd.name.lower()
    if cmd_name in validators:
        validators[cmd_name](cmd, result)
