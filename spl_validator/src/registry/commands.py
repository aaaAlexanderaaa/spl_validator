"""Command registry - SPL commands with metadata."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommandDef:
    """Definition of an SPL command for validation."""
    name: str
    type: str                    # generating, streaming, transforming, dataset
    required_args: list[str]
    optional_args: dict[str, type]
    clauses: list[str]           # BY, AS, OVER, WHERE, OUTPUT, OUTPUTNEW
    limit_key: Optional[str]     # Key into LIMITS dict for warnings
    semantic_key: Optional[str] = None  # Key into COMMAND_SEMANTICS for warnings
    filters_events: bool = False  # True if command removes events from results


# All 28+ commands from KB (no abbreviations, fully explicit)
COMMANDS: dict[str, CommandDef] = {
    # === GENERATING COMMANDS ===
    "search": CommandDef(
        name="search",
        type="generating",
        required_args=[],
        optional_args={"index": str, "sourcetype": str, "earliest": str, "latest": str, "host": str, "source": str},
        clauses=[],
        limit_key=None
    ),
    "makeresults": CommandDef(
        name="makeresults",
        type="generating",
        required_args=[],
        optional_args={"count": int, "annotate": bool, "splunk_server": str, "splunk_server_group": str},
        clauses=[],
        limit_key=None
    ),
    "inputlookup": CommandDef(
        name="inputlookup",
        type="generating",
        required_args=["filename"],
        optional_args={"append": bool, "start": int, "max": int, "strict": bool},
        clauses=["WHERE"],
        limit_key=None
    ),
    "rest": CommandDef(
        name="rest",
        type="generating",
        required_args=["uri"],
        optional_args={"splunk_server": str, "count": int, "timeout": int},
        clauses=[],
        limit_key=None
    ),
    "tstats": CommandDef(
        name="tstats",
        type="generating",
        required_args=["aggregation"],
        optional_args={
            "prestats": bool, "local": bool, "append": bool, "chunk_size": int,
            "summariesonly": bool, "allow_old_summaries": bool,
            "include_reduced_buckets": bool, "span": str
        },
        clauses=["FROM", "WHERE", "BY", "GROUPBY"],
        limit_key=None
    ),
    "metadata": CommandDef(
        name="metadata",
        type="generating",
        required_args=["type"],
        optional_args={"index": str, "splunk_server": str, "splunk_server_group": str},
        clauses=[],
        limit_key=None
    ),
    "datamodel": CommandDef(
        name="datamodel",
        type="generating",
        required_args=["datamodel_name"],
        optional_args={"search": str, "strict_fields": bool, "allow_old_summaries": bool},
        clauses=[],
        limit_key=None
    ),
    "dbinspect": CommandDef(
        name="dbinspect",
        type="generating",
        required_args=["index"],
        optional_args={"span": str, "splunk_server": str},
        clauses=[],
        limit_key=None
    ),

    # === MACRO (expanded by Splunk; treated as opaque here) ===
    "macro": CommandDef(
        name="macro",
        type="generating",
        required_args=["macro"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    
    # === STREAMING COMMANDS ===
    "eval": CommandDef(
        name="eval",
        type="streaming",
        required_args=["assignment"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "where": CommandDef(
        name="where",
        type="streaming",
        required_args=["expression"],
        optional_args={},
        clauses=[],
        limit_key=None,
        semantic_key="filters_events",
        filters_events=True
    ),
    "fields": CommandDef(
        name="fields",
        type="streaming",
        required_args=["field_list"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "rename": CommandDef(
        name="rename",
        type="streaming",
        required_args=["rename_pairs"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "rex": CommandDef(
        name="rex",
        type="streaming",
        required_args=["regex"],
        optional_args={"field": str, "max_match": int, "mode": str, "offset_field": str},
        clauses=[],
        limit_key=None
    ),
    "table": CommandDef(
        name="table",
        type="streaming",
        required_args=["field_list"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "lookup": CommandDef(
        name="lookup",
        type="streaming",
        required_args=["lookup_name", "field"],
        optional_args={"local": bool, "update": bool, "event_time_field": str},
        clauses=["OUTPUT", "OUTPUTNEW"],
        limit_key=None,
        semantic_key="lookup_input_required"
    ),
    "dedup": CommandDef(
        name="dedup",
        type="streaming",
        required_args=["field_list"],
        optional_args={"keepevents": bool, "keepempty": bool, "consecutive": bool, "sortby": str},
        clauses=[],
        limit_key=None,
        semantic_key="keeps_first",
        filters_events=True
    ),
    "spath": CommandDef(
        name="spath",
        type="streaming",
        required_args=[],
        optional_args={"input": str, "path": str, "output": str},
        clauses=[],
        limit_key=None
    ),
    "bin": CommandDef(
        name="bin",
        type="streaming",
        required_args=["field"],
        optional_args={"span": str, "bins": int, "start": int, "end": int, "aligntime": str, "minspan": str, "maxbins": int},
        clauses=["AS"],
        limit_key=None
    ),
    "makemv": CommandDef(
        name="makemv",
        type="streaming",
        required_args=["field"],
        optional_args={"delim": str, "tokenizer": str, "allowempty": bool, "setsv": bool},
        clauses=[],
        limit_key=None
    ),
    "mvexpand": CommandDef(
        name="mvexpand",
        type="streaming",
        required_args=["field"],
        optional_args={"limit": int},
        clauses=[],
        limit_key="mvexpand"
    ),
    "mvcombine": CommandDef(
        name="mvcombine",
        type="streaming",
        required_args=["field"],
        optional_args={"delim": str},
        clauses=[],
        limit_key=None
    ),
    "fillnull": CommandDef(
        name="fillnull",
        type="streaming",
        required_args=[],
        optional_args={"value": str},
        clauses=[],
        limit_key=None
    ),
    "eventstats": CommandDef(
        name="eventstats",
        type="streaming",
        required_args=["aggregation"],
        optional_args={"allnum": bool},
        clauses=["BY"],
        limit_key="stats_memory",
        semantic_key="by_clause_excludes"
    ),
    
    # === CENTRALIZED STREAMING COMMANDS ===
    "head": CommandDef(
        name="head",
        type="streaming_centralized",
        required_args=[],
        optional_args={"limit": int, "keeplast": bool, "null": bool},
        clauses=[],
        limit_key="head",
        filters_events=True
    ),
    "tail": CommandDef(
        name="tail",
        type="streaming_centralized",
        required_args=[],
        optional_args={"limit": int},
        clauses=[],
        limit_key="tail",
        filters_events=True
    ),
    "streamstats": CommandDef(
        name="streamstats",
        type="streaming_centralized",
        required_args=["aggregation"],
        optional_args={
            "window": int, "time_window": str, "global": bool, "current": bool,
            "reset_on_change": bool, "reset_before": str, "reset_after": str,
            "allnum": bool
        },
        clauses=["BY"],
        limit_key="stats_memory",
        semantic_key="by_clause_excludes"
    ),
    
    # === TRANSFORMING COMMANDS ===
    "stats": CommandDef(
        name="stats",
        type="transforming",
        required_args=["aggregation"],
        optional_args={"partitions": int, "allnum": bool, "delim": str},
        clauses=["BY", "dedup_splitvals"],
        limit_key="stats_memory",
        semantic_key="by_clause_excludes"
    ),
    "chart": CommandDef(
        name="chart",
        type="transforming",
        required_args=["aggregation"],
        optional_args={
            "limit": int, "agg": str, "useother": bool, "usenull": bool,
            "nullstr": str, "otherstr": str, "sep": str, "format": str, "cont": bool
        },
        clauses=["OVER", "BY", "dedup_splitvals"],
        limit_key="stats_memory",
        semantic_key="by_clause_excludes"
    ),
    "timechart": CommandDef(
        name="timechart",
        type="transforming",
        required_args=["aggregation"],
        optional_args={
            "span": str, "bins": int, "limit": int, "useother": bool, "usenull": bool,
            "nullstr": str, "otherstr": str, "fixedrange": bool, "partial": bool,
            "cont": bool, "sep": str, "format": str, "agg": str
        },
        clauses=["BY", "dedup_splitvals"],
        limit_key="stats_memory",
        semantic_key="by_clause_excludes"
    ),
    "top": CommandDef(
        name="top",
        type="transforming",
        required_args=["field_list"],
        optional_args={"limit": int, "countfield": str, "percentfield": str, "showcount": bool, "showperc": bool, "useother": bool, "otherstr": str},
        clauses=["BY"],
        limit_key=None,
        semantic_key="top_rare_excludes"
    ),
    "rare": CommandDef(
        name="rare",
        type="transforming",
        required_args=["field_list"],
        optional_args={"limit": int, "countfield": str, "percentfield": str, "showcount": bool, "showperc": bool},
        clauses=["BY"],
        limit_key=None,
        semantic_key="top_rare_excludes"
    ),
    "sort": CommandDef(
        name="sort",
        type="transforming",
        required_args=["field_list"],
        optional_args={"limit": int, "d": bool, "num": str, "str": str, "ip": str, "auto": str},
        clauses=[],
        limit_key="sort"
    ),
    "transaction": CommandDef(
        name="transaction",
        type="transforming",
        required_args=[],
        optional_args={
            "maxspan": str, "maxpause": str, "maxevents": int, "maxopentxn": int,
            "maxopenevents": int, "keeporphans": bool, "mvlist": bool, "delim": str,
            "connected": bool, "unifyends": bool, "name": str
        },
        clauses=["startswith", "endswith"],
        limit_key="transaction",
        semantic_key="transaction_orphans",
        filters_events=True
    ),
    
    # === DATASET PROCESSING COMMANDS ===
    "join": CommandDef(
        name="join",
        type="dataset",
        required_args=["field_list"],
        optional_args={
            "type": str, "usetime": bool, "earlier": bool, "max": int,
            "overwrite": bool, "return_multivalue": bool,
            "left": str, "right": str  # aliases for join
        },
        clauses=["WHERE"],
        limit_key="join_subsearch",
        semantic_key="join_excludes",
        filters_events=True
    ),
    "append": CommandDef(
        name="append",
        type="dataset",
        required_args=[],
        optional_args={"extendtimerange": bool, "maxtime": int, "maxout": int, "timeout": int},
        clauses=[],
        limit_key="append"
    ),
    "appendcols": CommandDef(
        name="appendcols",
        type="dataset",
        required_args=[],
        optional_args={"override": bool},
        clauses=[],
        limit_key="subsearch"
    ),
    
    # === OUTPUT COMMANDS ===
    "outputlookup": CommandDef(
        name="outputlookup",
        type="streaming",
        required_args=["filename"],
        optional_args={"append": bool, "create_empty": bool, "max": int, "key_field": str, "createinapp": bool, "override_if_empty": bool},
        clauses=[],
        limit_key=None
    ),
    "collect": CommandDef(
        name="collect",
        type="streaming",
        required_args=["index"],
        optional_args={"source": str, "sourcetype": str, "host": str, "marker": str, "testmode": bool, "run_in_preview": bool},
        clauses=[],
        limit_key=None
    ),
    "sendemail": CommandDef(
        name="sendemail",
        type="streaming",
        required_args=["to"],
        optional_args={"cc": str, "bcc": str, "from": str, "subject": str, "message": str, "server": str, "format": str, "inline": bool, "sendresults": bool, "sendpdf": bool, "sendcsv": bool},
        clauses=[],
        limit_key=None
    ),
    
    # === SUBSEARCH-RELATED COMMANDS ===
    "format": CommandDef(
        name="format",
        type="streaming",
        required_args=[],
        optional_args={"quote": bool, "maxresults": int, "mvsep": str, "emptystr": str},
        clauses=[],
        limit_key=None
    ),
    "return": CommandDef(
        name="return",
        type="streaming",
        required_args=[],
        optional_args={"count": int},
        clauses=[],
        limit_key=None
    ),
    
    # === UTILITY COMMANDS ===
    "addinfo": CommandDef(
        name="addinfo",
        type="streaming",
        required_args=[],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "convert": CommandDef(
        name="convert",
        type="streaming",
        required_args=["conversion"],
        optional_args={"timeformat": str, "mktime": bool},
        clauses=[],
        limit_key=None
    ),
    "fieldformat": CommandDef(
        name="fieldformat",
        type="streaming",
        required_args=["field", "format"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "regex": CommandDef(
        name="regex",
        type="streaming",
        required_args=["regex"],
        optional_args={"field": str},
        clauses=[],
        limit_key=None,
        semantic_key="regex_filters",
        filters_events=True
    ),
    "replace": CommandDef(
        name="replace",
        type="streaming",
        required_args=["wc_string", "with_string"],
        optional_args={},
        clauses=["IN"],
        limit_key=None
    ),
    "reverse": CommandDef(
        name="reverse",
        type="streaming",
        required_args=[],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "xmlkv": CommandDef(
        name="xmlkv",
        type="streaming",
        required_args=[],
        optional_args={"maxinputs": int},
        clauses=[],
        limit_key=None
    ),
    "multikv": CommandDef(
        name="multikv",
        type="streaming",
        required_args=[],
        optional_args={"conf": str, "copyattrs": bool, "fields": str, "filter": str, "forceheader": int, "header": str, "multitable": bool, "noheader": bool, "rmorig": bool},
        clauses=[],
        limit_key=None
    ),
    "abstract": CommandDef(
        name="abstract",
        type="streaming",
        required_args=[],
        optional_args={"maxterms": int, "maxlines": int},
        clauses=[],
        limit_key=None
    ),
    "highlight": CommandDef(
        name="highlight",
        type="streaming",
        required_args=["terms"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "untable": CommandDef(
        name="untable",
        type="transforming",
        required_args=["key_field", "attribute_field", "value_field"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "xyseries": CommandDef(
        name="xyseries",
        type="transforming",
        required_args=["x_field", "y_field", "value_field"],
        optional_args={"grouped": bool, "sep": str, "format": str},
        clauses=[],
        limit_key=None
    ),
    
    # === ADDITIONAL HIGH-PRIORITY COMMANDS ===
    "foreach": CommandDef(
        name="foreach",
        type="streaming",
        required_args=["field_pattern"],
        optional_args={"mode": str, "fieldstr": str, "matchstr": str},
        clauses=[],
        limit_key=None
    ),
    "filldown": CommandDef(
        name="filldown",
        type="streaming",
        required_args=[],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "iplocation": CommandDef(
        name="iplocation",
        type="streaming",
        required_args=["field"],
        optional_args={"prefix": str, "allfields": bool, "lang": str},
        clauses=[],
        limit_key=None
    ),
    "from": CommandDef(
        name="from",
        type="generating",
        required_args=["dataset"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "map": CommandDef(
        name="map",
        type="generating",
        required_args=["search"],
        optional_args={"maxsearches": int},
        clauses=[],
        limit_key=None,
        semantic_key="map_expensive"
    ),
    "gentimes": CommandDef(
        name="gentimes",
        type="generating",
        required_args=["start"],
        optional_args={"end": str, "increment": str},
        clauses=[],
        limit_key=None
    ),
    "union": CommandDef(
        name="union",
        type="generating",
        required_args=[],
        optional_args={"maxtime": int, "maxout": int},
        clauses=[],
        limit_key=None
    ),
    "multisearch": CommandDef(
        name="multisearch",
        type="generating",
        required_args=[],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "delta": CommandDef(
        name="delta",
        type="streaming",
        required_args=["field"],
        optional_args={"p": int},
        clauses=["AS"],
        limit_key=None
    ),
    "trendline": CommandDef(
        name="trendline",
        type="streaming",
        required_args=["trendtype", "field"],
        optional_args={},
        clauses=["AS"],
        limit_key=None
    ),
    "accum": CommandDef(
        name="accum",
        type="streaming",
        required_args=["field"],
        optional_args={},
        clauses=["AS"],
        limit_key=None
    ),
    "autoregress": CommandDef(
        name="autoregress",
        type="streaming",
        required_args=["field"],
        optional_args={"p": str},
        clauses=["AS"],
        limit_key=None
    ),
    "transpose": CommandDef(
        name="transpose",
        type="transforming",
        required_args=[],
        optional_args={"int": int, "column_name": str, "header_field": str, "include_empty": bool},
        clauses=[],
        limit_key=None
    ),
    "cluster": CommandDef(
        name="cluster",
        type="transforming",
        required_args=[],
        optional_args={"t": float, "delims": str, "showcount": bool, "countfield": str, "labelfield": str, "field": str, "labelonly": bool, "match": str},
        clauses=[],
        limit_key=None
    ),
    "inputcsv": CommandDef(
        name="inputcsv",
        type="generating",
        required_args=["filename"],
        optional_args={"append": bool, "start": int, "max": int, "events": bool},
        clauses=[],
        limit_key=None
    ),
    "outputcsv": CommandDef(
        name="outputcsv",
        type="streaming",
        required_args=["filename"],
        optional_args={"append": bool, "create_empty": bool, "override_if_empty": bool, "singlefile": bool},
        clauses=[],
        limit_key=None
    ),
    "loadjob": CommandDef(
        name="loadjob",
        type="generating",
        required_args=["job_id"],
        optional_args={"artifact_offset": int, "ignore_running": bool, "events": bool, "job_delegate": str},
        clauses=[],
        limit_key=None
    ),
    "set": CommandDef(
        name="set",
        type="dataset",
        required_args=["operation"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "selfjoin": CommandDef(
        name="selfjoin",
        type="dataset",
        required_args=["field_list"],
        optional_args={"overwrite": bool, "keepsingle": bool, "max": int},
        clauses=[],
        limit_key=None
    ),
    "pivot": CommandDef(
        name="pivot",
        type="transforming",
        required_args=["datamodel", "object"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),

    # === MISSING HIGH-PRIORITY COMMANDS (from searchbnf.conf) ===

    # Field extraction command (alias: kv)
    "extract": CommandDef(
        name="extract",
        type="streaming",
        required_args=[],
        optional_args={
            "segment": bool, "reload": bool, "kvdelim": str, "pairdelim": str,
            "limit": int, "maxchars": int, "mv_add": bool, "clean_keys": bool,
            "keep_empty_vals": bool, "auto": bool
        },
        clauses=[],
        limit_key=None
    ),

    # Append pipe command
    "appendpipe": CommandDef(
        name="appendpipe",
        type="dataset",
        required_args=[],
        optional_args={"run_in_preview": bool},
        clauses=[],
        limit_key=None
    ),

    # Geographic commands
    "geostats": CommandDef(
        name="geostats",
        type="transforming",
        required_args=["aggregation"],
        optional_args={
            "latfield": str, "longfield": str, "globallimit": int, "locallimit": int,
            "binspanlat": float, "binspanlong": float, "maxzoomlevel": int,
            "translatetoxy": bool, "outputlatfield": str, "outputlongfield": str
        },
        clauses=["BY"],
        limit_key=None
    ),
    "geom": CommandDef(
        name="geom",
        type="streaming",
        required_args=["featureCollection"],
        optional_args={"featureIdField": str, "gen": float, "min_x": float, "min_y": float, "max_x": float, "max_y": float},
        clauses=[],
        limit_key=None
    ),
    "geomfilter": CommandDef(
        name="geomfilter",
        type="streaming",
        required_args=[],
        optional_args={"min_x": float, "min_y": float, "max_x": float, "max_y": float},
        clauses=[],
        limit_key=None
    ),

    # Analytics/ML commands
    "kmeans": CommandDef(
        name="kmeans",
        type="transforming",
        required_args=[],
        optional_args={
            "k": int, "maxiters": int, "reps": int, "t": float,
            "cfield": str, "showcentroid": bool, "dt": str
        },
        clauses=[],
        limit_key=None
    ),
    "predict": CommandDef(
        name="predict",
        type="transforming",
        required_args=["field"],
        optional_args={
            "algorithm": str, "future_timespan": int, "holdback": int,
            "period": int, "upper": int, "lower": int, "correlate": str,
            "suppress": str
        },
        clauses=["AS"],
        limit_key=None
    ),
    "anomalies": CommandDef(
        name="anomalies",
        type="transforming",
        required_args=[],
        optional_args={
            "threshold": float,
            "labelonly": bool,
            "normalize": bool,
            "maxvalues": int,
            "field": str,
            "denylist": str,
            "denylistthreshold": float,
            "action": str,
        },
        clauses=["BY"],
        limit_key=None
    ),
    "anomalousvalue": CommandDef(
        name="anomalousvalue",
        type="transforming",
        required_args=[],
        optional_args={
            "action": str, "pthresh": float, "minsupcount": int,
            "minsupfreq": float, "maxanofreq": float
        },
        clauses=[],
        limit_key=None
    ),
    "anomalydetection": CommandDef(
        name="anomalydetection",
        type="transforming",
        required_args=[],
        optional_args={
            "method": str, "action": str, "pthresh": float,
            "cutoff": float, "field": str
        },
        clauses=[],
        limit_key=None
    ),
    "outlier": CommandDef(
        name="outlier",
        type="transforming",
        required_args=[],
        optional_args={
            "action": str, "param": float, "uselower": bool,
            "mark": bool, "field": str
        },
        clauses=[],
        limit_key=None
    ),
    "x11": CommandDef(
        name="x11",
        type="transforming",
        required_args=["field"],
        optional_args={"period": int, "mult": bool},
        clauses=["AS"],
        limit_key=None
    ),

    # Utility commands
    "rangemap": CommandDef(
        name="rangemap",
        type="streaming",
        required_args=["field"],
        optional_args={"default": str},
        clauses=[],
        limit_key=None
    ),
    "strcat": CommandDef(
        name="strcat",
        type="streaming",
        required_args=["field_list", "dest_field"],
        optional_args={"allrequired": bool},
        clauses=[],
        limit_key=None
    ),

    # Additional missing commands from searchbnf.conf
    "addcoltotals": CommandDef(
        name="addcoltotals",
        type="transforming",
        required_args=[],
        optional_args={"labelfield": str, "label": str},
        clauses=[],
        limit_key=None
    ),
    "addtotals": CommandDef(
        name="addtotals",
        type="streaming",
        required_args=[],
        optional_args={
            "row": bool, "col": bool, "fieldname": str, "labelfield": str, "label": str
        },
        clauses=[],
        limit_key=None
    ),
    "erex": CommandDef(
        name="erex",
        type="streaming",
        required_args=["field"],
        optional_args={"examples": str, "counterexamples": str, "fromfield": str, "maxtrainers": int},
        clauses=[],
        limit_key=None
    ),
    "eventcount": CommandDef(
        name="eventcount",
        type="generating",
        required_args=[],
        optional_args={"summarize": bool, "report_size": bool, "index": str, "list_vix": bool},
        clauses=[],
        limit_key=None
    ),
    "fieldsummary": CommandDef(
        name="fieldsummary",
        type="transforming",
        required_args=[],
        optional_args={"maxvals": int},
        clauses=[],
        limit_key=None
    ),
    "reltime": CommandDef(
        name="reltime",
        type="streaming",
        required_args=[],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "tojson": CommandDef(
        name="tojson",
        type="streaming",
        required_args=[],
        optional_args={"output_field": str, "include_nulls": bool},
        clauses=[],
        limit_key=None
    ),
    "fromjson": CommandDef(
        name="fromjson",
        type="streaming",
        required_args=[],
        optional_args={"field": str, "max_depth": int},
        clauses=[],
        limit_key=None
    ),
    "gauge": CommandDef(
        name="gauge",
        type="transforming",
        required_args=["field"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "iconify": CommandDef(
        name="iconify",
        type="streaming",
        required_args=["field_list"],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
    "makecontinuous": CommandDef(
        name="makecontinuous",
        type="streaming",
        required_args=[],
        optional_args={"span": str, "bins": int, "start": int, "end": int},
        clauses=[],
        limit_key=None
    ),
    "uniq": CommandDef(
        name="uniq",
        type="streaming",
        required_args=[],
        optional_args={},
        clauses=[],
        limit_key=None
    ),
}


# Command aliases (from searchbnf.conf)
# Maps alias -> canonical command name
COMMAND_ALIASES: dict[str, str] = {
    "kv": "extract",
    "bucket": "bin",
    "discretize": "bin",
    "transam": "transaction",
}


# Generating commands that can start a pipeline
GENERATING_COMMANDS = {name for name, cmd in COMMANDS.items() if cmd.type == "generating"}


def get_command(name: str) -> Optional[CommandDef]:
    """Get command definition by name (case-insensitive).

    Resolves command aliases to their canonical names.
    """
    key = name.lower()
    # Resolve alias to canonical name
    canonical = COMMAND_ALIASES.get(key, key)
    return COMMANDS.get(canonical)


def is_generating_command(name: str) -> bool:
    """Check if command is a generating command."""
    key = name.lower()
    canonical = COMMAND_ALIASES.get(key, key)
    return canonical in GENERATING_COMMANDS


def is_known_command(name: str) -> bool:
    """Check if command is known to the validator."""
    key = name.lower()
    canonical = COMMAND_ALIASES.get(key, key)
    return canonical in COMMANDS
