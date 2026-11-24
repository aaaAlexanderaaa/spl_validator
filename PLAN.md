# SPL Validator — Roadmap

The active roadmap, milestone order, and task queue live in [`docs/work.toml`](docs/work.toml), governed by [`ARCHITECTURE.md`](ARCHITECTURE.md) and [`docs/decisions/ADR-001-typescript-single-core-and-consolidation.md`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md) (anchored in owner decisions `SRC-001` and `SRC-002` in [`docs/sources.toml`](docs/sources.toml)).

## Active Direction (`ADR-001`, 2026-11-24)

1. **TypeScript Single Core & Registry Consolidation (`M-02`, Phase 1)**: Reach full parity with the 307-test Python suite and the 98.85% `splunk/security_content` strict-mode baseline, absorb obtainable Splunk Enterprise 10.0 `searchbnf.conf` / `limits.conf` reference snapshots and syntax extraction scripts from `spl-expert`, split oversized TypeScript parser files, and move canonical registry ownership natively into TypeScript while keeping `spl_validator/` frozen as a read-only regression reference through Phase 0–2.
2. **Lightweight `ProjectContext`, Real Macro Expansion & Node >= 22 Dual-Mode Hook CLI (`M-03`, Phase 2)**: Add a plain serializable `ProjectContext` (`macros.conf`, optional lookup CSV headers, custom command packs), expand nested/parameterized backtick macros into real SPL with original source-span mapping, and ship a **Node.js >= 22 LTS** single-file dual-mode `spl-validator.cjs` bundle (one-shot CLI, save-time hooks, `macros.conf` change reverse-impact revalidation, `batch` repo inspection to JSON/Markdown/SARIF, and lazy stdio NDJSON worker paired with a thin Python stdlib wrapper).
3. **Field Lineage, AutoFix Rewriter & Phase 3 Parity Acceptance (`M-04`)**: Trace upstream origins for every output field across pipeline stages, diagnose missing or dropped fields, generate span-anchored AutoFix and optimization rewrites, and run Phase 3 parity acceptance across the 307-test baseline, `security_content` corpus, and macro/field-lineage suites.
4. **Single-Query Deep Workbench (HTML Web UI + MV3 Extension) & Post-Phase-3 Legacy Retirement (`M-05`)**: Ship a zero-server static HTML Web UI v1 focused on the **Single-Query Deep Workbench** (diagnostics + AutoFix diff preview, side-by-side macro expansion highlight, interactive field lineage graph, local `macros.conf`/CSV header upload) reused directly in the standalone MV3 Chromium extension; keep batch repo scanning on the CLI, and archive/remove the legacy HTTP-backed `browser_extension/` and frozen Python core after Phase 3 parity acceptance passes.
5. **Standalone Native Binary Packaging (`M-06`, Later Distribution Milestone)**: Package `@spl-validator/runtime` as a standalone native binary (for example, Node SEA) for zero-Node external deployment after core milestones stabilize.

---

## Historical Baseline (Completed Before `ADR-001`)

The earlier seven-phase plan delivered the initial Python implementation, JSON contract, and first TypeScript port that now serve as the migration regression baseline:

- [x] **Phase 1 — Contract and tests**: Machine-readable JSON Schema (`docs/contract/cli-json-output.schema.json`), contract tests (`tests/test_contract.py`), and shared golden JSON fixtures (`tests/golden/`).
- [x] **Phase 2 — Python kernel & optional registry packs**: Optional YAML `--registry-pack` extension support (`spl_validator/registry_packs/`). *(Full built-in registry migration is now superseded by native TypeScript registry reconciliation in `ADR-001` / `M-02`.)*
- [x] **Phase 3 — Python CLI ergonomics**: Stdin piping, positional SPL argument, and optional `.spl-validator.yaml` defaults.
- [x] **Phase 4 — Python Textual TUI**: Optional `spl-validator-tui` interface. *(Deprioritized going forward in favor of a static HTML Web UI and standalone MV3 extension per `ADR-001`.)*
- [x] **Phase 5 — Stdlib HTTP bridge**: `spl-validator-httpd` serving `/`, `/validate`, and `/health`.
- [x] **Phase 6 — Legacy Chromium extension**: Minimal MV3 popup under `browser_extension/` calling the local HTTP bridge. *(Superseded by standalone `typescript/extension/`.)*
- [x] **Phase 7 — Initial TypeScript implementation**: `@spl-validator/core`, `@spl-validator/runtime`, and standalone `@spl-validator/extension` under `typescript/`. *(Promoted from secondary port to the single target core under `ADR-001`.)*
