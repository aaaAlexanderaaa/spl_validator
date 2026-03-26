# TypeScript Port — Development Guide

> **Status:** Experimental. The TypeScript implementation mirrors the Python validator's core logic using shared golden test fixtures. It powers the standalone MV3 browser extension and a Node.js CLI.

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

## Relationship to Python

Python is the **canonical** source for:
- Command registry (`spl_validator/src/registry/commands.py`)
- Function registry (`spl_validator/src/registry/functions.py`)
- Golden test fixtures (`tests/golden/*.json`)

After editing the Python registries, regenerate the TypeScript data:

```bash
python3 typescript/scripts/export_registry.py
```

This writes to `typescript/core/src/generated/registryData.ts`.

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
