#!/usr/bin/env python3
"""Unit tests for the SPL parser."""
import sys
import os

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)

from spl_validator.src.lexer import Lexer
from spl_validator.src.parser.parser import ExpressionParser, CommandParser, ParseError
from spl_validator.src.parser.ast import FieldRef, BinaryOp


def test_expression_parser():
    """Test expression parsing."""
    print("=== Expression Parser Tests ===\n")
    passed = 0
    total = 0
    
    test_cases = [
        # (input, description)
        ("1 + 2", "Simple addition"),
        ("field > 100", "Comparison"),
        ("status = 200 AND method = \"GET\"", "Logical AND"),
        ("NOT is_error", "Unary NOT"),
        ("count(field)", "Function call"),
        ("if(a, b, c)", "Multi-arg function"),
        ("round(avg(bytes), 2)", "Nested function"),
        ("x * y + z", "Operator precedence"),
        ("(a + b) * c", "Parentheses"),
        ("dns.sld", "Dotted field reference"),
        ("status == 200", "Double-equals comparison"),
        ("user LIKE \"adm%\"", "LIKE comparison"),
        ("hostname.version.\"test\".'a.b'", "Dot disambiguation (fieldref + concat)"),
    ]
    
    for expr, desc in test_cases:
        total += 1
        try:
            lexer = Lexer(expr)
            tokens = [t for t in lexer.tokenize() if t.type.name != 'EOF']
            parser = ExpressionParser(tokens)
            result = parser.parse_expression()
            if expr == "dns.sld":
                assert isinstance(result, FieldRef) and result.name == "dns.sld"
            if expr == "status == 200":
                assert isinstance(result, BinaryOp) and result.operator == "=="
            if expr == "user LIKE \"adm%\"":
                assert isinstance(result, BinaryOp) and result.operator == "LIKE"
            print(f"  ✅ {desc}: '{expr}' -> {type(result).__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {desc}: '{expr}' -> {e}")
    
    print(f"\n  Expression tests: {passed}/{total}\n")
    return passed, total


def test_command_parser():
    """Test command option parsing."""
    print("=== Command Parser Tests ===\n")
    passed = 0
    total = 0
    
    test_cases = [
        # (tokens_str, expected_options, description)
        ('span="1h"', {"span": "1h"}, "String time span"),  # Quoted strings work
        ("count=10", {"count": 10}, "Single int option"),
        ('field="value"', {"field": "value"}, "String option"),
        ("append=true", {"append": True}, "Boolean option"),
    ]
    
    for tokens_str, expected, desc in test_cases:
        total += 1
        try:
            lexer = Lexer(tokens_str)
            tokens = [t for t in lexer.tokenize() if t.type.name != 'EOF']
            parser = CommandParser(tokens)
            options = parser.parse_options()
            
            if options == expected:
                print(f"  ✅ {desc}: {options}")
                passed += 1
            else:
                print(f"  ❌ {desc}: Expected {expected}, got {options}")
        except Exception as e:
            print(f"  ❌ {desc}: {e}")
    
    print(f"\n  Command parser tests: {passed}/{total}\n")
    return passed, total


def test_lexer():
    """Test lexer tokenization."""
    print("=== Lexer Tests ===\n")
    passed = 0
    total = 0
    
    test_cases = [
        ('index=web | stats count BY host', 9, "Basic SPL"),  # index, =, web, |, stats, count, BY, host, EOF
        ('"hello world"', 2, "String literal"),  # STRING, EOF
        ('a AND b OR c', 6, "Boolean operators"),
        ('field >= 100', 4, "Comparison operator"),
        ('1.5e10', 2, "Scientific notation"),
        ('func(a, b, c)', 9, "Function with args"),  # func, (, a, ,, b, ,, c, ), EOF
        ('dns.sld', 4, "Dotted identifier (split tokens)"),  # dns, ., sld, EOF
        ('a==b', 4, "Double-equals operator"),  # a, ==, b, EOF
        ('a LIKE b', 4, "LIKE keyword operator"),  # a, LIKE, b, EOF
    ]
    
    for spl, expected_count, desc in test_cases:
        total += 1
        try:
            lexer = Lexer(spl)
            tokens = lexer.tokenize()
            
            if len(tokens) == expected_count:
                print(f"  ✅ {desc}: {len(tokens)} tokens")
                passed += 1
            else:
                print(f"  ❌ {desc}: Expected {expected_count} tokens, got {len(tokens)}")
                for t in tokens:
                    print(f"      {t}")
        except Exception as e:
            print(f"  ❌ {desc}: {e}")
    
    print(f"\n  Lexer tests: {passed}/{total}\n")
    return passed, total


def main():
    """Run all parser tests."""
    print("=== SPL Parser Unit Tests ===\n")
    
    total_passed = 0
    total_tests = 0
    
    p, t = test_lexer()
    total_passed += p
    total_tests += t
    
    p, t = test_expression_parser()
    total_passed += p
    total_tests += t
    
    p, t = test_command_parser()
    total_passed += p
    total_tests += t
    
    print(f"=== Total: {total_passed}/{total_tests} passed ===")
    
    if total_passed == total_tests:
        print("✅ All parser tests passed!")
        return 0
    else:
        print(f"❌ {total_tests - total_passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
