#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}/browser_extension"

npm install
npx playwright install chromium
npm run build
npm run test

if command -v xvfb-run >/dev/null 2>&1; then
  xvfb-run -a npm run test:e2e
else
  if [[ -n "${DISPLAY:-}" ]]; then
    npm run test:e2e
  else
    echo "error: no DISPLAY and xvfb-run not installed; install xvfb (e.g. apt install xvfb) or run on a machine with a display" >&2
    exit 1
  fi
fi
