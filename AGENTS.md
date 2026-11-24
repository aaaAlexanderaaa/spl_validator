# Repository Working Agreement

`spl_validator` is an offline static analyzer, macro expander, field-lineage inspector, and rewriter for Splunk Enterprise 10.0 SPL queries. This repository adopts the `template-project` engineering discipline (upstream release `2026.11.2`, commit `8abc2bd5`) starting at `[adoption]` stage `observed`. Canonical policy settings (`discipline_version`, `[project]`, `[collaboration]`, `[adoption]`, and file-size budgets) live in [`docs-policy.toml`](docs-policy.toml).

## 1. Priority Order

Apply these priorities in order whenever goals compete:

1. **Data safety, public-repo hygiene, and the requested outcome**: Never commit private domains, internal IPs, company names, personal-memory paths, or credentials to this public repository, and deliver the working result the owner asked for rather than extra paperwork.
2. **Shared vocabulary and single source of truth**: Give every concept one name and every authoritative fact, registry rule, threshold, or roadmap state one owning file.
3. **Clear module boundaries, plain language, and file budgets**: Keep `@spl-validator/core` free of Node/DOM dependencies, write direct prose, and split growing modules by cohesive responsibility.
4. **Stage- and risk-matched real verification**: Run real end-to-end checks on TypeScript builds, CLI execution, and Python regression baselines proportional to domain maturity (`usable` in `docs-policy.toml`).
5. **Lineage and documentation sync**: Keep `docs/sources.toml`, `docs/decisions/`, `ARCHITECTURE.md`, and `docs/work.toml` aligned whenever scope or architecture changes.

## 2. Three-Perspective Judgment Before Writing Code

Before changing code or architecture, check three angles at once:

- **Executor**: Separate settled owner choices ([`docs/sources.toml`](docs/sources.toml) `SRC-*` and [`docs/decisions/ADR-001-typescript-single-core-and-consolidation.md`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md)) from open implementation details. Follow settled choices directly; challenge a settled constraint only when concrete evidence shows a clearly better alternative.
- **Collaborator**: Match ceremony to design stability. Keep early exploration light; once an interface or module boundary settles, write it into `ARCHITECTURE.md` or the owning spec.
- **Senior Architect**: Check the repository's `default_stage` (`usable` in `docs-policy.toml`) and proactively supply clean boundaries, error paths, and data ownership when an owner states a workflow need informally.

## 3. Core Working Rules (By Object and Effect)

| Concrete object or situation | Required action |
|---|---|
| Human- or AI-readable text (`README.md`, `ARCHITECTURE.md`, ADRs, CLI output, errors, UI copy) | Write plain, direct English: state what the object is, how it works, and what problem it solves. Avoid coined jargon, stacked defensive disclaimers, and raw internal enum tokens. Keep verbatim owner quotes in their original language inside [`docs/sources.toml`](docs/sources.toml) without translating or paraphrasing. |
| System or module architecture ([`ARCHITECTURE.md`](ARCHITECTURE.md) and future `docs/specs/`) | Cover all five parts: (1) positioning, promises, and out-of-scope boundaries; (2) end-to-end runtime and failure flow in `mermaid`; (3) bounded subsystems, narrow interfaces, and forbidden couplings; (4) single-source state owners and hard invariants; (5) entrypoints and verification checks. |
| Validation logic, registry data, and single source of truth | **TypeScript (`typescript/`) is the target single core** ([`ADR-001`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md)). Put all new parser, macro expansion, semantic reconciliation, field lineage, and AutoFix work in TypeScript. Keep the Python core (`spl_validator/`) frozen as the regression reference baseline until TypeScript reaches full parity—do not expand Python as the future canonical registry. |
| Source files, stylesheets, and file-size budgets | Keep new and actively edited files within `max_source_lines` and `max_style_lines` in [`docs-policy.toml`](docs-policy.toml), avoid catch-all `utils / helpers / common / misc` directories, and add 2–3 line `# Role:` headers once `docs/specs/` claims files via `owns`. Respect the historical/generated file list in Section 4 below. |
| UI surfaces (static HTML Web UI and MV3 browser extension) | Meet WCAG 2.2 AA contrast (`4.5:1` for text, `3:1` for input/control borders and focus indicators), full keyboard navigation, visible `:focus-visible` outlines, `prefers-reduced-motion`, and explicit loading, empty, and error states. Draft layout options and get owner sign-off before locking a new UI design. |
| Substantive owner quote, trade-off, or direction change | Append exact unedited owner words chronologically to [`docs/sources.toml`](docs/sources.toml) (`SRC-*`), record cross-module trade-offs in `docs/decisions/ADR-*.md` linking `sources`, and update [`docs/work.toml`](docs/work.toml). |
| Verification and independent review | Verify bidirectionally: (1) Promise → Observation on real runtime entrypoints (CLI, builds, test suites, extension bundles); (2) Observation → Unintended Side Effects (`git status`, JSON output schema compatibility, regression baselines). In `interactive` mode (`docs-policy.toml`), skip automatic multi-subagent reviews on routine edits; reserve fresh-context, open-ended, closed-loop independent review for breaking contract/grammar changes, security boundaries, or explicit owner `/grill` requests. |

