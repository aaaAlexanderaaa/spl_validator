async function getApiBase() {
  const { apiBase } = await chrome.storage.sync.get({ apiBase: "http://127.0.0.1:8765" });
  return String(apiBase).replace(/\/$/, "");
}

async function validate() {
  const spl = document.getElementById("spl").value;
  const out = document.getElementById("out");
  out.textContent = "…";
  const base = await getApiBase();
  const url = `${base}/validate`;
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spl, strict: false, advice: "all" }),
    });
    const text = await res.text();
    try {
      out.textContent = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      out.textContent = text;
    }
  } catch (e) {
    out.textContent = String(e);
  }
}

document.getElementById("go").addEventListener("click", () => {
  validate();
});
