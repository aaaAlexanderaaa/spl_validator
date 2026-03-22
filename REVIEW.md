# SPL Validator — Project Review

## Executive Summary

SPL Validator is a well-architected static analysis tool for Splunk Processing Language (SPL) queries. It ships a Python package (CLI + HTTP API + optional TUI), a legacy Chromium extension, and a TypeScript implementation (core library, CLI, and standalone MV3 extension). The codebase is healthy: **188 Python tests and 4 TypeScript golden test suites all pass**, builds succeed across both languages, and the dual-implementation approach with shared golden tests is a strong foundation for cross-language parity.

**Overall assessment: solid engineering with clear architecture.** The findings below are improvement opportunities, not blockers.

---

## Architecture Overview

```
                    ┌─────────────────────────┐
                    │    Golden Test Corpus    │
                    │  (tests/golden/*.json)   │
                    └────────┬────────────────┘
                             │ shared
               ┌─────────────┴────────────────┐
               ▼                               ▼
   ┌───────────────────┐          ┌────────────────────────┐
   │  Python Package   │          │  TypeScript Workspace   │
   │  spl_validator/   │          │  typescript/            │
   │                   │          │                         │
   │  ├── core.py      │  export  │  ├── core/  (@spl-validator/core) │
   │  ├── src/         │ ───────► │  │   ├── src/generated/ │
   │  │   ├── lexer/   │ registry │  │   └── src/validate.ts│
   │  │   ├── parser/  │          │  ├── runtime/ (CLI)     │
   │  │   ├── analyzer/│          │  └── extension/ (MV3)   │
   │  │   ├── registry/│          │                         │
   │  │   └── models/  │          └────────────────────────┘
   │  ├── httpd.py     │
   │  ├── validator.py │
   │  └── tui.py       │
   └───────────────────┘
               │
    ┌──────────┴─────────┐
    ▼                    ▼
 Legacy Extension    HTTP API
 (browser_extension/) (httpd.py)
```

### Strengths of the Architecture

1. **Shared golden tests** — Both Python and TypeScript validate against the same JSON fixtures, providing a strong cross-language parity contract.
2. **Registry export pipeline** — Python is the canonical command/function registry; `export_registry.py` generates TypeScript data, avoiding duplication.
3. **Clean validation pipeline** — Lex → Parse → Analyze (sequence, commands, functions, limits, semantics, suggestions, fields) with each concern in its own module.
4. **Minimal dependencies** — Python uses only PyYAML (+ optional textual for TUI); TypeScript has zero runtime dependencies. The HTTP server is stdlib-only.
5. **Contract versioning** — JSON Schema (`docs/contract/cli-json-output.schema.json`) and `OUTPUT_JSON_SCHEMA_VERSION` ensure API stability.

---

## Findings

### 1. Code Quality

#### 1.1 `core.py` is a 1,726-line monolith

The Python `core.py` contains the parser (`parse_simple`), all command-specific parsing (eval, where, bin, stats, top/rare, search), and multiple validators (`validate_commands`, `validate_limits`, `validate_functions`, `validate_semantics`, `validate_search_terms`). The TypeScript side has already decomposed this into ~15 separate modules.

**Impact**: Harder to navigate, test in isolation, and modify without risk of side effects.

**Recommendation**: Extract `parse_simple` and command-specific parsing into `spl_validator/src/parser/`, and move validators into `spl_validator/src/analyzer/` (mirroring the TypeScript structure). This would reduce `core.py` to ~50 lines of pipeline orchestration.

#### 1.2 Duplicate code between implicit-search branches

In `parse_simple`, three near-identical code paths handle the initial command depending on whether the first token is a known generating command, a known non-generating command, or an implicit search. Each repeats the subsearch extraction, `CommandParser` invocation, and `_scan_search_kv_options` pattern.

**Recommendation**: Extract a helper like `_parse_command_body(cmd_tokens, cmd_name, result) -> (options, clauses, args, subsearch)` to eliminate the duplication.

#### 1.3 `setattr(result, "_lex_spl", spl_for_lexing)` in Python

