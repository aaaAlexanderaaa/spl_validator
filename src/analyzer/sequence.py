"""Command sequence validation - ensures logical correctness of pipeline."""
from enum import Enum
from typing import Optional
from ..parser.ast import Pipeline, Command
from ..lexer.tokens import Position
from ..models.result import ValidationResult


class DataState(Enum):
    """State of data flowing through pipeline."""
    NONE = "no_data"           # Pipeline start, no data yet
    EVENTS = "events"          # Raw events with _raw, _time, fields
    AGGREGATED = "aggregated"  # After stats/chart - only BY fields + aggregations
    ANY = "any"                # Command works on either


# What each command requires and produces: (requires, produces)
COMMAND_DATA_FLOW: dict[str, tuple[DataState, DataState]] = {
    # === GENERATING ===
    # `search` can start a pipeline (generating), but it can also appear later as a filter.
    # It should not "reset" aggregated data back to EVENTS.
    "search": (DataState.NONE, DataState.ANY),
    "makeresults": (DataState.NONE, DataState.EVENTS),
    "inputlookup": (DataState.NONE, DataState.EVENTS),
    "rest": (DataState.NONE, DataState.EVENTS),
    "tstats": (DataState.NONE, DataState.AGGREGATED),
    "metadata": (DataState.NONE, DataState.EVENTS),
    "datamodel": (DataState.NONE, DataState.EVENTS),
    "dbinspect": (DataState.NONE, DataState.EVENTS),

    # === MACRO (expanded by Splunk; treated as opaque here) ===
    "macro": (DataState.NONE, DataState.ANY),
    
    # === STREAMING (preserve event structure) ===
    "eval": (DataState.ANY, DataState.ANY),
    "where": (DataState.ANY, DataState.ANY),
    "fields": (DataState.ANY, DataState.ANY),
    "rename": (DataState.ANY, DataState.ANY),
    "rex": (DataState.ANY, DataState.ANY),
    "regex": (DataState.ANY, DataState.ANY),
    "lookup": (DataState.ANY, DataState.ANY),
    "dedup": (DataState.ANY, DataState.ANY),
    "head": (DataState.ANY, DataState.ANY),
    "tail": (DataState.ANY, DataState.ANY),
    "sort": (DataState.ANY, DataState.ANY),
    "table": (DataState.ANY, DataState.ANY),
    "bin": (DataState.ANY, DataState.ANY),
    "eventstats": (DataState.ANY, DataState.ANY),
    "streamstats": (DataState.ANY, DataState.ANY),
    "spath": (DataState.ANY, DataState.ANY),
    "makemv": (DataState.ANY, DataState.ANY),
    "mvexpand": (DataState.ANY, DataState.ANY),
    "mvcombine": (DataState.ANY, DataState.ANY),
    "fillnull": (DataState.ANY, DataState.ANY),
    # New streaming commands
    "outputlookup": (DataState.ANY, DataState.ANY),
    "collect": (DataState.ANY, DataState.ANY),
    "sendemail": (DataState.ANY, DataState.ANY),
    "format": (DataState.ANY, DataState.ANY),
    "return": (DataState.ANY, DataState.ANY),
    "addinfo": (DataState.ANY, DataState.ANY),
    "convert": (DataState.ANY, DataState.ANY),
    "fieldformat": (DataState.ANY, DataState.ANY),
    "replace": (DataState.ANY, DataState.ANY),
    "reverse": (DataState.ANY, DataState.ANY),
    "xmlkv": (DataState.EVENTS, DataState.EVENTS),
    "multikv": (DataState.EVENTS, DataState.EVENTS),
    "abstract": (DataState.EVENTS, DataState.EVENTS),
    "highlight": (DataState.ANY, DataState.ANY),
    
    # === TRANSFORMING (changes structure) ===
    "stats": (DataState.ANY, DataState.AGGREGATED),  # BY fields must exist; events without BY field values are filtered
    "chart": (DataState.ANY, DataState.AGGREGATED),  # OVER/BY fields must exist
    "timechart": (DataState.EVENTS, DataState.AGGREGATED),  # Needs _time; BY field must exist
    "top": (DataState.ANY, DataState.AGGREGATED),  # Field must exist
    "rare": (DataState.ANY, DataState.AGGREGATED),  # Field must exist
    "transaction": (DataState.EVENTS, DataState.EVENTS),
    "untable": (DataState.ANY, DataState.ANY),
    "xyseries": (DataState.ANY, DataState.ANY),
    
    # === DATASET (combine data) ===
    "join": (DataState.ANY, DataState.ANY),
    "append": (DataState.ANY, DataState.ANY),
    "appendcols": (DataState.ANY, DataState.ANY),
}



