---
id: ADR-001
kind: decision
status: current
title: "Move to a pure TypeScript single core, deepen SPL analysis with macro expansion and field lineage, keep project context lightweight, and consolidate spl-expert into spl_validator"
sources:
  - SRC-001
  - SRC-002
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
  1. **Node.js >= 22 LTS CLI & Hook Runner (`@spl-validator/runtime`)**: Ships during development as a single-file dual-mode `spl-validator.cjs` bundle (one-shot CLI for Git pre-commit/CI, low-frequency saves, `macros.conf` reverse-impact checks, and `batch` repository inspection outputting JSON/Markdown/SARIF; lazy stdio NDJSON worker paired with a thin Python standard-library wrapper for long-lived Python services). Standalone native binary packaging (for example, Node SEA) is scheduled as a later distribution milestone (`M-06`).
  2. **Standalone MV3 Browser Extension (`@spl-validator/extension`)**: Bundles `@spl-validator/core` directly in-browser with zero local HTTP server and minimal permissions, sharing the Single-Query Deep Workbench UI directly with the static HTML Web UI.
  3. **Static HTML Web UI**: Provides an accessible, zero-server **Single-Query Deep Workbench** (diagnostics + AutoFix diff preview, side-by-side macro expansion highlight, interactive field lineage graph, and local `macros.conf`/CSV header upload). Maintaining the Python Textual TUI (`spl_validator/tui_app.py`) is deprioritized.
- **Migration rule**: Through **Phase 0–2**, the Python package (`spl_validator/`) remains in the repository as a **frozen, read-only regression reference**; it is archived and removed from the main source tree only after **Phase 3 parity acceptance** passes (covering the 307-test Python suite, the >= 98.85% strict-mode `splunk/security_content` baseline of 1,983 / 2,006 detections on the 2026-03-20 snapshot, and the new macro-expansion and field-lineage suites). New validation rules, macro expansion, field lineage, and AutoFix work go into TypeScript only.

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

## Settled Implementation Contracts (2026-11-24, `SRC-002`)

Three follow-up delivery and lifecycle contracts lock down runtime packaging, legacy retirement timing, and browser UI v1 boundaries:

1. **Runtime Target, Dual-Mode Hook Packaging & Deferred Binary Distribution (`A4`)**:
   - **Target runtime**: CLI and hook execution targets **Node.js >= 22 LTS** (replacing legacy Node 18).
   - **Development packaging**: `@spl-validator/runtime` bundles into a single-file **`spl-validator.cjs`** supporting two execution modes:
     - **One-shot CLI mode**: Used by Git pre-commit hooks, CI pipelines, low-frequency rule saves, `macros.conf` change reverse-impact revalidation, and `batch` repository inspection (`JSON`, `Markdown`, and `SARIF` outputs).
     - **Lazy stdio NDJSON worker mode**: Spawned on demand by long-lived Python rule-management services for low-latency repeated checks, paired with a **thin Python standard-library wrapper** (zero third-party Python dependencies).
   - **Later distribution milestone**: **Standalone native binary packaging (for example, Node SEA)** is explicitly scheduled as a later distribution milestone (`M-06` in [`docs/work.toml`](../work.toml)) so binary packaging never blocks core validation, macro, lineage, or workbench development.

2. **Frozen Python Legacy Core Retirement Schedule (`A5`)**:
   - **Phase 0–2 (`M-01` through `M-03` / pre-acceptance)**: Keep `spl_validator/` frozen in the repository as a **read-only regression reference** while TypeScript parity, native registry ownership, macro expansion, field lineage, and AutoFix are built.
   - **After Phase 3 parity acceptance (`M-04` gate -> `M-05` retirement)**: Archive and remove `spl_validator/` (alongside the legacy HTTP-backed `browser_extension/`) from the main source tree only after TypeScript passes full parity acceptance across the 307-test Python suite, the >= 98.85% strict-mode `splunk/security_content` corpus benchmark, and the new macro-expansion and field-lineage test suites.

3. **HTML Web UI v1 Scope & Extension Sharing (`A5`)**:
   - **Single-Query Deep Workbench (v1)**: The static HTML Web UI v1 focuses exclusively on deep inspection of a single SPL query:
     - Real-time diagnostics and **AutoFix diff preview**;
     - **Side-by-side macro expansion highlight** linking original query tokens to expanded SPL spans;
     - **Interactive field lineage graph** tracing upstream origins and stage-by-stage field transformations;
     - **Local `macros.conf` and lookup CSV header upload** loaded locally in-browser into `ProjectContext`.
   - **Direct reuse in the MV3 extension**: The standalone MV3 Chromium extension (`@spl-validator/extension`) reuses this same Single-Query Deep Workbench UI directly on top of `@spl-validator/core` with zero local HTTP server.
   - **Batch boundary**: Repository-wide batch inspection stays on the CLI (`batch` -> `JSON` / `Markdown` / `SARIF`) instead of duplicating batch file management inside HTML Web UI v1.

## Trade-Offs & Rejected Alternatives

- **Keeping Python as the permanent canonical registry and continuing to export generated TypeScript data**: Rejected because dual-language authoring doubles effort on every command, macro, lineage, and AutoFix change and complicates embedding in browser and JavaScript/hook environments.
- **Pinning the CLI/hook runtime to Node 18 or blocking core milestones on upfront native binary packaging (Node SEA)**: Rejected because Node 18 is outdated and native executable packaging is an independent distribution concern that belongs in a later milestone (`M-06`) after core features stabilize.
- **Retiring the Python baseline before Phase 3 parity acceptance**: Rejected because keeping Python read-only across Phase 0–2 safeguards the 307-test and `security_content` corpus floor until TypeScript proves full parity including macro expansion and field lineage.
- **Maintaining a full-featured Python Textual TUI or adding multi-file batch scanning to HTML Web UI v1**: Rejected because visual single-query inspection is served cleanly by one shared Single-Query Deep Workbench across the static HTML Web UI and standalone MV3 extension, while multi-file repository scans belong in the CLI `batch` command (`JSON` / `Markdown` / `SARIF`).
- **Building a live Splunk-connected or workspace-indexing context service**: Rejected because the actual need is a portable, offline `ProjectContext` payload that an external repo hook or browser user can pass in directly.
- **Maintaining `spl_validator` and `spl-expert` as two peer main repositories**: Rejected because splitting official `.conf` snapshots from the validator that reconciles against them guarantees version drift and duplicate maintenance.
