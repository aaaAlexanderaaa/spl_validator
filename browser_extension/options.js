async function load() {
  const { apiBase } = await chrome.storage.sync.get({ apiBase: "http://127.0.0.1:8765" });
  document.getElementById("apiBase").value = apiBase;
}

async function save() {
  const apiBase = document.getElementById("apiBase").value.trim() || "http://127.0.0.1:8765";
  await chrome.storage.sync.set({ apiBase });
}

document.addEventListener("DOMContentLoaded", () => {
  load();
  const el = document.getElementById("apiBase");
  el.addEventListener("change", save);
  el.addEventListener("blur", save);
});
