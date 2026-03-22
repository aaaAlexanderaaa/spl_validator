#!/usr/bin/env bash
# One-shot dev environment: Python venv + package (dev+tui) + browser extension + Playwright Chromium.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

if [[ ! -d .venv ]]; then
  if ! python3 -m venv .venv; then
    echo "error: could not create .venv (on Debian/Ubuntu install: sudo apt install python3-venv)" >&2
    exit 1
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev,tui]"

if ! command -v npm >/dev/null 2>&1; then
  echo "warning: npm not found; skip browser_extension setup" >&2
  exit 0
fi

cd browser_extension
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
echo "Installing Playwright Chromium (browser extension e2e)…"
npx playwright install chromium

echo ""
echo "Done. Activate the venv with: source .venv/bin/activate"
echo "Run tests: pytest tests/   |   Extension: cd browser_extension && npm test"
