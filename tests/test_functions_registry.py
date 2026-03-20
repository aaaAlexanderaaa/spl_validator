#!/usr/bin/env python3
"""Tests for SPL function registry: syntax metadata, categories, arity, and command mapping."""
from __future__ import annotations

import os
import sys

import pytest

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)

from spl_validator.core import validate
from spl_validator.src.registry.functions import (
    EVAL_EXPRESSION_COMMANDS,
    FUNCTIONS,
    STATS_AGGREGATION_COMMANDS,
    SPLUNK_REF_EVALUATION,
    SPLUNK_REF_STATISTICAL_AND_CHARTING,
    FunctionDef,
    get_function,
    iter_percentile_examples,
    validate_function_arity,
    validate_function_context,
)


ALLOWED_CATEGORIES = frozenset(
    {
        "evaluation",
        "statistical",
        "evaluation_and_statistical",
        "statistical_charting",
    }
)


@pytest.mark.parametrize("name", sorted(FUNCTIONS.keys()))
def test_each_function_registry_entry(name: str) -> None:
    """One test node per function so regressions name the exact symbol."""
    fd = FUNCTIONS[name]
    assert fd.name == name
    assert fd.syntax.strip()
    assert fd.category in ALLOWED_CATEGORIES
    assert fd.splunk_reference_chapter()
    assert fd.command_usage_summary()


def test_registry_unique_names_and_nonempty_syntax() -> None:
    seen: set[str] = set()
    for name, fd in FUNCTIONS.items():
        assert name == name.lower(), f"registry key must be lowercase: {name!r}"
        assert name not in seen, f"duplicate function key {name!r}"
        seen.add(name)
        assert fd.syntax.strip(), f"{name!r} must document a syntax string"
        assert fd.category in ALLOWED_CATEGORIES, f"unknown category for {name!r}: {fd.category!r}"


def test_splunk_reference_chapter_mapping() -> None:
    for _name, fd in FUNCTIONS.items():
        ch = fd.splunk_reference_chapter()
        assert SPLUNK_REF_EVALUATION in ch or SPLUNK_REF_STATISTICAL_AND_CHARTING in ch, ch


def test_command_usage_matches_context_flags() -> None:
    """Evaluation-only functions must not claim stats aggregation; stats-only must not claim eval."""
    for name, fd in FUNCTIONS.items():
        summary = fd.command_usage_summary().lower()
        allows_eval = fd.allows_eval_expression_commands()
        allows_stats = fd.allows_stats_aggregation_position()
        assert allows_eval == (fd.context in ("eval", "both")), name
        assert allows_stats == (fd.context in ("stats", "both")), name
        if allows_eval:
            assert "eval" in summary and "where" in summary, name
        if allows_stats:
            assert "stats" in summary, name
        if fd.context == "eval":
            assert "stats" not in summary or "nested" in summary, name


def test_eval_and_stats_command_constants() -> None:
    assert "eval" in EVAL_EXPRESSION_COMMANDS
    assert "where" in EVAL_EXPRESSION_COMMANDS
    assert "fieldformat" in EVAL_EXPRESSION_COMMANDS
    assert "stats" in STATS_AGGREGATION_COMMANDS
    assert "chart" in STATS_AGGREGATION_COMMANDS
    assert "timechart" in STATS_AGGREGATION_COMMANDS


def test_arity_boundaries_per_context() -> None:
    for name, fd in FUNCTIONS.items():
        for ctx in ("eval", "stats"):
            spec = get_function(name, context=ctx)
            if spec is None:
                continue
            if spec.min_args > 0:
                err = validate_function_arity(name, spec.min_args - 1, context=ctx)
                assert err is not None, f"{name} {ctx}: expected underflow error"
            assert validate_function_arity(name, spec.min_args, context=ctx) is None, (
                f"{name} {ctx}: min arity should be valid"
            )
            if spec.max_args is not None:
                assert (
                    validate_function_arity(name, spec.max_args + 1, context=ctx) is not None
                ), f"{name} {ctx}: expected overflow error"
                assert validate_function_arity(name, spec.max_args, context=ctx) is None, (
                    f"{name} {ctx}: max arity should be valid"
                )


def test_mvindex_documented_like_user_example() -> None:
    fd = FUNCTIONS["mvindex"]
    assert "mvindex" in fd.syntax.lower()
    assert fd.min_args == 2 and fd.max_args == 3


def test_percentile_functions_meta_and_arity() -> None:
    for fn in iter_percentile_examples():
        g = get_function(fn, context="stats")
        assert g is not None, fn
        assert g.context == "stats"
        assert g.category == "statistical"
        assert validate_function_arity(fn, 0, context="stats") is not None
        assert validate_function_arity(fn, 1, context="stats") is None
        assert validate_function_arity(fn, 2, context="stats") is not None
        assert get_function(fn, context="eval") is None
        assert validate_function_context(fn, "eval") is not None


def test_sum_avg_min_max_stats_vs_eval_arity() -> None:
    for fn in ("sum", "avg", "min", "max"):
        ev = get_function(fn, context="eval")
        st = get_function(fn, context="stats")
        assert ev is not None and st is not None
        assert ev.max_args is None
        assert st.max_args == 1
        assert validate_function_arity(fn, 2, context="stats") is not None
        assert validate_function_arity(fn, 2, context="eval") is None


def test_stats_only_rejected_in_eval_validator() -> None:
    assert validate_function_context("count", "eval") is not None
    assert validate_function_context("dc", "eval") is not None
    assert validate_function_context("mean", "eval") is not None


def test_eval_only_rejected_at_stats_aggregation() -> None:
    for fn in ("mvindex", "md5", "if", "split"):
        assert validate_function_context(fn, "stats") is not None


def test_unknown_function_spl023_eval_and_stats() -> None:
    r_eval = validate("| makeresults | eval x=notarealfunction(1)")
    assert not r_eval.is_valid
    assert any(e.code == "SPL023" and "notarealfunction" in e.message for e in r_eval.errors)

    r_stats = validate("| makeresults | stats notarealfunction(field)")
    assert not r_stats.is_valid
    assert any(e.code == "SPL023" for e in r_stats.errors)


def test_end_to_end_spl_samples() -> None:
    valid_samples = [
        '| makeresults | eval x=mvindex(mvfield,0,1)',
        '| makeresults | where mvcount(mvfield) > 0',
        '| makeresults | stats count sum(bytes) BY host',
        '| makeresults | stats sparkline(count) BY host',
        '| makeresults | stats perc95(response_time)',
    ]
    for spl in valid_samples:
        r = validate(spl)
        assert r.is_valid, f"{spl!r} -> {[e.message for e in r.errors]}"

    bad = [
        '| makeresults | stats mvindex(field,1)',
        '| makeresults | eval x=count()',
    ]
    for spl in bad:
        r = validate(spl)
        assert not r.is_valid, spl


def test_category_counts_reasonable() -> None:
    by_cat: dict[str, int] = {}
    for fd in FUNCTIONS.values():
        by_cat[fd.category] = by_cat.get(fd.category, 0) + 1
    assert by_cat.get("evaluation", 0) > 50
    assert by_cat.get("statistical", 0) > 10


def test_function_def_is_frozen() -> None:
    fd = FunctionDef("x", 0, 0, "eval", "evaluation", "x()")
    try:
        fd.name = "y"  # type: ignore[misc]
        raise AssertionError("FunctionDef should be frozen")
    except AttributeError:
        pass
