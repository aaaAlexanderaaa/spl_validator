# SPL Validator

A lightweight validator for **Splunk Enterprise 10.0** SPL. It parses a query and reports:
1. **Validity** (syntax + supported semantics)
2. **Warnings** (best practices + limits)
3. **Suggestions** (quick-fix hints attached to findings)

## Installation

From the repository root (editable install recommended):

```bash
pip install -e .
```

This installs the `spl_validator` package and the **PyYAML** dependency used by `spl_validator.tools.validate_detections`.

## Quickstart

```bash
python3 -m spl_validator --spl="index=web | stats count BY host | sort -count"
python3 -m spl_validator --strict --spl="| makeresults | `my_macro(arg)` | stats count"
python3 -m spl_validator --file=query.spl --format=json
```

## Features

- Grammar validation: pipeline structure, balanced parentheses/quotes
- Semantic checks: common command ordering/contexts, expression/function usage
- Limit warnings: common SPL defaults (modeled after `limits.conf`)
- Macros: backtick macros are treated as opaque tokens (not expanded)
- Debugging: AST + a lightweight “flow” sketch for fields/actions

## Contract (Splunk Enterprise 10.0)

- For covered constructs (notably `eval` / `where` expressions), **valid** means the construct parses successfully and consumes all tokens; **invalid** means any parse error or trailing tokens.
- Unknown commands are warnings by default (`--strict` upgrades them to errors). Unknown commands/macros are treated as opaque for their internal argument grammar, but surrounding pipeline structure and known expression syntax are still validated.

## CLI Notes

- Warning filtering is group-based via `--advice`:
  - Default: `--advice=optimization` (shows limits + optimization only)
  - Everything: `--advice=all`
  - Nothing: `--advice=none`
  - Or: `--advice=limits,optimization,semantic,schema,diagnostic,style,other`
- Schema-aware field checking (optional):
  - `--schema schema.json` enables field availability checks
  - `--schema-missing error|warning` controls severity when fields are known

## Development

Run tests from the repository root (after `pip install -e .`, or with `PYTHONPATH` set to the repo root):

```bash
pip install -e ".[dev]"   # optional: pytest
python3 tests/test_basic.py
python3 tests/test_golden.py
python3 tests/test_parser.py
pytest tests/             # if using pytest discovery (optional)
```

## Reference

- Supported commands: `spl_validator/src/registry/commands.py`
- Supported functions: `spl_validator/src/registry/functions.py`
