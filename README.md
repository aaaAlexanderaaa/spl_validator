# SPL Validator

A lightweight, **offline** static analysis tool for **Splunk Enterprise 10.0** SPL queries. It parses a query and reports:
1. **Validity** — syntax and supported semantics
2. **Warnings** — best practices, limits, optimization opportunities
3. **Suggestions** — quick-fix hints attached to each finding

**Privacy:** Fully local. No telemetry, no network calls, no data collection. See [`docs/security_audit.md`](docs/security_audit.md).

## Architecture & Active Direction

Under [`ADR-001`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md), `spl_validator` is consolidating onto a **single pure-TypeScript core** (`typescript/`, zero Node/DOM dependencies) that powers:
- A **Node.js >= 22 LTS** CLI (`@spl-validator/runtime`) packaged during development as a single-file dual-mode `spl-validator.cjs` bundle (one-shot CLI for Git pre-commit/CI, save hooks, `macros.conf` reverse-impact revalidation, and `batch` repo scans outputting JSON/Markdown/SARIF; lazy stdio NDJSON worker + thin Python stdlib wrapper for long-lived Python services), with standalone native binary packaging (e.g., Node SEA) planned as a later distribution milestone (`M-06`);
- A zero-server **Single-Query Deep Workbench** static HTML Web UI (diagnostics + AutoFix diff preview, side-by-side macro expansion highlight, interactive field lineage graph, local `macros.conf`/CSV header upload);
- A standalone MV3 Chromium extension (`typescript/extension/`) requiring no local server and reusing the same workbench UI directly.

Core upgrades underway add real `macros.conf` expansion (replacing opaque macro skipping), Splunk 10.0 `searchbnf.conf` / `limits.conf` registry reconciliation, pipeline field-lineage tracking, and AutoFix/optimization rewrites. Through Phase 0–2, the Python package (`spl_validator/`) remains in-repo as the **frozen, read-only regression reference** (307 tests; 98.85% strict-mode pass rate on `splunk/security_content`) and will be archived/removed after Phase 3 parity acceptance passes.

- System architecture & pipeline: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Settled strategic decisions: [`docs/decisions/ADR-001-typescript-single-core-and-consolidation.md`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md)
- Active roadmap & tasks: [`docs/work.toml`](docs/work.toml) and [`PLAN.md`](PLAN.md)
- TypeScript workspace guide: [`docs/typescript_development.md`](docs/typescript_development.md)

## Installation (Current Python Baseline)

```bash
pip install -e .          # core (CLI + HTTP API)
pip install -e ".[tui]"   # optional: Textual TUI
pip install -e ".[dev]"   # optional: pytest + jsonschema for development
```

Requires **Python ≥ 3.10**.

## Quickstart

```bash
# Simple queries
python3 -m spl_validator --spl="index=web | stats count BY host | sort -count"
python3 -m spl_validator 'index=web | stats count BY host'

# Complex multiline queries — no shell quoting needed
python3 -m spl_validator --clipboard               # validate from system clipboard
python3 -m spl_validator --file=query.spl           # read from file
python3 -m spl_validator --edit                     # open $EDITOR, validate on save
python3 -m spl_validator < query.spl                # pipe/redirect

# Web UI — paste and validate in the browser (recommended for complex queries)
spl-validator-httpd --open                          # opens http://localhost:8765
```

Optional defaults file: `.spl-validator.yaml` or `SPL_VALIDATOR_CONFIG` (see `spl_validator/examples/defaults.example.yaml`). Optional **registry packs** (YAML) extend commands: `--registry-pack PATH` (repeatable).

## Features

- Grammar validation: pipeline structure, balanced parentheses/quotes
- Semantic checks: command ordering, expression/function usage
- Limit warnings: common SPL defaults (modeled after `limits.conf`)
- Best-practice suggestions: consecutive evals, wildcard usage, join alternatives
- Warning consolidation: repeated findings are grouped into actionable summaries
- Macros: currently treated as opaque backtick tokens in the baseline; real expansion via `macros.conf` with source-span mapping is tracked under [`ADR-001`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md)
- `map`: inner `search="..."` strings blanked before lexing (SPL054)
- Debugging: AST dump + data-flow field tracking

## Interfaces

### Web UI (recommended for complex queries)

```bash
spl-validator-httpd --open
```

