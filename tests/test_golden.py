#!/usr/bin/env python3
"""Golden file test runner for SPL validator."""
import json
import os
import sys

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _repo_root)

from spl_validator.contract import GOLDEN_FILE_FORMAT_VERSION
from spl_validator.core import validate


def run_golden_tests(test_file: str) -> tuple[int, int]:
    """Run tests from a golden file.
    
    Returns: (passed, total)
    """
    with open(test_file) as f:
        data = json.load(f)

    gv = int(data.get("golden_format_version", 1))
    if gv > GOLDEN_FILE_FORMAT_VERSION:
        print(
            f"  ❌ Unsupported golden_format_version={gv} in {test_file} "
            f"(runner supports up to {GOLDEN_FILE_FORMAT_VERSION})"
        )
        return 0, 1
    
    passed = 0
    total = 0
    
    for test in data["tests"]:
        total += 1
        name = test["name"]
        spl = test["spl"]
        expected = test["expected"]
        
        result = validate(spl)
        
        # Check validity
        expected_valid = expected.get("valid", True)
        if result.is_valid != expected_valid:
            print(f"  ❌ {name}: Expected valid={expected_valid}, got {result.is_valid}")
            for err in result.errors:
                print(f"       Error: [{err.code}] {err.message}")
            continue
        
        # Check error codes if specified
        if "error_codes" in expected:
            actual_codes = [e.code for e in result.errors]
            for code in expected["error_codes"]:
                if code not in actual_codes:
                    print(f"  ❌ {name}: Expected error code {code}, got {actual_codes}")
                    continue
        
        # Check error count if specified
        if "error_count" in expected:
            if len(result.errors) != expected["error_count"]:
                print(f"  ❌ {name}: Expected {expected['error_count']} errors, got {len(result.errors)}")
                continue

        # Check warning codes if specified
        if "warning_codes" in expected:
            actual_warn_codes = [w.code for w in result.warnings]
            missing = [c for c in expected["warning_codes"] if c not in actual_warn_codes]
            if missing:
                print(f"  ❌ {name}: Expected warning codes {missing}, got {actual_warn_codes}")
                continue

        if "warning_codes_not" in expected:
            actual_warn_codes = [w.code for w in result.warnings]
            present = [c for c in expected["warning_codes_not"] if c in actual_warn_codes]
            if present:
                print(f"  ❌ {name}: Did not expect warning codes {present}, got {actual_warn_codes}")
                continue

        # Check warning message/suggestion content if specified
        def _warning_text() -> str:
            chunks = []
            for w in result.warnings:
                chunks.append(w.message)
                if w.suggestion:
                    chunks.append(w.suggestion)
            return "\n".join(chunks)

        if "warning_text_contains" in expected:
            text = _warning_text()
            missing = [s for s in expected["warning_text_contains"] if s not in text]
            if missing:
                print(f"  ❌ {name}: Expected warning text to contain {missing}")
                continue

        if "warning_text_not_contains" in expected:
            text = _warning_text()
            present = [s for s in expected["warning_text_not_contains"] if s in text]
            if present:
                print(f"  ❌ {name}: Did not expect warning text to contain {present}")
                continue
        
        print(f"  ✅ {name}")
        passed += 1
    
    return passed, total


def main():
    """Run all golden file tests."""
    print("=== SPL Validator Golden File Tests ===\n")
    
    test_dir = os.path.join(os.path.dirname(__file__), "golden")
    total_passed = 0
    total_tests = 0
    
    for filename in sorted(os.listdir(test_dir)):
        if not filename.endswith(".json"):
            continue
        
        filepath = os.path.join(test_dir, filename)
        print(f"📁 {filename}:")
        
        passed, total = run_golden_tests(filepath)
        total_passed += passed
        total_tests += total
        print()
    
    print(f"=== Results: {total_passed}/{total_tests} passed ===")
    
    if total_passed == total_tests:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print(f"❌ {total_tests - total_passed} tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
