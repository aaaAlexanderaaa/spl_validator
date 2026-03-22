# AGENTS.md

## Cursor Cloud specific instructions

### Overview

SPL Validator is a static analysis / linting tool for Splunk Processing Language (SPL) queries.
It consists of two products: a **Python package** (CLI + HTTP API + optional TUI) and a **Chromium browser extension** that talks to the HTTP API.

### Running services

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
- See `README.md` for the full development setup and CLI usage reference.
