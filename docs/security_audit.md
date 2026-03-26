# SPL Validator — Security Audit & Architecture Review

**Date:** 2026-03-23  
**Scope:** Full codebase — Python package, HTTP server, web UI, TUI, CLI, legacy browser extension, TypeScript port  
**Purpose:** Provide transparency about data handling, network behavior, and the absence of backdoors

---

## Executive Summary

SPL Validator is a **fully offline, local-only** static analysis tool. It **does not transmit user data to any external service**, contains **no telemetry or analytics**, and has **no network dependencies** for its core validation functionality. All processing happens in-process on the user's machine.

---

## 1. Architecture Overview

```
User Input (SPL query)
    │
    ├─→ CLI (python3 -m spl_validator)     → stdout/stderr
    ├─→ TUI (spl-validator-tui)            → terminal display
    ├─→ HTTP API (spl-validator-httpd)      → JSON response to caller
    │       └─→ Web UI (GET /)             → browser (same-origin fetch)
    ├─→ Browser Extension (legacy)          → popup display (calls local HTTP API)
    ├─→ Browser Extension (TypeScript)      → popup display (fully in-browser, no HTTP)
    └─→ TypeScript CLI (spl-validator-ts)   → stdout/stderr

All paths: Input → Lexer → Parser → Analyzer → Result (local only)
```

**No path sends user SPL to any external server.** The HTTP API listens only on `127.0.0.1` by default and serves results back to the requesting client.

## 2. Data Privacy

### What data the tool processes

- **SPL query text** provided by the user
- **Optional configuration** (`.spl-validator.yaml`, registry packs, schema files) — all local files
- **No** user accounts, authentication tokens, or personal information

### What data the tool stores

| Location | Content | Lifetime |
|----------|---------|----------|
| stdout/stderr | Validation results (text or JSON) | Transient (terminal buffer) |
| `spl_validation_result.json` (TUI Ctrl+S) | JSON validation output in CWD | Until user deletes |
| Temp file for `--edit` | User's SPL query | Deleted immediately after editor closes |
| Browser extension `chrome.storage.local` | API base URL setting only | Until user clears extension data |

### What data the tool does NOT store or transmit

- **No** query history or logging of user SPL
- **No** crash reports, usage analytics, or telemetry
- **No** network calls to external services from any component
- **No** cookies, tracking pixels, or fingerprinting in the web UI

## 3. Network Behavior

### Inbound only (HTTP server)

The HTTP server (`spl_validator/httpd.py`) is a stdlib `ThreadingHTTPServer` that:
- Binds to `127.0.0.1:8765` by default (localhost only)
- Accepts `POST /validate` (JSON body with SPL), `GET /health`, `GET /` (web UI HTML)
- Returns validation results as JSON
- **Does not make any outbound HTTP requests**

### No outbound network in application code

Verified by full codebase search: the `spl_validator` Python package contains **zero** imports of `requests`, `httpx`, `aiohttp`, or `urllib.request` in application modules. The only `urllib.request` usage is in test files (against localhost).

### Web UI

The embedded web UI (`spl_validator/web_ui.py`) uses only two `fetch()` calls:
- `fetch("/validate", ...)` — same-origin POST to the local server
- `fetch("/health")` — same-origin GET for version display

No external CDN, fonts, analytics scripts, or third-party resources are loaded.

### Browser extensions

| Extension | Network behavior |
|-----------|-----------------|
| Legacy (`browser_extension/`) | POSTs SPL to user-configured API URL (default `http://127.0.0.1:8765`) |
| TypeScript (`typescript/extension/`) | **No network at all** — validates entirely in-browser using bundled core |

## 4. Dependency Audit

### Python runtime dependencies

| Package | Version | Purpose | Notes |
|---------|---------|---------|-------|
| PyYAML | ≥6.0 | Config/schema/registry pack parsing | Uses `yaml.safe_load` only (no arbitrary object deserialization) |

### Python optional dependencies

| Package | Extra | Purpose |
|---------|-------|---------|
| pytest | `[dev]` | Test runner |
| jsonschema | `[dev]` | Contract/schema tests |
| textual | `[tui]` | Terminal UI framework |

### TypeScript/npm

The TypeScript `@spl-validator/core` package has **zero runtime dependencies**. Dev dependencies (`typescript`, `tsx`, `esbuild`) are build-time only and not shipped to end users.

### Supply chain notes

