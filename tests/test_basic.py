#!/usr/bin/env python3
"""Test script for SPL validator."""
import sys
import os

# Add parent directory to path
# NOTE: This file is intended to be runnable as:
#   python3 validator/tests/test_basic.py
# So we need the repository root (the directory that contains `validator/`) on sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

print("=== SPL Validator Test Suite ===\n")

# Test 1: Lexer
print("Test 1: Lexer")
try:
    from validator.src.lexer import Lexer, TokenType
    lexer = Lexer('index=web | stats count BY host')
    tokens = lexer.tokenize()
    print(f"  ✅ Tokenized: {len(tokens)} tokens")
    print(f"  First 5: {[str(t) for t in tokens[:5]]}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 2: Valid SPL
print("Test 2: Valid SPL (index=web | stats count BY host)")
try:
    from validator.core import validate
    result = validate('index=web | stats count BY host')
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Warnings: {len(result.warnings)}")
    if result.ast:
        print(f"  Commands: {[c.name for c in result.ast.commands]}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 3: Invalid SPL (non-generating first)
print("Test 3: Invalid SPL (| stats count)")
try:
    from validator.core import validate
    result = validate('| stats count')
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {len(result.errors)}")
    for err in result.errors:
        print(f"    - [{err.code}] {err.message}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 4: Registry
print("Test 4: Registry")
try:
    from validator.src.registry import COMMANDS, FUNCTIONS
    print(f"  ✅ Commands: {len(COMMANDS)}")
    print(f"  ✅ Functions: {len(FUNCTIONS)}")
    print(f"  Sample commands: {list(COMMANDS.keys())[:5]}")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 5: Stats aggregation arity
print("Test 5: Invalid stats aggregation arity (index=web | stats sum(bytes, foo))")
try:
    from validator.core import validate
    result = validate('index=web | stats sum(bytes, foo)')
    print(f"  Valid: {result.is_valid}")
    if result.is_valid:
        print("  ❌ Expected invalid SPL due to sum() arity in stats context")
    else:
        codes = [e.code for e in result.errors]
        print(f"  Error codes: {codes}")
        if 'SPL020' in codes:
            print("  ✅ Detected invalid aggregation arity")
        else:
            print("  ❌ Expected SPL020 for invalid aggregation arity")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 6: Function context errors (stats-only function used in eval)
print("Test 6: Invalid eval function context (| makeresults | eval x = dc(foo))")
try:
    from validator.core import validate
    result = validate('| makeresults | eval x = dc(foo)')
    print(f"  Valid: {result.is_valid}")
    codes = [e.code for e in result.errors]
    print(f"  Error codes: {codes}")
    if 'SPL021' in codes:
        print("  ✅ Detected invalid function context")
    else:
        print("  ❌ Expected SPL021 for invalid function context")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 7: Missing pipe between commands (newline is whitespace, not a command separator)
print("Test 7: Missing pipe between bin and sort (index=test | bin _time span=1d\\n sort -cc,test1)")
try:
    from validator.core import validate
    result = validate("index=test | bin _time span=1d\n sort -cc,test1")
    print(f"  Valid: {result.is_valid}")
    codes = [e.code for e in result.errors]
    print(f"  Error codes: {codes}")
    if 'SPL012' in codes:
        print("  ✅ Detected missing pipe")
    else:
        print("  ❌ Expected SPL012 for missing pipe")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 8: Strict mode unknown commands (macros still allowed)
print("Test 8: Strict mode unknown command error (| makeresults | foo bar)")
try:
    from validator.core import validate
    result = validate("| makeresults | foo bar", strict=True)
    print(f"  Valid: {result.is_valid}")
    codes = [e.code for e in result.errors]
    print(f"  Error codes: {codes}")
    if "SPL013" in codes:
        print("  ✅ Unknown command is an error in --strict mode")
    else:
        print("  ❌ Expected SPL013 in --strict mode")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 9: Strict mode allows macros as opaque commands
print("Test 9: Strict mode allows macros (| makeresults | `my_macro(arg)` | stats count)")
try:
    from validator.core import validate
    result = validate("| makeresults | `my_macro(arg)` | stats count", strict=True)
    print(f"  Valid: {result.is_valid}")
    codes = [e.code for e in result.errors]
    print(f"  Error codes: {codes}")
    if "SPL013" in codes:
        print("  ❌ Did not expect unknown command error for macro")
    else:
        print("  ✅ Macro is allowed")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

# Test 10: Missing pipe after initial search (newline is whitespace)
print("Test 10: Missing pipe after initial search (index=test\\n eval -cc,test1)")
try:
    from validator.core import validate
    result = validate("index=test\n eval -cc,test1")
    print(f"  Valid: {result.is_valid}")
    codes = [e.code for e in result.errors]
    print(f"  Error codes: {codes}")
    if "SPL012" in codes:
        print("  ✅ Detected missing pipe after initial search")
    else:
        print("  ❌ Expected SPL012 for missing pipe after initial search")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

print("Test 11: Detections runner (fixtures)")
try:
    import io
    from contextlib import redirect_stdout, redirect_stderr
    from pathlib import Path

    from validator.tools.validate_detections import run

    fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "detections"

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        code = run(
            detections_dir=fixtures_dir,
            start_after=None,
            output_format="json",
            max_yaml_error_logs=0,
            skip_files=set(),
        )
    print(f"  Exit code (expect 2): {code}")
    if code != 2:
        raise AssertionError(f"Expected exit code 2, got {code}")

    buf_out2 = io.StringIO()
    with redirect_stdout(buf_out2), redirect_stderr(io.StringIO()):
        code2 = run(
            detections_dir=fixtures_dir,
            start_after=Path("validator/tests/fixtures/detections/invalid.yml"),
            output_format="json",
            max_yaml_error_logs=0,
            skip_files=set(),
        )
    print(f"  Exit code resume-after-invalid (expect 0): {code2}")
    if code2 != 0:
        raise AssertionError(f"Expected exit code 0, got {code2}")

    print("  ✅ Detections runner works on fixtures")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

print("Test 12: Stats whitespace-separated aggregations (index=web | stats count values(user_id) AS user_id BY host)")
try:
    from validator.core import validate
    result = validate("index=web | stats count values(user_id) AS user_id BY host")
    print(f"  Valid: {result.is_valid}")
    if not result.is_valid:
        print(f"  Error codes: {[e.code for e in result.errors]}")
        print("  ❌ Expected valid SPL for whitespace-separated aggregations")
    else:
        print("  ✅ Parsed whitespace-separated aggregations")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

print("Test 13: No SPL050 for mid-pipeline search (index=main | search foo IN (\"a\",\"b\") | stats count)")
try:
    from validator.core import validate
    result = validate('index=main | search foo IN ("a","b") | stats count')
    print(f"  Valid: {result.is_valid}")
    codes = [w.code for w in result.warnings]
    print(f"  Warning codes: {codes}")
    if "SPL050" in codes:
        print("  ❌ Did not expect SPL050 for mid-pipeline | search")
    else:
        print("  ✅ No SPL050 for mid-pipeline | search")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

print("Test 14: Schema-aware missing field becomes error when known")
try:
    from validator.core import validate
    result = validate(
        "| makeresults | eval x = foo | stats count BY x",
        schema_fields={"_time", "_raw", "bar"},
        schema_missing_severity="error",
    )
    print(f"  Valid: {result.is_valid}")
    codes = [e.code for e in result.errors]
    print(f"  Error codes: {codes}")
    if "FLD001" not in codes:
        print("  ❌ Expected FLD001 error when schema is provided and field is missing")
    else:
        print("  ✅ FLD001 becomes an error with --schema")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

print("Test 15: Schema-aware stats default count output (| stats count BY host | where count>0)")
try:
    from validator.core import validate
    result = validate(
        "index=web | stats count BY host | where count>0",
        schema_fields={"host"},
        schema_missing_severity="error",
    )
    print(f"  Valid: {result.is_valid}")
    if not result.is_valid:
        print(f"  Errors: {[(e.code, e.message) for e in result.errors]}")
        print("  ❌ Expected valid SPL (count should be recognized as stats output)")
    else:
        print("  ✅ count recognized as stats output field")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print()

print("Test 16: Schema-aware top numeric limit is not a field (| top 5 host | where count>0)")
try:
    from validator.core import validate
    result = validate(
        "index=web | top 5 host | where count>0",
        schema_fields={"host"},
        schema_missing_severity="error",
    )
    print(f"  Valid: {result.is_valid}")
    if not result.is_valid:
        print(f"  Errors: {[(e.code, e.message) for e in result.errors]}")
        print("  ❌ Expected valid SPL (numeric limit should not be treated as a field)")
    else:
        print("  ✅ numeric limit not treated as a field; count/host available after top")
except Exception as e:
    print(f"  ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Tests Complete ===")
