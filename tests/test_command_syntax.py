#!/usr/bin/env python3
"""Per-command SPL syntax documentation and validation coverage.

Each registered command in ``spl_validator.src.registry.COMMANDS`` has a BNF-style syntax
line (condensed from the Splunk Search Reference) plus a minimal SPL string that this
validator accepts as syntactically valid.

Official Splunk documentation hubs (10.0.x family):

- Using the Help portal: https://help.splunk.com/en/release-notes-and-updates/using-the-help-portal
- Search Reference introduction:
  https://help.splunk.com/en/splunk-cloud-platform/search/search-reference/10.0.2503/introduction/welcome-to-the-search-reference

Command pages live under the same Search Reference tree (e.g. ``lookup``, ``stats``).
"""
from __future__ import annotations

import inspect
import os
import sys
import unittest

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from spl_validator.core import validate
from spl_validator.src.registry import COMMANDS
from spl_validator.src.registry.commands import COMMAND_ALIASES

# (command_name, syntax_line, example_spl) — one row per key in COMMANDS.
COMMAND_SYNTAX_EXAMPLES: list[tuple[str, str, str]] = [
    ("abstract", "abstract [maxterms=<int>] [maxlines=<int>]", "| makeresults count=1 | abstract"),
    ("accum", "accum <field> [AS <newfield>]", "| makeresults count=1 | accum x AS ax"),
    ("addcoltotals", "addcoltotals [labelfield=<f>] [label=<str>]", "| makeresults count=1 | stats count BY host | addcoltotals"),
    ("addinfo", "addinfo", "| makeresults count=1 | addinfo"),
    ("addtotals", "addtotals [row=<bool>] [col=<bool>] [fieldname=<f>] ...", "| makeresults count=1 | addtotals"),
    ("anomalies", "anomalies [<opts>...] [BY <fieldlist>]", "| makeresults count=1 | anomalies BY host"),
    ("anomalousvalue", "anomalousvalue [<opts>...]", "| makeresults count=1 | anomalousvalue"),
    ("anomalydetection", "anomalydetection [<opts>...]", "| makeresults count=1 | anomalydetection"),
    ("append", "append [<opts>...] [ <subsearch> ]", "| makeresults count=1 | append [ search index=_internal | head 1 ]"),
    ("appendcols", "appendcols [override=<bool>] [ <subsearch> ]", "| makeresults count=1 | appendcols [ search index=_internal | head 1 | fields _time ]"),
    ("appendpipe", "appendpipe [ <subsearch> ]", "| makeresults count=1 | appendpipe [ stats count ]"),
    ("apply", "apply <model_name> [ <args> ]", "| makeresults count=1 | apply MyModel"),
    ("autoregress", "autoregress <field> [p=<n>] [AS <newfield>]", "| makeresults count=1 | autoregress x"),
    ("bin", "bin (<bin-opt>=<val>)* <field> [AS <newfield>]", "| makeresults count=1 | bin _time span=1h"),
    ("chart", "chart <agg>(...) ... [OVER <f>] [BY <fieldlist>]", "| makeresults count=1 | chart count BY host"),
    ("cluster", "cluster [t=<float>] [field=<f>] [showcount=<bool>] ...", "| makeresults count=1 | cluster t=0.9 showcount=t"),
    ("collect", "collect index=<name> [sourcetype=<st>] ...", "| makeresults count=1 | collect index=summary"),
    ("convert", "convert (<conv>)(<field>) ... [timeformat=<str>] ...", '| makeresults count=1 | convert timeformat="%Y-%m-%d" ctime(_time)'),
    ("cyberchef", "cyberchef [infield=<f>] [outfield=<f>] [recipe=<str>] [jsonrecipe=<str>]", "| makeresults count=1 | cyberchef infield=x outfield=y"),
    ("datamodel", "datamodel <datamodel_name> [search=<str>] ...", '| datamodel Internal_Audit search=""'),
    ("dbinspect", "dbinspect index=<name> [span=<str>] ...", "| dbinspect index=_internal"),
    ("dedup", "dedup <fieldlist> [keepevents=<bool>] [consecutive=<bool>] ...", "| makeresults count=1 | dedup host"),
    ("deletemodel", "deletemodel [<model_name>]", "| makeresults count=1 | deletemodel MyModel"),
    ("delta", "delta <field> [p=<int>] [AS <newfield>]", "| makeresults count=1 | delta x AS dx"),
    ("erex", "erex <newfield> [examples=<str>] [counterexamples=<str>] ...", '| makeresults count=1 | erex x examples="foo"'),
    ("eval", "eval <field>=<expr> ( , <field>=<expr> )*", "| makeresults count=1 | eval y=1"),
    ("eventcount", "eventcount [summarize=<bool>] [index=<name>] ...", "| eventcount summarize=false index=_internal"),
    ("eventstats", "eventstats <agg>(...) ... [BY <fieldlist>]", "| makeresults count=1 | eventstats count BY host"),
    ("experiment", "experiment [<opts>...]", "| makeresults count=1 | experiment"),
    ("extract", "extract [auto=<bool>] [kvdelim=<str>] ...", "| makeresults count=1 | extract"),
    ("fieldformat", 'fieldformat (<field>="<display>")+', '| makeresults count=1 | fieldformat _time="%Y-%m-%d"'),
    ("fields", "fields [+|-] <fieldlist>", "| makeresults count=1 | fields + host"),
    ("fieldsummary", "fieldsummary [maxvals=<int>]", "| makeresults count=1 | fieldsummary"),
    ("fit", "fit <algorithm> <field> [ <args> ] ...", "| makeresults count=1 | fit LinearRegression x"),
    ("filldown", "filldown [<fieldlist>]", "| makeresults count=1 | filldown"),
    ("fillnull", "fillnull [value=<str>] [<fieldlist>]", '| makeresults count=1 | fillnull value="-"'),
    ("foreach", "foreach <wc_field_pattern> [mode=<str>] ...", '| makeresults count=1 | foreach "*_x"'),
    ("format", "format [quote=<bool>] [maxresults=<int>] ...", "| makeresults count=1 | format"),
    ("from", "from <dataset_spec>", "| from datamodel:Internal_Audit"),
    ("fromjson", "fromjson [field=<f>] [max_depth=<int>]", "| makeresults count=1 | fromjson field=_raw"),
    ("gauge", "gauge <field>", "| makeresults count=1 | gauge x"),
    ("gentimes", "gentimes start=<time> [end=<time>] [increment=<span>]", "| gentimes start=-1d"),
    ("geom", "geom <featureCollection> [featureIdField=<f>] ...", "| makeresults count=1 | geom geo_us_states"),
    ("geomfilter", "geomfilter [min_x=<n>] [max_x=<n>] [min_y=<n>] [max_y=<n>]", "| makeresults count=1 | geomfilter min_x=-1 max_x=1 min_y=-1 max_y=1"),
    ("geostats", "geostats <agg>(...) [BY <fieldlist>]", "| makeresults count=1 | geostats count BY host"),
    ("head", "head [<N>] [limit=<N>] ...", "| makeresults count=1 | head 10"),
    ("highlight", "highlight <term> [<term> ...]", "| makeresults count=1 | highlight foo"),
    ("iconify", "iconify <fieldlist>", "| makeresults count=1 | iconify host"),
    ("inputcsv", "inputcsv <filename> [append=<bool>] [start=<n>] [max=<n>]", "| inputcsv users.csv"),
    ("inputlookup", "inputlookup <lookup_stanza> [append=<bool>] [WHERE <expr>]", "| inputlookup users.csv"),
    ("iplocation", "iplocation <ip_field> [prefix=<str>] [allfields=<bool>]", "| makeresults count=1 | iplocation clientip"),
    ("join", "join (<join-opt>=<val>)* <fieldlist> [ <subsearch> ]", "| makeresults count=1 | join host [ search index=_internal | head 1 | fields host ]"),
    ("kmeans", "kmeans [k=<int>] [cfield=<f>] ...", "| makeresults count=1 | kmeans k=3"),
    ("loadjob", "loadjob <sid_or_uri> [events=<bool>] ...", "| loadjob 123.45"),
    ("listmodels", "listmodels", "| makeresults count=1 | listmodels"),
    (
        "lookup",
        "lookup <lookup_dataset> ( <lookup_field> [AS <event_field>] )* [ (OUTPUT|OUTPUTNEW) ( <dest_field> [AS <event_dest>] )* ]",
        "| makeresults count=1 | lookup users user OUTPUTNEW email AS user_email",
    ),
    ("macro", "`<macro_name>(<args>)?`", "| makeresults count=1 | `foo(bar)`"),
    ("makecontinuous", "makecontinuous [<field>] [span=<str>] [bins=<n>] ...", "| makeresults count=1 | makecontinuous _time span=1h"),
    ("makemv", "makemv [delim=<str>] <field>", '| makeresults count=1 | makemv delim="," foo'),
    ("makeresults", "makeresults [count=<n>] [annotate=<bool>] ...", "| makeresults count=1"),
    ("map", "map search=\"<pipeline>\" [maxsearches=<n>]", '| makeresults count=1 | map search="search index=_internal | head 1"'),
    ("mcatalog", "mcatalog [local=<bool>] [WHERE <expr>]", "| mcatalog metric_name=*"),
    ("mcollect", "mcollect [index=<name>] [split=<str>] ...", "| makeresults count=1 | mcollect index=metrics"),
    ("metadata", "metadata type=<hosts|sources|sourcetypes> [index=<name>]", "| metadata type=sourcetypes"),
    ("mpreview", "mpreview [<opts>...]", "| mpreview metric_name=*"),
    ("mstats", "mstats <agg>(...) [WHERE ...] [BY ...] [span=<str>] ...", "| mstats avg(_value) WHERE index=* BY metric_name span=5m"),
    ("multikv", "multikv [conf=<str>] [rmorig=<bool>] ...", "| makeresults count=1 | multikv"),
    ("multisearch", "multisearch ( [ <subsearch> ] )+", "multisearch [ search index=_internal | head 1 ] [ search index=_audit | head 1 ]"),
    ("mvcombine", "mvcombine <field> [delim=<str>]", "| makeresults count=1 | mvcombine host"),
    ("mvexpand", "mvexpand <field> [limit=<n>]", "| makeresults count=1 | mvexpand foo"),
    ("outlier", "outlier [action=<str>] [field=<f>] ...", "| makeresults count=1 | outlier"),
    ("outputcsv", "outputcsv <filename> [append=<bool>] ...", "| makeresults count=1 | outputcsv out.csv"),
    ("outputlookup", "outputlookup <filename> [append=<bool>] ...", "| makeresults count=1 | outputlookup out.csv"),
    ("pivot", "pivot <datamodel> <object> ...", "| makeresults count=1 | pivot dm obj"),
    ("predict", "predict <field> AS <newfield> [algorithm=<str>] ...", "| makeresults count=1 | predict x AS p algorithm=LLP"),
    ("rangemap", "rangemap field=<f> (<range_label>=<lo>-<hi>)* [default=<label>]", "| makeresults count=1 | rangemap field=x low=0-10 default=severe"),
    ("rare", "rare [<limit>] <fieldlist> [BY <fieldlist>]", "| makeresults count=1 | rare host"),
    ("regex", "regex [field=<f>] <regex> | regex <f>=<regex>", r'| makeresults count=1 | regex "\d+"'),
    ("reltime", "reltime", "| makeresults count=1 | reltime"),
    ("rename", "rename (<field> AS <newfield>)+", "| makeresults count=1 | rename host AS h"),
    ("replace", "replace <wc> WITH <wc> IN <field>", '| makeresults count=1 | replace "a" WITH "b" IN _raw'),
    ("rest", "rest [splunk_server=<host>] <uri> [count=<n>] ...", "| rest splunk_server=local /services/server/info"),
    ("return", "return [<count>] <field> [<field> ...]", "| makeresults count=1 | return 5 host"),
    ("reverse", "reverse", "| makeresults count=1 | reverse"),
    ("rex", "rex [field=<f>] \"<regex>\" [mode=<str>] ...", r'| makeresults count=1 | rex "(?<n>\w+)"'),
    ("sample", "sample [prob=<float>] [count=<n>] [seed=<n>]", "| makeresults count=5 | sample count=2"),
    ("search", "search <bool-expr> | <implicit-search-prefix>", "search index=_internal"),
    ("selfjoin", "selfjoin <fieldlist> [overwrite=<bool>] [max=<n>] ...", "| makeresults count=1 | selfjoin host"),
    ("sendemail", "sendemail to=<email> [subject=<str>] ...", "| makeresults count=1 | sendemail to=a@b.com"),
    ("set", "set (union|intersect|diff) [ <subsearch> ] [ <subsearch> ]", "| set intersect [ search index=_internal | head 1 | fields host ] [ search index=_audit | head 1 | fields host ]"),
    ("sort", "sort [<limit>] [+|-][<opt>]* <fieldlist>", "| makeresults count=1 | sort host"),
    ("spath", "spath [input=<f>] [path=<path>] [output=<f>]", "| makeresults count=1 | spath"),
    ("stats", "stats <agg>(...) ... [BY <fieldlist>]", "| makeresults count=1 | stats count BY host"),
    ("strcat", "strcat [allrequired=<bool>] <source_fields> <dest_field>", "| makeresults count=1 | strcat a b c dest"),
    ("streamstats", "streamstats <agg>(...) ... [BY <fieldlist>]", "| makeresults count=1 | streamstats count BY host"),
    ("summary", "summary [<opts>...]", "| makeresults count=1 | summary"),
    ("table", "table <fieldlist>", "| makeresults count=1 | table host"),
    ("tail", "tail [<N>]", "| makeresults count=1 | tail 5"),
    ("timechart", "timechart (<tc-opt>=<val>)* <agg>(...) [BY <fieldlist>]", "| makeresults count=1 | timechart span=1h count"),
    ("tojson", "tojson [output_field=<f>] [include_nulls=<bool>]", "| makeresults count=1 | tojson"),
    ("top", "top [<limit>] <fieldlist> [BY <fieldlist>]", "| makeresults count=1 | top host"),
    ("transaction", "transaction [<fieldlist>] [maxspan=<span>] [startswith=<str>] [endswith=<str>] ...", "| makeresults count=1 | transaction host maxspan=30m"),
    ("transpose", "transpose [<int>] [column_name=<str>] ...", "| makeresults count=1 | transpose 10"),
    ("trendline", "trendline <trendtype><n> <field> [AS <newfield>]", "| makeresults count=1 | trendline sma2 x AS sma_x"),
    ("tstats", "tstats <agg>(...) FROM ... [WHERE ...] [BY ...]", "| tstats count FROM datamodel=Internal_Audit"),
    ("union", "union [maxout=<n>] [ <subsearch> ] [ <subsearch> ]", "| union [ search index=_internal | head 1 ] [ search index=_audit | head 1 ]"),
    ("uniq", "uniq", "| makeresults count=1 | uniq"),
    ("untable", "untable <key_field> <attribute_field> <value_field>", "| makeresults count=1 | untable k attr val"),
    ("walklex", "walklex [type=<str>] [index=<name>] ...", "| walklex type=terms"),
    ("where", "where <bool-expr>", '| makeresults count=1 | where host="*"'),
    ("x11", "x11 <field> [period=<n>] [AS <newfield>]", "| makeresults count=1 | x11 x AS y period=7"),
    ("xmlkv", "xmlkv [maxinputs=<n>]", "| makeresults count=1 | xmlkv"),
    ("xyseries", "xyseries <x_field> <y_field> <value_field> [grouped=<bool>] ...", "| makeresults count=1 | xyseries x y val"),
]


