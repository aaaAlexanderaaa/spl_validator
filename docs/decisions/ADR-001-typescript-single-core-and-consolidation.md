---
id: ADR-001
kind: decision
status: current
title: "Move to a pure TypeScript single core, deepen SPL analysis with macro expansion and field lineage, keep project context lightweight, and consolidate spl-expert into spl_validator"
sources:
  - SRC-001
affects: []
supersedes: []
---

# ADR-001: TypeScript Single Core, Core Engine Upgrades, Lightweight Context & Repository Consolidation

## Context & Problem

As of 2026-11-24, `spl_validator` maintained two parallel validator implementations (`spl_validator/` in Python and `typescript/` in TypeScript), two Chromium extensions (an HTTP-backed legacy extension under `browser_extension/` and a standalone TypeScript extension under `typescript/extension/`), and a separate `spl-expert` repository containing official Splunk `.conf` snapshots, extraction scripts, SPL knowledge notes, and a vendored duplicate of `spl_validator/`.

This layout caused four concrete problems:

1. **Integration and maintenance friction**: External Splunk detection repositories—for example, a Python-managed rule repository using a Git edit-commit-PR workflow—need a self-contained CLI hook that validates an SPL query on save or in CI without coupling into a second Python validator runtime, while browser users need zero-server usability.
2. **Shallow macro and field semantics**: Backtick macros were skipped as opaque allowlist tokens rather than expanded into real SPL before validation, and field analysis could not trace which upstream fields or expressions produced each output field or propose automated fixes.
3. **Unclear environment-context scope**: Treating workspace/environment awareness as a standalone platform risked over-engineering what only needs to be a small configuration payload.
4. **Split repository ownership**: Keeping official Splunk reference `.conf` snapshots and SPL reference assets in `spl-expert` alongside a vendored copy of `spl_validator` created drift between validation rules and reference data.

## Chosen Approach (Four Settled Decisions)

### 1. Pure TypeScript Single Core & Delivery Surfaces (Option C)

- `@spl-validator/core` in TypeScript becomes the **sole target validation core** with zero Node.js or browser DOM dependencies.
- Three thin delivery surfaces sit on top of `@spl-validator/core`:
  1. **Node.js CLI & Hook Runner (`@spl-validator/runtime`)**: Validates single queries, stdin/files, save-time editor/tool hooks inside external rule repositories (including Python-managed Git repos), and batch PR validation runs.
  2. **Standalone MV3 Browser Extension (`@spl-validator/extension`)**: Bundles `@spl-validator/core` directly in-browser with zero local HTTP server and minimal permissions.
  3. **Static HTML Web UI**: Provides an accessible, zero-server browser interface for pasting queries and inspecting diagnostics, expanded macros, field lineage, and rewrite suggestions. Maintaining the Python Textual TUI (`spl_validator/tui_app.py`) is deprioritized.
- **Migration rule**: Until TypeScript reaches full parity against the existing 307-test Python suite and the 98.85% strict-mode `splunk/security_content` baseline (1,983 / 2,006 valid on the 2026-03-20 snapshot), the Python package (`spl_validator/`) remains in the repository as a **frozen regression reference**. New validation rules, macro expansion, field lineage, and AutoFix work go into TypeScript only.

### 2. Core Engine Capability Upgrades

- **Real Macro Expansion**: Expand backtick macros (including nested and parameterized macros) from caller-supplied `macros.conf` definitions into actual SPL before lexing and parsing, preserving source-span mappings back to the author's original query. Macros are no longer treated as an opaque bypass.
- **Deeper Parsing & Pragmatic Registry Reconciliation**: Strengthen command, argument, subsearch, and expression parsing, and reconcile built-in command/function/limit metadata against **obtainable** authoritative artifacts—specifically Splunk Enterprise 10.0 `searchbnf.conf`, `limits.conf`, and the public `splunk/security_content` detection corpus—rather than assuming access to unavailable proprietary internals.
- **Field Lineage & Origin Tracking**: Track field creation, transformation, renaming, aggregation, lookup enrichment, and pruning across pipeline stages so the validator detects missing/dropped field errors and explains which upstream fields or expressions produce every output field.
- **AutoFix & Optimization Rewriter**: Produce structured, deterministic rewrite suggestions and safe auto-fixes (syntax repair, redundant command simplification, performance improvements, and field-error fixes) anchored to exact source spans.

### 3. Lightweight `ProjectContext` Wrapper

- Environment awareness stays a **small, plain, serializable `ProjectContext` input object** passed into `@spl-validator/core`, containing optional macro definitions (`macros.conf`), optional lookup CSV header schemas, optional custom command/registry pack definitions, and optional known field schemas.
- File discovery and parsing of `.conf`/YAML/CSV inputs belong in thin adapters inside `@spl-validator/runtime` or host integrations, avoiding any persistent daemon, background indexer, or heavyweight context framework.

### 4. `spl_validator` as the Single Main Repository (Absorbing `spl-expert`)

- `spl_validator` becomes the sole authoritative repository for SPL validation code, reconciled Splunk reference data, and core documentation.
- **Consolidation boundary for `spl-expert` assets**:
  - **Absorb into `spl_validator`**: Obtainable official Splunk configuration snapshots (`official_conf/searchbnf.conf`, `official_conf/limits.conf`), extraction utilities (`extract_command_syntax.py`, `extract_stanza.py`) used for offline registry reconciliation, and verified SPL syntax/performance/troubleshooting reference material that directly supports diagnostic rules and rewrite guidance.
  - **Remove duplication**: Retire the vendored duplicate copy of `spl_validator/` inside `spl-expert`.
  - **Keep agent skill packaging thin**: Any AI coding skill (`SKILL.md` and wrapper scripts) consumes the single `spl_validator` CLI/core rather than shipping a forked validator.
  - **Keep out of `@spl-validator/core`**: Dashboard Studio JSON authoring guides (`kb/dashboard-studio/` and `visualizations.conf`) stay separate from SPL validation logic and may be retained only as optional reference documentation if still needed.

## Trade-Offs & Rejected Alternatives

- **Keeping Python as the permanent canonical registry and continuing to export generated TypeScript data**: Rejected because dual-language authoring doubles effort on every command, macro, lineage, and AutoFix change and complicates embedding in browser and JavaScript/hook environments.
- **Maintaining a full-featured Python Textual TUI alongside the HTML UI and MV3 extension**: Rejected because visual inspection and everyday ease of use are served with lower maintenance cost by a static HTML Web UI and standalone MV3 extension sharing the same TypeScript core.
- **Building a live Splunk-connected or workspace-indexing context service**: Rejected because the actual need is a portable, offline `ProjectContext` payload that an external repo hook or browser user can pass in directly.
- **Maintaining `spl_validator` and `spl-expert` as two peer main repositories**: Rejected because splitting official `.conf` snapshots from the validator that reconciles against them guarantees version drift and duplicate maintenance.