def validate_sequence(pipeline: Pipeline, result: ValidationResult) -> None:
    """Validate command sequence in pipeline.
    
    Checks:
    - First command must be generating (or implicit search)
    - Commands get the data state they require
    """
    if not pipeline.commands:
        result.add_error(
            "SPL005",
            "Empty pipeline - add a search command",
            Position(1, 1, 0),
            Position(1, 1, 0)
        )
        return
    
    state = DataState.NONE
    last_aggregation_cmd: Optional[Command] = None
    mutated_since_aggregation = False
    
    for i, cmd in enumerate(pipeline.commands):
        cmd_name = cmd.name.lower()
        known_flow = cmd_name in COMMAND_DATA_FLOW
        flow = COMMAND_DATA_FLOW.get(cmd_name, (DataState.ANY, DataState.ANY))
        required, produces = flow
        
        # Check: First command must be generating
        if i == 0 and required != DataState.NONE and required != DataState.ANY:
            result.add_error(
                "SPL001",
                f"'{cmd.name}' is not a generating command and cannot start a pipeline. "
                f"Pipeline must start with search, makeresults, inputlookup, or implicit search terms.",
                cmd.start,
                cmd.end
            )
        elif i == 0 and required == DataState.ANY and known_flow:
            # Non-generating non-first command as first
            result.add_error(
                "SPL001", 
                f"'{cmd.name}' requires input data. "
                f"Pipeline must start with search, makeresults, inputlookup, or similar generating command.",
                cmd.start,
                cmd.end
            )
        
        # Check: Command gets what it needs
        if required == DataState.EVENTS and state == DataState.AGGREGATED:
            if cmd_name != "bin":
                result.add_error(
                    "SPL010",
                    f"'{cmd.name}' requires event data but pipeline is already aggregated. "
                    f"Original event fields are gone after transforming commands.",
                    cmd.start,
                    cmd.end
                )

        if cmd_name == "bin" and state == DataState.AGGREGATED:
            target_field = None
            for a in getattr(cmd, "args", []):
                if hasattr(a, "value") and isinstance(a.value, str):
                    target_field = a.value
                    break

            if not target_field:
                result.add_error(
                    "SPL011",
                    f"'bin' requires a target field (commonly _time), but pipeline is already aggregated.",
                    cmd.start,
                    cmd.end,
                )
            else:
                available = False
                if last_aggregation_cmd is not None:
                    last_name = last_aggregation_cmd.name.lower()
                    if last_name == "timechart":
                        available = (target_field == "_time")
                    else:
                        by_clause = last_aggregation_cmd.clauses.get("BY") if hasattr(last_aggregation_cmd, "clauses") else None
                        over_clause = last_aggregation_cmd.clauses.get("OVER") if hasattr(last_aggregation_cmd, "clauses") else None
                        if by_clause and hasattr(by_clause, "fields") and target_field in (by_clause.fields or []):
                            available = True
                        if over_clause and hasattr(over_clause, "fields") and target_field in (over_clause.fields or []):
                            available = True

                if last_aggregation_cmd is not None and not available and not mutated_since_aggregation:
                    result.add_error(
                        "SPL011",
                        f"'bin' target field '{target_field}' may not be available after '{last_aggregation_cmd.name}'.",
                        cmd.start,
                        cmd.end,
                    )

        if cmd_name == "rex" and state == DataState.AGGREGATED:
            field_opt = None
            if hasattr(cmd, "options") and isinstance(cmd.options, dict):
                field_opt = cmd.options.get("field")
            if not field_opt or field_opt == "_raw":
                result.add_error(
                    "SPL010",
                    f"'rex' requires raw event data with _raw field, but pipeline is already "
                    f"aggregated. _raw and original fields are not available after stats/chart/timechart.",
                    cmd.start,
                    cmd.end
                )

        if cmd_name == "spath" and state == DataState.AGGREGATED:
            input_opt = None
            if hasattr(cmd, "options") and isinstance(cmd.options, dict):
                input_opt = cmd.options.get("input")
            if not input_opt or input_opt == "_raw":
                result.add_error(
                    "SPL010",
                    f"'spath' requires raw event data with _raw field unless input=<field> is provided, "
                    f"but pipeline is already aggregated.",
                    cmd.start,
                    cmd.end,
                )

        if cmd_name == "regex" and state == DataState.AGGREGATED:
            field_opt = None
            if hasattr(cmd, "options") and isinstance(cmd.options, dict):
                field_opt = cmd.options.get("field")
                has_field_match = any(k != "field" for k in cmd.options.keys())
                if (field_opt and field_opt != "_raw") or has_field_match:
                    has_field_match = True
            else:
                has_field_match = False
            if not has_field_match:
                result.add_error(
                    "SPL010",
                    f"'regex' requires raw event data with _raw field unless a target field is provided, "
                    f"but pipeline is already aggregated.",
                    cmd.start,
                    cmd.end,
                )

        # Update state
        if produces != DataState.ANY:
            state = produces
            if produces == DataState.AGGREGATED:
                last_aggregation_cmd = cmd
                mutated_since_aggregation = False
            elif produces == DataState.EVENTS:
                last_aggregation_cmd = None
                mutated_since_aggregation = False
        elif state == DataState.NONE:
            # First command didn't set state properly
            state = DataState.EVENTS

        if state == DataState.AGGREGATED and cmd_name in {"eval", "rename", "lookup", "rex", "regex", "spath"}:
            mutated_since_aggregation = True


def get_data_state_after(command_name: str) -> DataState:
    """Get the data state after a command executes."""
    flow = COMMAND_DATA_FLOW.get(command_name.lower())
    if flow:
        return flow[1]
    return DataState.ANY
