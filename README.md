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

This installs the `spl_validator` package and the **PyYAML** dependency used by `spl_validator.tools.validate_detections` (optional **`--strict`** treats unknown commands as errors). For **security_content**-style audits, prefer `tools/scan_external_detections.py`, which defaults to strict mode.

## Quickstart

```bash
python3 -m spl_validator --spl="index=web | stats count BY host | sort -count"
python3 -m spl_validator --strict --spl="| makeresults | `my_macro(arg)` | stats count"
python3 -m spl_validator --file=query.spl --format=json
# Paste-friendly (no inline shell quoting for multiline):
python3 -m spl_validator < query.spl
cat query.spl | python3 -m spl_validator --format=json
python3 -m spl_validator 'index=web | stats count BY host'
```

Optional defaults file: `.spl-validator.yaml` or `SPL_VALIDATOR_CONFIG` (see `spl_validator/examples/defaults.example.yaml`). Optional **registry packs** (YAML) extend commands: `--registry-pack PATH` (repeatable).

### `prod` branch integrations

On branch **`prod`**, the same validator also ships:

- **HTTP**: `python3 -m spl_validator.httpd` then `POST /validate` with JSON `{"spl":"..."}` (CORS enabled for local tooling).
- **TUI**: `pip install -e ".[tui]"` then `python3 -m spl_validator.tui` or `spl-validator-tui`.
- **Browser**: build `browser_extension/dist` (`npm run build` in `browser_extension/`) and load that folder as unpacked; it talks to the local HTTP server.
- **Contract**: JSON Schema for default API output in `docs/contract/cli-json-output.schema.json` (for ports / CI).

Full roadmap: [`PLAN.md`](PLAN.md).

## Features

- Grammar validation: pipeline structure, balanced parentheses/quotes
- Semantic checks: common command ordering/contexts, expression/function usage
- Limit warnings: common SPL defaults (modeled after `limits.conf`)
- Macros: backtick macros are treated as opaque tokens (not expanded)
- `map`: the `search="..."` argument is blanked before lexing (with **SPL054**); inner SPL is not validated, matching Splunk’s separate subsearch execution
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

## Interfaces (CLI, HTTP API, TUI, browser extension)

- **CLI** (stdin, positional SPL, presets): `python3 -m spl_validator --help`
  - Pipe SPL: `echo 'index=web | stats count' | python3 -m spl_validator --format=json` (or `--stdin`)
  - Positional: `python3 -m spl_validator --format=json 'index=web | stats count'`
  - Presets: `--preset=strict` or `--preset=security_content` (strict + `--advice=all`)
- **JSON contract**: machine output includes `output_schema_version` and `package_version` (see `spl_validator/contract.py`).
- **HTTP API** (for integrations and the extension): `spl-validator-httpd --host 127.0.0.1 --port 8765` then `POST /validate` with JSON `{"spl":"...","strict":false,"advice":"optimization"}`; `GET /health`.
- **TUI** (multiline editor, optional): `pip install -e ".[tui]"` then `spl-validator-tui` or `python3 -m spl_validator.tui_app`.
- **Browser extension** (Chromium): build `browser_extension/dist` with `cd browser_extension && npm install && npm run build`, then **Load unpacked** → pick **`browser_extension/dist`**. Run `spl-validator-httpd` and set the API URL in extension options (defaults to `http://127.0.0.1:8765`). Automated checks: `npm test` (esbuild bundle + Node mocks) and `xvfb-run -a npm run test:e2e` (Playwright loads the real extension against the Python httpd), or run `./tools/run_browser_extension_e2e.sh` from the repo root.

## Development

### TypeScript as the main entry point

The project is currently **focused on TypeScript** for day-to-day development and for **automated environment setup**. When bringing up a workspace, treat the **`typescript/`** tree as the primary surface: install dependencies, build **`@spl-validator/core`**, and run its tests. For that setup path, **only the TypeScript components need to succeed** for the environment to be considered healthy.

If that setup fails, assume the issue is in the **TypeScript code, configuration, or npm dependencies** and resolve it there unless you have explicitly chosen a Python-only workflow and the failure is clearly unrelated to `typescript/`.

**Automatic or agent-driven bug fixes are permitted** while getting `npm install`, `npm run build`, and `npm test` (within the TypeScript workspace) to pass.

The Python package remains the **canonical source** for command/function registry data (see `typescript/scripts/export_registry.py` to regenerate `typescript/core/src/generated/registryData.*` after registry edits). It still powers the original CLI, HTTP API, TUI, and the **`browser_extension/`** UI that talks to the local server.

**TypeScript quickstart** (standalone CLI and extension, no local HTTP server for the MV3 bundle under `typescript/extension/`):

```bash
cd typescript && npm install
npm run build
npm run test -w @spl-validator/core
npm run build -w @spl-validator/extension   # then load typescript/extension/dist unpacked
node runtime/dist/cli.js --format=json --spl 'index=_internal | head 5'   # run from typescript/
```

**Full-stack environment setup** (Python + legacy extension + e2e): from the repository root run `./tools/setup_environment.sh`. It creates `.venv/`, installs `spl-validator` in editable mode with **`[dev,tui]`** extras, runs `npm ci` under `browser_extension/`, and installs Playwright’s Chromium build for extension e2e tests. Activate the venv with `source .venv/bin/activate`.

Run tests from the repository root (after `pip install -e .`, or with `PYTHONPATH` set to the repo root):

```bash
pip install -e ".[dev]"   # pytest + jsonschema (contract tests)
pip install -e ".[tui]"   # optional: Textual TUI
python3 tests/test_basic.py
python3 tests/test_golden.py
python3 tests/test_parser.py
python3 -m pytest tests/test_functions_registry.py  # every SPL function: syntax, category, arity, command mapping
python3 -m pytest tests/  # includes registry pack, CLI I/O, JSON schema contract
pytest tests/test_interfaces.py  # CLI contract + HTTP API smoke tests
```

## Reference

- Supported commands: `spl_validator/src/registry/commands.py`
- Supported functions: `spl_validator/src/registry/functions.py`

## External corpus (splunk/security_content)

To batch-validate detection YAML from [splunk/security_content](https://github.com/splunk/security_content):

```bash
python3 tools/scan_external_detections.py --root /path/to/security_content/detections
```

By default the scanner uses **`strict=True`**: unknown SPL **commands** (SPL013) and unknown **functions** (SPL023) make a search invalid, so registry coverage affects the score. Use **`--loose`** if you only want parse/syntax errors without treating unknown commands as fatal.

Findings from a sample scan are documented in [`docs/security_content_validation.md`](docs/security_content_validation.md). Optional pytest: set `SECURITY_CONTENT_ROOT` and run `tests/test_security_content_scan.py` (also uses strict mode).

For complexity / throughput characteristics, see [`docs/scalability.md`](docs/scalability.md). For a line-by-line review of strict-mode invalid ESCU-style searches, see [`docs/security_content_23_invalid_analysis.md`](docs/security_content_23_invalid_analysis.md).
