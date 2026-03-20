# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- SPL function registry metadata: categories, syntax strings, eval/stats command hints (`spl_validator/src/registry/functions.py`).
- **SPL023**: unknown function name (eval/where and stats aggregations). Arity issues remain **SPL020**; wrong eval/stats context remains **SPL021**.
- `tools/scan_external_detections.py`: batch-validate YAML `search` fields (e.g. `splunk/security_content`), **`strict=True` by default**; **`--loose`** for legacy behavior.
- Optional pytest `tests/test_security_content_scan.py` when `SECURITY_CONTENT_ROOT` is set.
- `docs/security_content_validation.md`: corpus scan notes.

### Changed

- **`validate_function_arity`**: no longer returns errors for unknown function names (handled as **SPL023** at call sites).
- **`spl_validator.tools.validate_detections`**: defaults to **`strict=False`** again for API/CLI backward compatibility; use **`--strict`** for unknown-command-as-error behavior (same as the external security_content scanner’s default).

### Compatibility notes

- Integrations that treated **SPL020** as “unknown function” must switch to **SPL023** (message still contains `Unknown function`).
- `validate(..., strict=False)` remains the **default** for `spl_validator.core.validate` (unchanged).