This stores the preprocessed SPL string on the result object using `setattr` for a private attribute, which is later retrieved via `getattr(result, "_lex_spl", result.spl)` in `validate_search_terms`. The TypeScript side models this properly as `_lexSpl?: string` on the interface.

**Recommendation**: Add `_lex_spl: Optional[str] = None` to the `ValidationResult` dataclass to make this explicit.

#### 1.4 `ast: Optional[Any]` / `ast: unknown`

Both implementations type the AST field loosely (`Any` in Python, `unknown` in TypeScript). Callers cast it (e.g., `result.ast as Pipeline` in TS).

**Recommendation**: Type as `Optional[Pipeline]` / `Pipeline | null` for better safety and IDE support.

#### 1.5 Test functions return values (Python)

`tests/test_parser.py` functions return `(passed, total)` tuples, triggering `PytestReturnNotNoneWarning`:

```
PytestReturnNotNoneWarning: Test functions should return None
```

These tests use a manual pass/fail counter instead of pytest assertions, which means individual sub-cases don't appear in pytest output and failures don't produce standard pytest diffs.

**Recommendation**: Refactor to use `@pytest.mark.parametrize` for individual test cases with standard `assert` statements.

#### 1.6 Late imports inside functions (Python)

Several functions in `core.py` use late imports (`from .src.parser.ast import Argument`, `from .src.analyzer.fields import track_fields`), sometimes repeatedly inside loops or branches. While this avoids circular imports, it adds overhead and obscures dependencies.

**Recommendation**: Consolidate imports at the module level where possible, or at least at the function level (not inside loops).

### 2. Testing

#### 2.1 Strong golden test coverage

The golden test framework is excellent — 4 fixture files with test cases covering errors, parser behavior, security content patterns, and correlation searches. Both Python and TypeScript run the same corpus.

#### 2.2 TypeScript tests are golden-only

The TypeScript `@spl-validator/core` package has no unit tests for individual components (lexer, parser, validators). All testing runs through the golden integration tests.

**Impact**: When a golden test fails, it's harder to pinpoint which component broke. Edge cases in individual modules (e.g., lexer handling of unusual characters, expression parser precedence) aren't tested in isolation.

**Recommendation**: Add targeted unit tests for the TypeScript lexer, parser, and individual validators — similar to the Python `test_parser.py` and `test_functions_registry.py`.

#### 2.3 No Python workflow in CI

The `.github/workflows/` directory only contains `browser-extension.yml`. Python tests (`pytest tests/`) and TypeScript tests (`npm test`) aren't run in CI.

**Impact**: Regressions in the core validator (Python or TypeScript) won't be caught automatically on push/PR.

**Recommendation**: Add a CI workflow that runs `pytest tests/` and `npm test -w core` (plus build) on push and PR.

#### 2.4 E2E coverage is minimal

The browser extension E2E has a single happy-path test (valid SPL, server is up). No tests for invalid SPL, server errors, or options persistence.

**Recommendation**: Add at least one invalid-SPL E2E case and one server-down case for more robust coverage.

### 3. Security

#### 3.1 HTTP server CORS policy

The CORS implementation reflects the `Origin` header back as-is when present:

```python
if origin:
    return {"Access-Control-Allow-Origin": origin, ...}
return {"Access-Control-Allow-Origin": "*", ...}
```

This is effectively `Access-Control-Allow-Origin: *` for all requests, which is fine for a local development tool. If the server is ever exposed on a network, this should be tightened.

#### 3.2 Body size limit is enforced

The HTTP server enforces a 2MB body limit (`max_body`), preventing trivial DoS via large payloads.

#### 3.3 No input sanitization concerns

The validator processes SPL strings but never evaluates or executes them. Output is JSON-serialized. There are no injection vectors.

### 4. Dependencies and Packaging

#### 4.1 esbuild vulnerability (moderate)

```
esbuild <=0.24.2 - moderate severity
Enables any website to send requests to the development server
```

This only affects the build tool (not runtime) and is relevant only during development. Still, upgrading to esbuild >=0.25.0 would resolve it.

#### 4.2 Python packaging is clean

`pyproject.toml` with proper extras (`[dev]`, `[tui]`), console scripts, and Python >=3.10 requirement. No stale `setup.py` or `requirements.txt`.