## 4. File Budgets, Historical Exceptions & Generated Artifacts

File-size budgets (`max_source_lines` and `max_style_lines`) and `[adoption]` stage (`observed`) are owned by [`docs-policy.toml`](docs-policy.toml). Track these existing oversized files explicitly rather than growing them further:

- **Generated file (never edit by hand)**:
  - `typescript/core/src/generated/registryData.ts` (3,035 lines; regenerated via `python3 typescript/scripts/export_registry.py` only while migrating registry ownership to native TypeScript).
- **Frozen Python regression baseline (do not add new features here)**:
  - `spl_validator/core.py` (1,771 lines)
  - `spl_validator/src/registry/commands.py` (1,133 lines)
  - `spl_validator/src/parser/parser.py` (879 lines)
  - `spl_validator/src/analyzer/fields.py` (510 lines)
  - `spl_validator/validator.py` (503 lines)
- **Active TypeScript files currently above budget (split by cohesive responsibility before expanding)**:
  - `typescript/core/src/parseSimple.ts` (636 lines)
  - `typescript/core/src/parser/expressionParser.ts` (526 lines)

## 5. Direct Prohibitions

- **No unrequested wide rewrites**: Complete only the authorized task and its real verification cleanly; do not run sweeping self-directed refactors across unrelated subsystems.
- **No shortcuts on real execution paths**: Verify actual TypeScript builds, CLI outputs, JSON contract compliance (`docs/contract/cli-json-output.schema.json`), and regression parity rather than assuming edits work from code inspection alone.
- **No silent baseline regressions**: Do not regress the 307-test Python suite or the 98.85% strict-mode `splunk/security_content` benchmark (1,983 / 2,006 detections on the 2026-03-20 snapshot) without documenting an explicit, verified SPL defect.
- **No unapproved design sign-off**: Do not treat exploratory UI drafts as owner approval.
- **No sensitive data in this public repo**: Never include private domains, internal or Tailscale IPs, real company names, or credentials in code, tests, fixtures, or quotes.

## 6. Build, Test & Verification Commands

### TypeScript Workspace (Primary Target Core)

```bash
cd typescript
npm install
npm run build                        # builds @spl-validator/core, runtime, and extension
npm test                             # runs @spl-validator/core golden + edge-case tests (43 tests)
```

Package-specific builds and CLI invocation:

```bash
cd typescript
npm run build -w @spl-validator/core
npm run build -w @spl-validator/runtime
npm run build -w @spl-validator/extension

node runtime/dist/cli.js --format=json --spl 'index=web | stats count BY host'
node runtime/dist/cli.js --file /path/to/query.spl
```

### Python Regression Reference (Frozen Baseline)

Requires Python `>= 3.10`. Run from repository root:

```bash
pytest tests/                        # 307 tests (2 skipped unless env vars are set)
```

Optional external detection corpus check (strict mode by default; see [`docs/security_content_validation.md`](docs/security_content_validation.md)):

```bash
python3 tools/scan_external_detections.py --root /path/to/security_content/detections
```

Legacy HTTP-backed Chromium extension unit tests (`browser_extension/`, deprecated in favor of `typescript/extension/`):

```bash
cd browser_extension && npm test
```

## 7. Key Repository Entrypoints

- System architecture and runtime pipeline: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Settled strategic decisions: [`docs/decisions/ADR-001-typescript-single-core-and-consolidation.md`](docs/decisions/ADR-001-typescript-single-core-and-consolidation.md)
- Verbatim owner direction quotes: [`docs/sources.toml`](docs/sources.toml)
- Active milestones and task queue: [`docs/work.toml`](docs/work.toml)
- Discipline adoption record: [`docs/discipline-adoption.md`](docs/discipline-adoption.md)
- Machine-readable JSON output contract: [`docs/contract/cli-json-output.schema.json`](docs/contract/cli-json-output.schema.json)
