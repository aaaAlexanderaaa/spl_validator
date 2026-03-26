# SPL Validator

A lightweight, **offline** static analysis tool for **Splunk Enterprise 10.0** SPL queries. It parses a query and reports:
1. **Validity** — syntax and supported semantics
2. **Warnings** — best practices, limits, optimization opportunities
3. **Suggestions** — quick-fix hints attached to each finding

**Privacy:** Fully local. No telemetry, no network calls, no data collection. See [`docs/security_audit.md`](docs/security_audit.md).

## Installation

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
- Macros: backtick macros treated as opaque tokens (not expanded)
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

### TypeScript port (experimental)

An experimental TypeScript implementation of the core validator is available in `typescript/`. See [`docs/typescript_development.md`](docs/typescript_development.md) for setup and usage.

## Reference

- Supported commands: `spl_validator/src/registry/commands.py`
- Supported functions: `spl_validator/src/registry/functions.py`
- Security audit: [`docs/security_audit.md`](docs/security_audit.md)
- Scalability: [`docs/scalability.md`](docs/scalability.md)

## External corpus (splunk/security_content)

```bash
python3 tools/scan_external_detections.py --root /path/to/security_content/detections
```

By default the scanner uses `strict=True`. Use `--loose` for syntax errors only. See [`docs/security_content_validation.md`](docs/security_content_validation.md) for findings from a sample scan.