#### 4.3 TypeScript workspace structure is sound

npm workspaces with proper dependency ordering (core → runtime → extension). The build chain is deterministic: `tsc` for core/runtime, esbuild for extension.

### 5. Documentation

#### 5.1 Documentation is thorough

`README.md` covers installation, quickstart, features, development, and contract details. `AGENTS.md` provides clear instructions for automated tooling. `PLAN.md` tracks roadmap progress. `CHANGELOG.md` exists.

#### 5.2 Missing inline architecture docs

The codebase lacks a high-level architecture document or module-level docstrings that explain how the validation pipeline flows (lex → parse → analyze) and how Python and TypeScript relate. The `PLAN.md` tracks phases but doesn't describe the current architecture.

**Recommendation**: Add a brief `docs/architecture.md` with a pipeline diagram and module responsibilities.

### 6. Project Hygiene

#### 6.1 Orphaned legacy files in `browser_extension/`

`browser_extension/popup.js`, `popup.html`, `popup.css`, and `manifest.json` at the root level are legacy files not used by the build (which reads from `src/`). They can confuse contributors.

**Recommendation**: Remove or move to an `archive/` directory.

#### 6.2 No linter configured for either language

Neither Python nor TypeScript has a linter (ruff/flake8/mypy for Python; ESLint/Prettier for TypeScript). Code style is enforced only by convention.

**Recommendation**: At minimum, add `ruff` for Python and enable TypeScript strict mode (already enabled) with a basic ESLint config. This catches issues like unused imports, type narrowing gaps, and style inconsistencies.

#### 6.3 No `.editorconfig`

No `.editorconfig` exists to standardize indentation, line endings, and trailing whitespace across editors.

#### 6.4 PLAN.md references a `prod` branch

`PLAN.md` describes itself as a roadmap for a `prod` branch ("not intended to merge into `master`"), but the current branch is `cursor/overall-project-review-67f2` off `master`. This may be outdated context.

---

## Metrics

| Metric | Value |
|--------|-------|
| Python source LOC | ~5,600 |
| TypeScript source LOC | ~7,600 |
| Python test files | 10 |
| Python test cases | 188 passed, 2 skipped |
| TypeScript golden suites | 4 (all pass) |
| Golden test fixture lines | 517 |
| Registered SPL commands | ~100 |
| Registered SPL functions | ~80 |
| CI workflows | 1 (browser extension only) |
| npm vulnerabilities | 1 moderate (esbuild, build-time only) |
| Python dependencies | 1 runtime (PyYAML), 2 dev (pytest, jsonschema), 1 optional (textual) |
| TypeScript runtime deps | 0 |

---

## Priority Recommendations

### High Priority (correctness / CI)

1. **Add CI workflows for Python and TypeScript tests** — Currently only the browser extension has CI. Core validator regressions go undetected.
2. **Fix pytest return warnings** — `test_parser.py` functions return values, causing `PytestReturnNotNoneWarning`. Refactor to use `@pytest.mark.parametrize`.

### Medium Priority (maintainability)

3. **Extract `parse_simple` from `core.py`** — Move the 770-line parser into `spl_validator/src/parser/` and decompose command-specific parsing into helpers, mirroring the TypeScript structure.
4. **Add `_lex_spl` field to `ValidationResult` dataclass** — Replace the `setattr`/`getattr` pattern with an explicit optional field.
5. **Type `ast` as `Pipeline | None`** — In both Python and TypeScript, replace `Any`/`unknown` with the concrete type.
6. **Add TypeScript unit tests** — Cover the lexer, expression parser, and individual validators beyond golden integration tests.

### Low Priority (polish)

7. **Remove orphaned browser extension files** — Clean up `browser_extension/popup.js`, `popup.html`, `popup.css`, `manifest.json` at root.
8. **Upgrade esbuild** — Resolve the moderate npm advisory.
9. **Add basic linter configs** — `ruff` for Python, ESLint for TypeScript.
10. **Add `.editorconfig`** — Standardize formatting across editors.
11. **Add `docs/architecture.md`** — Document the validation pipeline and cross-language relationship.
