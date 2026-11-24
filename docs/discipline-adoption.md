---
doc_type: guide
status: current
authority: guidance
---

# Engineering Discipline Adoption Record

This record documents the onboarding of `spl_validator` to the `template-project` engineering discipline (upstream release `2026.11.2`, commit `8abc2bd5`) on **2026-11-24**. Canonical policy settings (`discipline_version`, `[project]`, `[collaboration]`, `[adoption]`, and line budgets) live in [`docs-policy.toml`](../docs-policy.toml).

## 1. Repository Inventory at Adoption (2026-11-24, commit `816a5a5`)

Measured via `read_rules.py onboard --target <repo>`:

- **Project purpose & maturity stage**: Offline static analyzer for Splunk Enterprise 10.0 SPL queries; default stage `usable`.
- **Tracked code and style footprint**: 20,201 lines across 137 code/style files (including both Python and TypeScript implementations plus HTML/JS extension surfaces).
- **Configured source roots**: `typescript/` (active target core, CLI, and standalone MV3 extension) and `spl_validator/` (frozen Python regression reference during migration).
- **Existing test baselines**:
  - TypeScript (`typescript/core/test/`): 43 golden and edge-case tests (`cd typescript && npm run build && npm test`).
  - Python (`tests/`): 307 tests, 2 skipped unless environment variables are set (`pytest tests/`).
  - External corpus benchmark (`docs/security_content_validation.md`, 2026-03-20 snapshot): 1,983 / 2,006 valid (98.85%) in strict mode.
- **Oversized files measured against the 500-line code / 300-line style budget**:
  - `typescript/core/src/generated/registryData.ts` (3,035 lines — generated file; never edit by hand).
  - `spl_validator/core.py` (1,771 lines — frozen Python regression reference).
  - `spl_validator/src/registry/commands.py` (1,133 lines — frozen Python regression reference).
  - `spl_validator/src/parser/parser.py` (879 lines — frozen Python regression reference).
  - `tests/test_edge_cases.py` (648 lines — test harness under `harness_paths`).
  - `typescript/core/src/parseSimple.ts` (636 lines — active TypeScript file; split before expanding parser logic).
  - `typescript/core/src/parser/expressionParser.ts` (526 lines — active TypeScript file; split before expanding expression grammar).
  - `spl_validator/src/analyzer/fields.py` (510 lines — frozen Python regression reference).
  - `spl_validator/validator.py` (503 lines — frozen Python regression reference).

## 2. Rule Applicability Matrix

| Discipline area | Status in `spl_validator` | Concrete local owner or reason |
|---|---|---|
| Single-owner policy & metadata | Adopted now | [`docs-policy.toml`](../docs-policy.toml) (`identity = "product"`, `language = "en"`, `default_stage = "usable"`, `[adoption]` stage `observed`) |
| Working agreement & three-perspective judgment | Adopted now | [`AGENTS.md`](../AGENTS.md) replaces the legacy Cursor Cloud setup prompt |
| Five-part system architecture + Mermaid runtime flow | Adopted now | [`ARCHITECTURE.md`](../ARCHITECTURE.md) covers baseline vs. `ADR-001` target pipeline, boundaries, state owners, and migration invariants |
| Verbatim owner quote lineage (`SRC-*`) | Adopted now | [`docs/sources.toml`](sources.toml) records `SRC-001` and `SRC-002` verbatim in original Chinese without paraphrasing |
| Cross-module architectural decisions (`ADR-*`) | Adopted now | [`docs/decisions/ADR-001-typescript-single-core-and-consolidation.md`](decisions/ADR-001-typescript-single-core-and-consolidation.md) |
| Roadmap slots & task queue | Adopted now | [`docs/work.toml`](work.toml) (`M-01` through `M-06`, `T-01` through `T-10`) |
| Plain, direct English prose | Adopted now | Main docs, ADRs, CLI, and UI use plain English; `docs/sources.toml` keeps original owner wording |
| Module specs (`docs/specs/`), `# Role:` headers & bundled `check_docs.py` | Deferred to `M-02` | Existing codebase starts in `observed` stage; module specs and `# Role:` headers will be added once TypeScript parser files are split and native TS modules stabilize |
| Frontend & visual discipline (WCAG 2.2 AA, keyboard/focus, pre-code design approval) | Applies at `M-05` | Triggered when designing and building the shared Single-Query Deep Workbench static HTML Web UI and refreshing `typescript/extension/` |
| Unattended autonomous charter | Not applicable now | `[collaboration]` runs in `interactive` mode with the human owner in the loop |
| Public-repo privacy & hygiene | Enforced now | Repository is public open source; no private domains, internal IPs, company names, personal-memory paths, or credentials may enter commits |

## 3. Adoption Progression Path

1. **`observed` (current)**: Governance metadata, `ARCHITECTURE.md`, `docs/sources.toml`, `ADR-001`, and `docs/work.toml` establish clear direction and boundaries without blocking existing CI or forcing premature refactors on frozen Python files.
2. **`scoped_enforcement` (planned at `M-02` / `M-03`)**: Add `docs/specs/` module contracts for `typescript/` packages, add `# Role:` headers to claimed TypeScript files, split `parseSimple.ts` and `expressionParser.ts`, and enforce budgets and import boundaries on `typescript/`.
3. **`adopted` (planned at `M-05`)**: Archive and remove legacy `browser_extension/` and frozen Python `spl_validator/` after Phase 3 parity acceptance passes, then enforce checks across the entire remaining TypeScript repository.
