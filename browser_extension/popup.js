const baseUrlInput = document.getElementById("baseUrl");
const splInput = document.getElementById("spl");
const strictInput = document.getElementById("strict");
const out = document.getElementById("out");
const go = document.getElementById("go");

if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
  chrome.storage.local.get(["baseUrl"], (r) => {
    if (r.baseUrl) baseUrlInput.value = r.baseUrl;
  });
}

function saveBase() {
  if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
    chrome.storage.local.set({ baseUrl: baseUrlInput.value.trim() });
  }
}

baseUrlInput.addEventListener("change", saveBase);

go.addEventListener("click", async () => {
  saveBase();
  const base = baseUrlInput.value.replace(/\/$/, "");
  const url = `${base}/validate`;
  const body = {
    spl: splInput.value,
    strict: strictInput.checked,
    advice: "optimization",
  };
  out.textContent = "…";
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      out.textContent = `HTTP ${res.status}\n${text}`;
      return;
    }
    out.textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    out.textContent = String(e);
  }
});