Opens `http://localhost:8765` in the browser. Paste SPL directly, press **Ctrl+Enter** to validate. Toggle **Strict** / **Advice** settings live. Features auto-validate on paste, collapsible JSON output, and a Copy button. No external dependencies loaded.

### CLI

```bash
python3 -m spl_validator --help

# Input methods (use exactly one):
python3 -m spl_validator --spl="index=web | stats count BY host"    # inline
python3 -m spl_validator --clipboard                                 # system clipboard
python3 -m spl_validator --file=query.spl                           # file
python3 -m spl_validator --edit                                     # open $EDITOR
python3 -m spl_validator < query.spl                                # stdin/pipe
echo '...' | python3 -m spl_validator --stdin --format=json         # explicit stdin

# Options:
--format=json          # machine-readable JSON output
--strict               # unknown commands become errors
--advice=all           # show all warning groups (default: optimization)
--preset=security_content   # strict + all advice
--schema=schema.json   # field availability checking
```

### TUI (interactive terminal)

```bash
pip install -e ".[tui]"
spl-validator-tui                     # interactive editor
spl-validator-tui --file=query.spl    # pre-load from file
```

Keyboard shortcuts: **F5** validate, **Ctrl+L** clear, **Ctrl+O** open file, **Ctrl+S** save JSON results. Tabbed output (Summary + JSON), interactive Strict / Advice controls.

### HTTP API

```bash
spl-validator-httpd --host 127.0.0.1 --port 8765
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (HTML) |
| `/validate` | POST | Validate SPL — body: `{"spl":"...","strict":false,"advice":"optimization"}` |
| `/health` | GET | Health check — `{"ok":true,"service":"spl-validator"}` |

CORS is enabled for local tooling. See [`docs/security_audit.md`](docs/security_audit.md) for hardening guidance.

### Browser extension (Chromium)

The legacy extension (`browser_extension/`) calls the local HTTP API. Build and load:

```bash
cd browser_extension && npm install && npm run build
# Load unpacked → browser_extension/dist in chrome://extensions
```

A standalone TypeScript extension that validates entirely in-browser (no server needed) is available under `typescript/extension/`. See [`docs/typescript_development.md`](docs/typescript_development.md).

## CLI Notes

- Warning filtering: `--advice=optimization` (default), `--advice=all`, `--advice=none`, or comma-separated groups
- Schema-aware: `--schema schema.json` + `--schema-missing error|warning`
- Presets: `--preset=strict`, `--preset=security_content` (strict + all advice)
- JSON contract: output includes `output_schema_version` and `package_version` (see `spl_validator/contract.py`)
- Config file: `.spl-validator.yaml` or `$SPL_VALIDATOR_CONFIG`
- Registry packs: `--registry-pack PATH` (YAML, repeatable)

## Development

```bash
pip install -e ".[dev,tui]"
pytest tests/                          # 307 tests (2 skipped by design)
```

Individual test modules:
```bash
pytest tests/test_edge_cases.py        # parser edge cases
pytest tests/test_functions_registry.py # every SPL function
pytest tests/test_interfaces.py        # CLI I/O + HTTP API + web UI
pytest tests/test_contract.py          # JSON output schema
```

### Full-stack setup (Python + browser extension E2E)

```bash
./tools/setup_environment.sh
source .venv/bin/activate
pytest tests/
cd browser_extension && npm test && xvfb-run -a npm run test:e2e
```

### TypeScript workspace (target single core)

The TypeScript workspace under `typescript/` (`@spl-validator/core`, `@spl-validator/runtime`, and standalone `@spl-validator/extension`) is the active target core under [`ADR-001`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md). See [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`docs/typescript_development.md`](docs/typescript_development.md) for setup and usage.

## Reference

- Architecture & target pipeline: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Strategic decisions: [`docs/decisions/ADR-001-typescript-single-core-and-consolidation.md`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md)
- Legacy Python command registry (frozen reference): `spl_validator/src/registry/commands.py`
- Legacy Python function registry (frozen reference): `spl_validator/src/registry/functions.py`
- Security audit: [`docs/security_audit.md`](docs/security_audit.md)
- Scalability: [`docs/scalability.md`](docs/scalability.md)

## External corpus (splunk/security_content)

```bash
python3 tools/scan_external_detections.py --root /path/to/security_content/detections
```

By default the scanner uses `strict=True`. Use `--loose` for syntax errors only. See [`docs/security_content_validation.md`](docs/security_content_validation.md) for findings from a sample scan.
