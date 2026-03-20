"""Simulated SPL data-flow sketch (fields + filter/aggregate boundaries)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..analyzer.fields import FieldFlowStage, compute_field_flow
from ..analyzer.sequence import DataState
from ..parser.ast import Pipeline, Command
from ..registry import get_command


@dataclass(frozen=True)
class FlowStage:
    index: int
    command: str
    command_type: str
    filters_events: bool
    aggregates: bool
    data_in: str
    data_out: str
    fields_known_in: bool
    fields_known_out: bool
    field_actions: list[dict[str, Any]]


def build_flow(
    pipeline: Pipeline,
    *,
    schema_fields: Optional[set[str]] = None,
    conservative_unknown: bool = True,
) -> dict[str, Any]:
    """Build a JSON-serializable flow model."""
    field_flow = compute_field_flow(
        pipeline, schema_fields=schema_fields, conservative_unknown=conservative_unknown
    )
    data_flow = _compute_data_flow(pipeline)

    stages: list[dict[str, Any]] = []
    for i, cmd in enumerate(pipeline.commands):
        cmd_name = cmd.name.lower()
        cmd_def = get_command(cmd_name)
        cmd_type = cmd_def.type if cmd_def is not None else "unknown"
        filters = bool(getattr(cmd_def, "filters_events", False)) if cmd_def is not None else False

        ff = field_flow[i]
        aggregates = (data_flow[i]["in"] != DataState.AGGREGATED.value) and (
            data_flow[i]["out"] == DataState.AGGREGATED.value
        )
        stage = FlowStage(
            index=i,
            command=cmd.name,
            command_type=cmd_type,
            filters_events=filters or _is_filter_like(cmd, i),
            aggregates=aggregates,
            data_in=data_flow[i]["in"],
            data_out=data_flow[i]["out"],
            fields_known_in=ff.known_in,
            fields_known_out=ff.known_out,
            field_actions=_field_actions(cmd, ff),
        )
        stages.append(_stage_to_dict(stage))

    out: dict[str, Any] = {
        "type": "flow",
        "stages": stages,
        "subsearches": _collect_subsearches(pipeline, schema_fields=schema_fields, conservative_unknown=conservative_unknown),
    }
    return out


def flow_to_text(flow: dict[str, Any], *, max_fields: int = 20) -> str:
    lines: list[str] = []
    lines.append("Flow (simulated):")
    for st in flow.get("stages", []):
        idx = st.get("index", 0) + 1
        name = st.get("command", "")
        lines.append(f"[{idx}] {name}  data: {st.get('data_in')} -> {st.get('data_out')}")
        if st.get("filters_events"):
            lines.append("    action: filter")
        if st.get("aggregates"):
            lines.append("    action: aggregate")

        fa = st.get("field_actions", [])
        for act in fa:
            action = act.get("action")
            fields = act.get("fields") or []
            if not fields:
                continue
            shown = fields[:max_fields]
            tail = "" if len(fields) <= max_fields else f" (+{len(fields) - max_fields} more)"
            lines.append(f"    fields {action}: {', '.join(shown)}{tail}")

        if st.get("fields_known_in"):
            lines.append("    fields_in: known")
        else:
            lines.append("    fields_in: unknown")
        if st.get("fields_known_out"):
            lines.append("    fields_out: known")
        else:
            lines.append("    fields_out: unknown")

    subs = flow.get("subsearches") or []
    if subs:
        lines.append("")
        lines.append("Subsearches:")
        for s in subs:
            lines.append(f"- in command {s.get('parent_index', 0) + 1}:")
            lines.extend(["  " + l for l in flow_to_text(s.get("flow", {}), max_fields=max_fields).splitlines()[1:]])

    return "\n".join(lines).rstrip() + "\n"


def flow_to_dot(flow: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("digraph spl_flow {")
    lines.append('  rankdir="LR";')
    lines.append('  node [shape=box,fontname="Helvetica"];')

    stages = flow.get("stages") or []
    for st in stages:
        i = st["index"]
        label = _dot_label_for_stage(st)
        lines.append(f'  n{i} [label="{label}"];')
    for i in range(len(stages) - 1):
        lines.append(f"  n{i} -> n{i+1};")

    # Subsearches as dashed edges to a cluster-like node list (flattened)
    subs = flow.get("subsearches") or []
    sub_id = 0
    for s in subs:
        parent = s.get("parent_index", 0)
        sub_flow = s.get("flow") or {}
        sub_stages = sub_flow.get("stages") or []
        if not sub_stages:
            continue
        lines.append(f'  subgraph cluster_sub{sub_id} {{')
        lines.append('    style="dashed";')
        lines.append(f'    label="subsearch @{parent+1}";')
        for st in sub_stages:
            i = st["index"]
            label = _dot_label_for_stage(st)
            lines.append(f'    s{sub_id}_{i} [label="{label}"];')
        for i in range(len(sub_stages) - 1):
            lines.append(f"    s{sub_id}_{i} -> s{sub_id}_{i+1};")
        lines.append("  }")
        lines.append(f"  n{parent} -> s{sub_id}_0 [style=dashed];")
        sub_id += 1

    lines.append("}")
    return "\n".join(lines) + "\n"


def _stage_to_dict(stage: FlowStage) -> dict[str, Any]:
    return {
        "index": stage.index,
        "command": stage.command,
        "command_type": stage.command_type,
        "filters_events": stage.filters_events,
        "aggregates": stage.aggregates,
        "data_in": stage.data_in,
        "data_out": stage.data_out,
        "fields_known_in": stage.fields_known_in,
        "fields_known_out": stage.fields_known_out,
        "field_actions": stage.field_actions,
    }


def _dot_label_for_stage(st: dict[str, Any]) -> str:
    idx = st.get("index", 0) + 1
    name = st.get("command", "")
    parts = [f"{idx}. {name}"]
    if st.get("filters_events"):
        parts.append("filter")
    if st.get("aggregates"):
        parts.append("aggregate")
    if st.get("fields_known_out"):
        parts.append("fields: known")
    else:
        parts.append("fields: unknown")
    label = "\\n".join(parts)
    return label.replace('"', '\\"')


def _is_filter_like(cmd: Command, index: int) -> bool:
    # Treat mid-pipeline `search` as a filter (base search is generating).
    if cmd.name.lower() == "search":
        return index > 0
    return cmd.name.lower() in {"where", "regex"}


def _field_actions(cmd: Command, ff: FieldFlowStage) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    cmd_name = cmd.name.lower()

    if ff.added_fields:
        actions.append({"action": "add", "fields": sorted(ff.added_fields)})
    if ff.modified_fields:
        actions.append({"action": "modify", "fields": sorted(ff.modified_fields)})
    if ff.removed_fields:
        # For stats/table/fields, this indicates a drop/select action.
        if cmd_name in {"stats", "chart", "timechart", "top", "rare", "table", "fields"}:
            actions.append({"action": "drop", "fields": sorted(ff.removed_fields)})
        else:
            actions.append({"action": "delete", "fields": sorted(ff.removed_fields)})

    return actions


def _compute_data_flow(pipeline: Pipeline) -> list[dict[str, str]]:
    """Compute DataState transitions without emitting errors."""
    from ..analyzer.sequence import COMMAND_DATA_FLOW

    state = DataState.NONE
    out: list[dict[str, str]] = []
    for i, cmd in enumerate(pipeline.commands):
        cmd_name = cmd.name.lower()
        required, produces = COMMAND_DATA_FLOW.get(cmd_name, (DataState.ANY, DataState.ANY))

        # Update state similarly to validate_sequence()
        if produces != DataState.ANY:
            state_out = produces
        else:
            state_out = state

        if state == DataState.NONE and i == 0:
            # First command might be implicit search terms, treated as EVENTS.
            if produces == DataState.ANY:
                state_out = DataState.EVENTS

        out.append({"in": state.value, "out": state_out.value})
        state = state_out
    return out


def _collect_subsearches(
    pipeline: Pipeline,
    *,
    schema_fields: Optional[set[str]],
    conservative_unknown: bool,
) -> list[dict[str, Any]]:
    subs: list[dict[str, Any]] = []
    for idx, cmd in enumerate(pipeline.commands):
        sub = getattr(cmd, "subsearch", None)
        if sub is None or getattr(sub, "pipeline", None) is None:
            continue
        subs.append(
            {
                "parent_index": idx,
                "flow": build_flow(
                    sub.pipeline, schema_fields=schema_fields, conservative_unknown=conservative_unknown
                ),
            }
        )
    return subs
