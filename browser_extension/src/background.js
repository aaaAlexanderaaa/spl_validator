// Minimal MV3 service worker: required for manifest v3 and enables stable extension
// discovery in automated tests (Playwright waits for the service worker URL).
chrome.runtime.onInstalled.addListener(() => {});
