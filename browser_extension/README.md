# SPL Validator (Chromium extension)

This directory builds an **unpacked MV3 extension** in `dist/` that talks to the local
`spl-validator-httpd` API.

## Build

```bash
cd browser_extension
npm install
npm run build
```

Load `browser_extension/dist` via **Chrome → Extensions → Developer mode → Load unpacked**.

## Test (automated)

```bash
cd browser_extension
npm test
```

- Bundles with esbuild (minified IIFE targets)
- Runs Node unit tests with mocked `chrome.storage` + `fetch`
- Verifies `dist/` artifacts exist

End-to-end (real Chromium + real Python httpd + extension):

```bash
cd browser_extension
npm install
npx playwright install chromium
npm run build
# Extensions require a display buffer on Linux CI:
xvfb-run -a npm run test:e2e
```

On macOS/Windows with a normal desktop session, `npm run test:e2e` is usually enough.
