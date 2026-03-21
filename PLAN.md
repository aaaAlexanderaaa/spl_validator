# SPL Validator — `prod` branch roadmap

This branch is a **standalone integration line** (not intended to merge into `master`) that rolls up UX, distribution, architecture, and portability work in dependency order.

## Phase 1 — Contract and tests

- [x] Machine-readable **JSON Schema** for default CLI/API JSON payloads (`docs/contract/cli-json-output.schema.json`).
- [x] Tests that assert sample outputs conform to the schema (`tests/test_contract.py`, optional `jsonschema` in dev extras).
- [x] Golden JSON fixtures remain the primary cross-language black-box corpus; extend over time.

## Phase 2 — Kernel and configuration

- [x] **Registry packs**: optional YAML files that register **additional** commands (and aliases) without editing Python (`--registry-pack`, `spl_validator/registry_packs/`).
- [ ] Full extraction of built-in `COMMANDS` / `FUNCTIONS` to packs (future; large migration).

## Phase 3 — CLI ergonomics

- [x] **Stdin** input when no `--spl`, `--file`, or positional query (non-TTY pipe/heredoc).
- [x] Optional **positional** SPL argument.
- [x] Optional **defaults file** `.spl-validator.yaml` or path via `--config` / `SPL_VALIDATOR_CONFIG`.

## Phase 4 — TUI

- [x] Optional **Textual** UI: `python -m spl_validator.tui` or `pip install '.[tui]'` and `spl-validator-tui`.

## Phase 5 — HTTP bridge

- [x] **Stdlib HTTP** server: `python -m spl_validator.httpd` — `POST /validate` with JSON body, same JSON shape as CLI (CORS enabled for local extension use).

## Phase 6 — Browser extension

- [x] Minimal MV3 **popup** under `browser_extension/` targeting the local HTTP server (load unpacked in Chrome/Edge).

## Phase 7 — Second implementation (WASM / other language)

- [ ] Not started on this branch; use golden JSON + schema + registry pack YAML as the portability contract when you begin.

## Maintenance

- Keep `master` free of experimental packaging and extension assets if desired; develop integrations on **`prod`** and cherry-pick validator-core fixes back to `master` as needed.