- All YAML parsing uses **`yaml.safe_load`** — immune to the `yaml.load` arbitrary code execution vulnerability
- No native/C extensions beyond PyYAML's optional C loader
- Recommend pinning versions and running `pip audit` / `npm audit` in CI

## 5. Code Execution Safety

### No eval/exec of user input

The validator parses SPL using a custom lexer (`spl_validator/src/lexer/`) and recursive-descent parser (`spl_validator/src/parser/`). **User SPL is never passed to Python's `eval()`, `exec()`, or `compile()`**. It is treated as data, not code.

### Subprocess usage

| Feature | Mechanism | Risk |
|---------|-----------|------|
| `--clipboard` | `subprocess.run(["xclip", ...])` with fixed argv | Low — command list is hardcoded, not user-controlled |
| `--edit` | `os.system(f'{editor} "{tmp_path}"')` | Medium — `$EDITOR` env var is used in a shell string; only a risk if the environment is already hostile |

**Recommendation:** Users in untrusted environments should avoid `--edit` or set `EDITOR` to a known-safe value. The `--clipboard` and `--file` paths have no subprocess injection risk.

## 6. HTTP Server Hardening

| Control | Status | Details |
|---------|--------|---------|
| Bind address | ✅ Localhost by default | `--host 127.0.0.1` (not `0.0.0.0`) |
| Request body limit | ✅ 2 MB default | `--max-body` flag; rejects before reading |
| CORS | ⚠️ Permissive | Reflects `Origin` header; allows `*` when no Origin. Acceptable for localhost dev tool; not for production deployment |
| Authentication | ❌ None | Appropriate for local dev tool; do not expose to network |
| Rate limiting | ❌ None | Appropriate for localhost; add if deploying on a network |
| TLS | ❌ None | Localhost HTTP only; use a reverse proxy for TLS if needed |
| Path traversal | ✅ Not applicable | No filesystem paths derived from URL; only fixed routes |

## 7. Browser Extension Permissions

### Legacy extension (`browser_extension/src/manifest.json`)

```json
{
  "permissions": ["storage"],
  "host_permissions": ["http://127.0.0.1/*", "http://localhost/*"]
}
```

- **storage**: Stores API base URL preference only
- **host_permissions**: Restricted to localhost — cannot access any web pages or browsing data
- **No** `tabs`, `scripting`, `activeTab`, `<all_urls>`, `history`, or `cookies` permissions

### TypeScript extension (`typescript/extension/src/manifest.json`)

```json
{
  "permissions": []
}
```

- **Zero permissions** — the TypeScript extension bundles the validator and runs entirely offline in the extension popup

## 8. What This Tool Cannot Do

For full transparency, SPL Validator **cannot**:

- Access your Splunk instance, data, or credentials
- Read browser history, cookies, or page content
- Send data to any external server
- Execute arbitrary code from SPL input
- Modify files outside its own output (JSON results, temp editor file)
- Access network resources beyond the local HTTP listener
- Collect any form of analytics, telemetry, or usage statistics

## 9. Recommendations for Users

1. **Run the HTTP server on localhost only** (the default). Do not bind to `0.0.0.0` unless behind authentication.
2. **Keep dependencies updated**: `pip install --upgrade PyYAML` and `npm audit` periodically.
3. **Review `$EDITOR`** if using `--edit` in shared environments.
4. **For CI/CD pipelines**: Use the CLI with `--file` or stdin — no HTTP server needed.

## 10. Reproducibility

This audit was performed against the repository at commit `a642664` on branch `cursor/development-environment-setup-13fe`. All claims can be verified by:

```bash
# No outbound network in application code
grep -r "requests\.\|httpx\.\|aiohttp\.\|urllib\.request" spl_validator/ --include="*.py" | grep -v test

# No eval/exec of user input
grep -rn "eval(" spl_validator/ --include="*.py" | grep -v "# " | grep -v "\"eval"

# YAML safe_load only
grep -rn "yaml\." spl_validator/ --include="*.py"

# Extension permissions
cat browser_extension/src/manifest.json | python3 -c "import sys,json; m=json.load(sys.stdin); print(m.get('permissions',[])); print(m.get('host_permissions',[]))"
cat typescript/extension/src/manifest.json | python3 -c "import sys,json; m=json.load(sys.stdin); print(m.get('permissions',[])); print(m.get('host_permissions',[]))"
```
