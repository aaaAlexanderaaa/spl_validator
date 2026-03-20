"""Limit warnings aligned to Splunk Enterprise 10.0 limits.conf and SPL defaults."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class LimitDef:
    """Definition of a default limit from limits.conf."""
    limit: int
    config: Optional[str]  # limits.conf stanza
    message: str


@dataclass
class SemanticWarning:
    """Definition of a command semantic behavior warning."""
    message: str
    suggestion: Optional[str] = None


# All limits from kb/spl/performance/limits-and-constraints.md
LIMITS: dict[str, LimitDef] = {
    "sort": LimitDef(
        limit=10000,
        config=None,
        message="sort returns max 10,000 rows by default. Use limit=0 for unlimited."
    ),
    "head": LimitDef(
        limit=10,
        config=None,
        message="head returns 10 events if count not specified."
    ),
    "tail": LimitDef(
        limit=10,
        config=None,
        message="tail returns 10 events if count not specified."
    ),
    "subsearch": LimitDef(
        limit=50000,
        config="[subsearch] maxout",
        message="Subsearch returns max 50,000 results by default ([subsearch] maxout in limits.conf; older releases often used 10,000)."
    ),
    "join_subsearch": LimitDef(
        limit=50000,
        config="[join] subsearch_maxout",
        message="Join subsearch limited to 50,000 results by default."
    ),
    "transaction": LimitDef(
        limit=1000,
        config=None,
        message="Transaction groups max 1,000 events by default. Use maxevents=N to change."
    ),
    "stats_memory": LimitDef(
        limit=200,  # MB
        config="[default] max_mem_usage_mb",
        message="Stats commands limited to 200MB memory. High cardinality BY fields may exceed this."
    ),
    "mvexpand": LimitDef(
        limit=500,  # MB
        config="[mvexpand] max_mem_usage_mb",
        message="mvexpand limited to 500MB memory."
    ),
}


# Semantic warnings about command behavior (KB-aligned)
# Sources: aggregation-and-statistics.md, filtering-and-selection.md, data-enrichment.md
COMMAND_SEMANTICS: dict[str, SemanticWarning] = {
    # === BY CLAUSE FIELD REQUIREMENTS (aggregation-and-statistics.md) ===
    "by_clause_excludes": SemanticWarning(
        message="BY clause: Events where BY field(s) are null/missing are EXCLUDED from results.",
        suggestion="Use 'fillnull value=\"(none)\" <fields>' before this command to include events with missing values."
    ),
    
    # === FILTERING COMMANDS (filtering-and-selection.md) ===
    "filters_events": SemanticWarning(
        message="This command FILTERS events. Non-matching events are removed from results.",
        suggestion=None
    ),
    "regex_filters": SemanticWarning(
        message="regex FILTERS events to only those matching the pattern.",
        suggestion="Use 'rex mode=sed' to modify without filtering."
    ),
    "keeps_first": SemanticWarning(
        message="dedup keeps only the FIRST occurrence by default (order is undefined unless sorted).",
        suggestion="Add 'sort -_time' before dedup for deterministic results."
    ),
    
    # === FIELD REQUIREMENTS ===
    "lookup_input_required": SemanticWarning(
        message="Lookup input field must exist. Events with null input field won't match any lookup rows.",
        suggestion="Ensure input field exists or use 'fillnull' before lookup."
    ),
    
    # === JOIN/TRANSACTION BEHAVIOR (data-enrichment.md) ===
    "join_excludes": SemanticWarning(
        message="Inner join (default) EXCLUDES non-matching rows from results.",
        suggestion="Use 'type=left' to keep all main search results, or consider 'lookup' instead."
    ),
    "transaction_orphans": SemanticWarning(
        message="Events not matching transaction criteria may be ORPHANED (excluded).",
        suggestion="Use 'keeporphans=true' to include non-matching events."
    ),

    # === PERFORMANCE CAVEATS ===
    "map_expensive": SemanticWarning(
        message="map can be expensive: it runs a subsearch repeatedly and can multiply search load.",
        suggestion="Use 'maxsearches=<N>' and return only needed fields; consider stats/eventstats alternatives."
    ),
    
    # === COUNT/STATS BEHAVIOR ===
    "top_rare_excludes": SemanticWarning(
        message="top/rare counts only events where target field EXISTS. Null values are excluded.",
        suggestion="Use 'fillnull' before to count missing values as a category."
    ),
    
    # === LEGACY (kept for backwards compatibility) ===
    "stats_by": SemanticWarning(
        message="stats BY clause: Events where BY field is null/missing are EXCLUDED from results.",
        suggestion="Use fillnull before stats if you need to include events with missing field values."
    ),
    "dedup": SemanticWarning(
        message="dedup removes duplicate events, keeping only the first occurrence by default.",
        suggestion="Use sortby= option to control which event is kept."
    ),
    "top": SemanticWarning(
        message="top returns only the N most common values (default 10).",
        suggestion="Use limit=0 to return all values."
    ),
    "rare": SemanticWarning(
        message="rare returns only the N least common values (default 10).",
        suggestion="Use limit=0 to return all values."
    ),
    "join": SemanticWarning(
        message="join is resource-intensive and limited. Inner join excludes non-matching rows.",
        suggestion="Consider using stats or lookup instead for better performance."
    ),
    "transaction": SemanticWarning(
        message="transaction is memory-intensive. Events without matching transaction criteria may be orphaned.",
        suggestion="Use keeporphans=true to include non-matching events."
    ),
    "where": SemanticWarning(
        message="where filters events. Events not matching the condition are removed from results.",
        suggestion=None
    ),
    "regex": SemanticWarning(
        message="regex filters events to only those matching the pattern.",
        suggestion="Use rex with mode=sed to modify without filtering."
    ),
}


def get_limit(key: str) -> Optional[LimitDef]:
    """Get limit definition by key."""
    return LIMITS.get(key)


def get_semantic_warning(key: str) -> Optional[SemanticWarning]:
    """Get semantic warning by key."""
    return COMMAND_SEMANTICS.get(key)