class CommandSyntaxExamplesTests(unittest.TestCase):
    """Registry completeness and syntax-level validation."""

    def test_registry_has_example_for_every_command(self) -> None:
        names = {c[0] for c in COMMAND_SYNTAX_EXAMPLES}
        self.assertEqual(names, set(COMMANDS.keys()))

    def test_each_example_is_valid_spl(self) -> None:
        for name, syntax, spl in COMMAND_SYNTAX_EXAMPLES:
            with self.subTest(command=name, syntax=syntax):
                result = validate(spl)
                self.assertTrue(
                    result.is_valid,
                    f"SPL should validate for {name!r}.\n  spl={spl!r}\n  errors={[e.code + ': ' + e.message for e in result.errors]}",
                )


class CommandAliasTests(unittest.TestCase):
    """Aliases from ``searchbnf.conf`` map to canonical commands and parse."""

    def test_aliases_resolve_in_registry(self) -> None:
        from spl_validator.src.registry import get_command

        for alias, canonical in COMMAND_ALIASES.items():
            with self.subTest(alias=alias, canonical=canonical):
                d = get_command(alias)
                self.assertIsNotNone(d)
                self.assertEqual(d.name, canonical)

    def test_alias_invocations_validate(self) -> None:
        cases = [
            ("kv", "| makeresults count=1 | kv"),
            ("bucket", "| makeresults count=1 | bucket _time span=1h"),
            ("discretize", "| makeresults count=1 | discretize _time span=1h"),
            ("transam", "| makeresults count=1 | transam host maxspan=30m"),
        ]
        for _alias, spl in cases:
            with self.subTest(spl=spl):
                r = validate(spl)
                self.assertTrue(r.is_valid, [e.message for e in r.errors])


class LookupSyntaxDocumentationTests(unittest.TestCase):
    """Ensure lookup guidance matches Search Reference style OUTPUT / OUTPUTNEW clauses."""

    def test_lookup_validator_doc_mentions_output_clauses(self) -> None:
        from spl_validator.src.analyzer.commands import validate_lookup

        src = inspect.getsource(validate_lookup)
        self.assertIn("OUTPUT", src)
        self.assertIn("OUTPUTNEW", src)


class FieldformatValidationTests(unittest.TestCase):
    def test_bare_fieldformat_errors(self) -> None:
        r = validate("| makeresults count=1 | fieldformat")
        self.assertFalse(r.is_valid)
        self.assertTrue(any(e.code == "SPL014" for e in r.errors))


if __name__ == "__main__":
    unittest.main()
