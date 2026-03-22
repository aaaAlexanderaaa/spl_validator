# AGENTS.md

## Cursor Cloud specific instructions

### Overview

SPL Validator is a static analysis / linting tool for Splunk Processing Language (SPL) queries.
It ships a **Python package** (CLI + HTTP API + optional TUI), a **legacy Chromium extension** under `browser_extension/` that calls the HTTP API, and a **TypeScript implementation** under `typescript/` (core library, `spl-validator-ts` CLI, and a **standalone** MV3 extension that bundles the validator without a local server).

### TypeScript as the main entry point

The project is currently **focused on TypeScript** for day-to-day work and for **automated environment setup**. When provisioning or validating a workspace, prioritize the **`typescript/`** workspace: `npm install` there, build **`@spl-validator/core`**, and run its tests. **Only the TypeScript components need to succeed** for that setup path to be considered healthy.

If that setup fails, treat it as a **TypeScript code, config, or dependency problem** to fix in-repo (unless you explicitly need a Python-only path and the failure is unrelated to `typescript/`).

**Automatic or agent-driven bug fixes are allowed** while getting `npm install`, `npm run build`, and `npm test` (TypeScript packages) to pass.

Python remains the **canonical registry**; after editing `spl_validator` command/function registries, run `python3 typescript/scripts/export_registry.py` to refresh generated data under `typescript/core/src/generated/`.

### Running services

- **TypeScript (primary for setup):** from `typescript/`: `npm install`, then `npm run build -w @spl-validator/core`, `npm run test -w @spl-validator/core`, and optionally `npm run build -w @spl-validator/extension`. CLI: `node runtime/dist/cli.js` or the `spl-validator-ts` bin from `@spl-validator/runtime` after build.
- **Python tests:** `pytest tests/` from the repo root (188 tests; 2 skipped by design).
- **CLI:** `python3 -m spl_validator --spl="index=web | stats count BY host"` (or `--format=json`).
- **HTTP API:** `python3 -m spl_validator.httpd --host 127.0.0.1 --port 8765` — serves `POST /validate` and `GET /health`.
- **Browser extension unit tests:** `cd browser_extension && npm test` (builds with esbuild then runs Node test runner).
- **Browser extension E2E:** `cd browser_extension && xvfb-run -a npm run test:e2e` (requires Playwright Chromium + xvfb).

### Gotchas

- The scripts installed via `pip install -e .` (e.g. `spl-validator-httpd`, `pytest`) land in `~/.local/bin`. Ensure `PATH` includes `$HOME/.local/bin`.
- No dedicated Python linter (ruff, flake8, mypy) is configured in the repo. `pytest tests/` is the primary quality gate.
- `tests/test_security_content_scan.py` and the TUI headless smoke test are intentionally skipped unless specific env vars (`SECURITY_CONTENT_ROOT`, `RUN_TUI_HEADLESS_SMOKE`) are set.
- The HTTP server is stdlib-only (`http.server.ThreadingHTTPServer`) — no Flask/FastAPI dependency needed.
- Python >=3.10 is required (uses `match` statements and `X | Y` union types).
- Browser extension E2E tests require Playwright Chromium (`npx playwright install chromium`) and `xvfb` (`sudo apt install xvfb`). Run via `xvfb-run -a npm run test:e2e` from `browser_extension/`. Playwright auto-starts the HTTP server on port 19999 for E2E.
- The E2E test launches Chromium in non-headless mode with `--load-extension`; xvfb provides the virtual display on headless Linux.
- See `README.md` for the full development setup and CLI usage reference.
