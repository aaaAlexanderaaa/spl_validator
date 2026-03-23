export const DEFAULT_API_BASE = "http://127.0.0.1:8765";

export async function getApiBase() {
  // Fallback for non-extension contexts (e.g. file:// protocol testing)
  if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.sync) {
    return DEFAULT_API_BASE;
  }
  const { apiBase } = await chrome.storage.sync.get({ apiBase: DEFAULT_API_BASE });
  return String(apiBase).replace(/\/$/, "");
}

export async function setApiBase(apiBase) {
  const v = String(apiBase).trim() || DEFAULT_API_BASE;
  await chrome.storage.sync.set({ apiBase: v });
}
