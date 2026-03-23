#!/usr/bin/env python3
"""Unit tests for the SPL parser."""
import pytest

from spl_validator.src.lexer import Lexer
from spl_validator.src.parser.parser import ExpressionParser, CommandParser, ParseError
from spl_validator.src.parser.ast import FieldRef, BinaryOp


# ── Expression parser ────────────────────────────────────────────────

EXPRESSION_CASES = [
    ("1 + 2", "Simple addition"),
    ("field > 100", "Comparison"),
    ('status = 200 AND method = "GET"', "Logical AND"),
    ("NOT is_error", "Unary NOT"),
    ("count(field)", "Function call"),
    ("if(a, b, c)", "Multi-arg function"),
    ("round(avg(bytes), 2)", "Nested function"),
    ("x * y + z", "Operator precedence"),
    ("(a + b) * c", "Parentheses"),
    ("dns.sld", "Dotted field reference"),
    ("status == 200", "Double-equals comparison"),
    ('user LIKE "adm%"', "LIKE comparison"),
    ("hostname.version.\"test\".'a.b'", "Dot disambiguation (fieldref + concat)"),
]


@pytest.mark.parametrize("expr,desc", EXPRESSION_CASES, ids=[d for _, d in EXPRESSION_CASES])
def test_expression_parser(expr: str, desc: str) -> None:
    lexer = Lexer(expr)
    tokens = [t for t in lexer.tokenize() if t.type.name != "EOF"]
    parser = ExpressionParser(tokens)
    result = parser.parse_expression()

    if expr == "dns.sld":
        assert isinstance(result, FieldRef) and result.name == "dns.sld"
    if expr == "status == 200":
        assert isinstance(result, BinaryOp) and result.operator == "=="
    if expr == 'user LIKE "adm%"':
        assert isinstance(result, BinaryOp) and result.operator == "LIKE"


# ── Command parser ───────────────────────────────────────────────────

COMMAND_CASES = [
    ('span="1h"', {"span": "1h"}, "String time span"),
    ("count=10", {"count": 10}, "Single int option"),
    ('field="value"', {"field": "value"}, "String option"),
    ("append=true", {"append": True}, "Boolean option"),
]


@pytest.mark.parametrize(
    "tokens_str,expected,desc",
    COMMAND_CASES,
    ids=[d for _, _, d in COMMAND_CASES],
)
def test_command_parser(tokens_str: str, expected: dict, desc: str) -> None:
    lexer = Lexer(tokens_str)
    tokens = [t for t in lexer.tokenize() if t.type.name != "EOF"]
    parser = CommandParser(tokens)
    options = parser.parse_options()
    assert options == expected, f"{desc}: expected {expected}, got {options}"


# ── Lexer ────────────────────────────────────────────────────────────

LEXER_CASES = [
    ("index=web | stats count BY host", 9, "Basic SPL"),
    ('"hello world"', 2, "String literal"),
    ("a AND b OR c", 6, "Boolean operators"),
    ("field >= 100", 4, "Comparison operator"),
    ("1.5e10", 2, "Scientific notation"),
    ("func(a, b, c)", 9, "Function with args"),
    ("dns.sld", 4, "Dotted identifier (split tokens)"),
    ("a==b", 4, "Double-equals operator"),
    ("a LIKE b", 4, "LIKE keyword operator"),
]


@pytest.mark.parametrize(
    "spl,expected_count,desc",
    LEXER_CASES,
    ids=[d for _, _, d in LEXER_CASES],
)
def test_lexer(spl: str, expected_count: int, desc: str) -> None:
    lexer = Lexer(spl)
    tokens = lexer.tokenize()
    assert len(tokens) == expected_count, (
        f"{desc}: expected {expected_count} tokens, got {len(tokens)}"
    )
