# TypeScript Workspace — Development Guide

> **Status:** Active target single core under [`ADR-001`](decisions/ADR-001-typescript-single-core-and-consolidation.md). During migration from the frozen Python regression baseline, the TypeScript workspace shares golden test fixtures (`tests/golden/`) and powers the Node.js CLI and standalone MV3 browser extension. See [`ARCHITECTURE.md`](../ARCHITECTURE.md) for the full target pipeline.

## Overview

The `typescript/` workspace contains three packages:

| Package | Path | Purpose |
|---------|------|---------|
| `@spl-validator/core` | `typescript/core/` | Lexer, parser, analyzer — port of `spl_validator` Python |
| `@spl-validator/runtime` | `typescript/runtime/` | Node.js CLI (`spl-validator-ts`) wrapping core |
| `@spl-validator/extension` | `typescript/extension/` | MV3 Chromium extension — validates in-browser, no HTTP server |

## Quickstart

```bash
cd typescript
npm install
npm run build                              # builds all three packages
npm run test -w @spl-validator/core        # 43 golden + edge-case tests
npm run build -w @spl-validator/extension  # then load typescript/extension/dist unpacked in chrome://extensions
```

## CLI usage

After building:

```bash
node runtime/dist/cli.js --format=json --spl 'index=_internal | head 5'
node runtime/dist/cli.js --file /path/to/query.spl
echo 'index=web | stats count' | node runtime/dist/cli.js --format=json
```

## Relationship to Python (Transitional)

Under [`ADR-001`](decisions/ADR-001-typescript-single-core-and-consolidation.md), TypeScript is taking over as the single core and canonical registry (`M-02` in [`docs/work.toml`](work.toml)). Until native TypeScript registry reconciliation completes, the frozen Python package still supplies the temporary exported snapshot and cross-language golden fixtures:
- Transitional command registry export source (`spl_validator/src/registry/commands.py`)
- Transitional function registry export source (`spl_validator/src/registry/functions.py`)
- Cross-language golden test fixtures (`tests/golden/*.json`)

Do not add new long-term features to Python; only run the export script if synchronizing a transitional baseline fix:

```bash
python3 typescript/scripts/export_registry.py
```

This overwrites the generated artifact `typescript/core/src/generated/registryData.ts` (never edit generated files by hand).

## Extension (MV3)

The TypeScript extension (`typescript/extension/`) is a fully self-contained Chromium extension that validates SPL entirely in the browser — **no local HTTP server required**. It bundles `@spl-validator/core` via esbuild.

To load it:
1. Build: `npm run build -w @spl-validator/extension`
2. Open `chrome://extensions` → Enable developer mode → Load unpacked → Select `typescript/extension/dist`

**Permissions:** The extension requests **zero** browser permissions (see `typescript/extension/src/manifest.json`).

## Tests

TypeScript core tests validate against the same golden JSON fixtures used by the Python test suite, ensuring cross-language consistency:

```bash
npm run test -w @spl-validator/core   # 43 tests (golden + edge cases)
```
