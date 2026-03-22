export interface LimitDef {
  limit: number;
  config: string | null;
  message: string;
}

export interface SemanticWarning {
  message: string;
  suggestion?: string;
}

export const LIMITS: Record<string, LimitDef> = {
  sort: {
    limit: 10000,
    config: null,
    message: "sort returns max 10,000 rows by default. Use limit=0 for unlimited.",
  },
  head: { limit: 10, config: null, message: "head returns 10 events if count not specified." },
  tail: { limit: 10, config: null, message: "tail returns 10 events if count not specified." },
  subsearch: {
    limit: 10000,
    config: "[subsearch] maxout",
    message:
      "Subsearches return max 10,000 results by default (SPL Search Reference; see limits.conf [subsearch] maxout on your instance).",
  },
  join_subsearch: {
    limit: 50000,
    config: "[join] subsearch_maxout",
    message: "Join subsearch limited to 50,000 results by default.",
  },
  transaction: {
    limit: 1000,
    config: null,
    message: "Transaction groups max 1,000 events by default. Use maxevents=N to change.",
  },
  stats_memory: {
    limit: 200,
    config: "[default] max_mem_usage_mb",
    message:
      "Stats commands limited to 200MB memory. High cardinality BY fields may exceed this.",
  },
  mvexpand: {
    limit: 500,
    config: "[mvexpand] max_mem_usage_mb",
    message: "mvexpand limited to 500MB memory.",
  },
  append: {
    limit: 50000,
    config: "[subsearch] maxout (append command default)",
    message:
      "append subsearch returns max 50,000 rows by default (append-specific maxout; other subsearches use the lower global default).",
  },
};

export const COMMAND_SEMANTICS: Record<string, SemanticWarning> = {
  by_clause_excludes: {
    message: "BY clause: Events where BY field(s) are null/missing are EXCLUDED from results.",
    suggestion:
      'Use \'fillnull value="(none)" <fields>\' before this command to include events with missing values.',
  },
  filters_events: {
    message: "This command FILTERS events. Non-matching events are removed from results.",
  },
  regex_filters: {
    message: "regex FILTERS events to only those matching the pattern.",
    suggestion: "Use 'rex mode=sed' to modify without filtering.",
  },
  keeps_first: {
    message: "dedup keeps only the FIRST occurrence by default (order is undefined unless sorted).",
    suggestion: "Add 'sort -_time' before dedup for deterministic results.",
  },
  lookup_input_required: {
    message: "Lookup input field must exist. Events with null input field won't match any lookup rows.",
    suggestion: "Ensure input field exists or use 'fillnull' before lookup.",
  },
  join_excludes: {
    message: "Inner join (default) EXCLUDES non-matching rows from results.",
    suggestion: "Use 'type=left' to keep all main search results, or consider 'lookup' instead.",
  },
  transaction_orphans: {
    message: "Events not matching transaction criteria may be ORPHANED (excluded).",
    suggestion: "Use 'keeporphans=true' to include non-matching events.",
  },
  map_expensive: {
    message: "map can be expensive: it runs a subsearch repeatedly and can multiply search load.",
    suggestion:
      "Use 'maxsearches=<N>' and return only needed fields; consider stats/eventstats alternatives.",
  },
  top_rare_excludes: {
    message: "top/rare counts only events where target field EXISTS. Null values are excluded.",
    suggestion: "Use 'fillnull' before to count missing values as a category.",
  },
  stats_by: {
    message: "stats BY clause: Events where BY field is null/missing are EXCLUDED from results.",
    suggestion: "Use fillnull before stats if you need to include events with missing field values.",
  },
  dedup: {
    message: "dedup removes duplicate events, keeping only the first occurrence by default.",
    suggestion: "Use sortby= option to control which event is kept.",
  },
  top: {
    message: "top returns only the N most common values (default 10).",
    suggestion: "Use limit=0 to return all values.",
  },
  rare: {
    message: "rare returns only the N least common values (default 10).",
    suggestion: "Use limit=0 to return all values.",
  },
  join: {
    message: "join is resource-intensive and limited. Inner join excludes non-matching rows.",
    suggestion: "Consider using stats or lookup instead for better performance.",
  },
  transaction: {
    message:
      "transaction is memory-intensive. Events without matching transaction criteria may be orphaned.",
    suggestion: "Use keeporphans=true to include non-matching events.",
  },
  where: {
    message: "where filters events. Events not matching the condition are removed from results.",
  },
  regex: {
    message: "regex filters events to only those matching the pattern.",
    suggestion: "Use rex with mode=sed to modify without filtering.",
  },
};

export function getLimit(key: string): LimitDef | undefined {
  return LIMITS[key];
}

export function getSemanticWarning(key: string): SemanticWarning | undefined {
  return COMMAND_SEMANTICS[key];
}
