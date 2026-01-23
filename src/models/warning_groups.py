"""Warning grouping and filtering for validator output.

The validator emits many warnings for different purposes (limits, optimization tips,
semantics, schema hints, parser diagnostics). This module classifies warnings into
groups so the CLI can show only the most relevant ones by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .result import ValidationIssue


GROUP_LIMITS = "limits"
GROUP_OPTIMIZATION = "optimization"
GROUP_STYLE = "style"
GROUP_SEMANTIC = "semantic"
GROUP_SCHEMA = "schema"
GROUP_DIAGNOSTIC = "diagnostic"
GROUP_OTHER = "other"

ALL_GROUPS = {
    GROUP_LIMITS,
    GROUP_OPTIMIZATION,
    GROUP_STYLE,
    GROUP_SEMANTIC,
    GROUP_SCHEMA,
    GROUP_DIAGNOSTIC,
    GROUP_OTHER,
}


# "Optimization" warnings are the ones that are primarily about cost/performance:
# CPU/memory/network/work amplification.
_OPTIMIZATION_CODES = {
    # Core best-practice
    "SPL050",
    # Performance/memory tips
    "BEST003",
    "BEST004",
    "BEST005",
    "BEST006",
    "BEST007",
    "BEST008",
    "BEST009",
    "BEST010",
    "BEST013",
    "BEST014",
    "BEST016",
}

_STYLE_CODES = {
    # Determinism/readability/explicitness
    "BEST001",
    "BEST002",
    "BEST011",
    "BEST012",
}

_DIAGNOSTIC_CODES = {
    # Non-SPL text hygiene warnings
    "SPL052",
    "SPL053",
}


def warning_group(issue: ValidationIssue) -> str:
    code = issue.code

    if code.startswith("LIM"):
        return GROUP_LIMITS
    if code.startswith("FLD"):
        return GROUP_SCHEMA
    if code.startswith("SEM-") or code.startswith("SEM"):
        return GROUP_SEMANTIC
    if code in _OPTIMIZATION_CODES:
        return GROUP_OPTIMIZATION
    if code in _STYLE_CODES:
        return GROUP_STYLE
    if code in _DIAGNOSTIC_CODES:
        return GROUP_DIAGNOSTIC

    # Everything else (including many SPL0xx warnings) is treated as "diagnostic/other"
    # and is hidden by default unless explicitly enabled.
    if code.startswith("SPL"):
        return GROUP_DIAGNOSTIC

    if code.startswith("BEST"):
        # BEST codes not explicitly categorized above.
        return GROUP_OTHER

    return GROUP_OTHER


def parse_warning_groups(value: str) -> set[str]:
    """Parse `--advice` / warning-group selector.

    Supported values:
      - "optimization" (default): limits + optimization
      - "all": all groups
      - "none": no warnings
      - comma-separated list: limits,optimization,style,semantic,schema,diagnostic,other
    """
    raw = value.strip().lower()
    if raw in {"optimization", "opt"}:
        return {GROUP_LIMITS, GROUP_OPTIMIZATION}
    if raw == "all":
        return set(ALL_GROUPS)
    if raw in {"none", "off"}:
        return set()

    out: set[str] = set()
    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        # aliases
        if part == "opt":
            part = GROUP_OPTIMIZATION
        if part == "diag":
            part = GROUP_DIAGNOSTIC
        if part == "sem":
            part = GROUP_SEMANTIC

        if part not in ALL_GROUPS:
            raise ValueError(
                f"Unknown warning group '{part}'. Valid groups: {', '.join(sorted(ALL_GROUPS))}."
            )
        out.add(part)
    return out


def filter_warnings(
    warnings: Iterable[ValidationIssue], *, enabled_groups: set[str]
) -> list[ValidationIssue]:
    return [w for w in warnings if warning_group(w) in enabled_groups]


@dataclass(frozen=True)
class WarningGroupSummary:
    limits: list[ValidationIssue]
    optimization: list[ValidationIssue]
    style: list[ValidationIssue]
    semantic: list[ValidationIssue]
    schema: list[ValidationIssue]
    diagnostic: list[ValidationIssue]
    other: list[ValidationIssue]

    @property
    def total(self) -> int:
        return (
            len(self.limits)
            + len(self.optimization)
            + len(self.style)
            + len(self.semantic)
            + len(self.schema)
            + len(self.diagnostic)
            + len(self.other)
        )


def group_warnings(
    warnings: Iterable[ValidationIssue], *, enabled_groups: set[str]
) -> WarningGroupSummary:
    filtered = filter_warnings(warnings, enabled_groups=enabled_groups)

    limits: list[ValidationIssue] = []
    optimization: list[ValidationIssue] = []
    style: list[ValidationIssue] = []
    semantic: list[ValidationIssue] = []
    schema: list[ValidationIssue] = []
    diagnostic: list[ValidationIssue] = []
    other: list[ValidationIssue] = []

    for w in filtered:
        g = warning_group(w)
        if g == GROUP_LIMITS:
            limits.append(w)
        elif g == GROUP_OPTIMIZATION:
            optimization.append(w)
        elif g == GROUP_STYLE:
            style.append(w)
        elif g == GROUP_SEMANTIC:
            semantic.append(w)
        elif g == GROUP_SCHEMA:
            schema.append(w)
        elif g == GROUP_DIAGNOSTIC:
            diagnostic.append(w)
        else:
            other.append(w)

    return WarningGroupSummary(
        limits=limits,
        optimization=optimization,
        style=style,
        semantic=semantic,
        schema=schema,
        diagnostic=diagnostic,
        other=other,
    )

