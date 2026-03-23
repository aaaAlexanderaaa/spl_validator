"""Embedded single-page web UI for the SPL Validator HTTP server.

Served at GET / by ``spl_validator.httpd`` so users can paste queries
directly in the browser — no files, no shell quoting.
"""

WEB_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SPL Validator</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#1a1b26;--bg2:#24283b;--bg3:#292e42;--fg:#c0caf5;--fg2:#a9b1d6;
  --accent:#7aa2f7;--green:#9ece6a;--red:#f7768e;--yellow:#e0af68;
  --cyan:#7dcfff;--border:#3b4261;--radius:8px;--shadow:0 2px 8px rgba(0,0,0,.3);
}
html{font-size:15px}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen,sans-serif;
  background:var(--bg);color:var(--fg);min-height:100vh;
  display:flex;flex-direction:column;
}
header{
  background:var(--bg2);border-bottom:1px solid var(--border);
  padding:.75rem 1.5rem;display:flex;align-items:center;gap:1rem;
}
header h1{font-size:1.15rem;font-weight:600;color:var(--accent)}
header .version{font-size:.75rem;color:var(--fg2);opacity:.6}
main{flex:1;display:flex;flex-direction:column;padding:1rem 1.5rem;gap:.75rem;max-width:1200px;width:100%;margin:0 auto}
label{font-size:.8rem;color:var(--fg2);font-weight:500}

/* Editor */
#spl-editor{
  width:100%;min-height:220px;resize:vertical;
  font-family:"Cascadia Code","Fira Code","JetBrains Mono","SF Mono",Consolas,monospace;
  font-size:.875rem;line-height:1.5;tab-size:4;
  background:var(--bg2);color:var(--fg);border:1px solid var(--border);
  border-radius:var(--radius);padding:.75rem 1rem;outline:none;
  transition:border-color .15s;
}
#spl-editor:focus{border-color:var(--accent)}
#spl-editor::placeholder{color:var(--fg2);opacity:.4}

/* Controls */
.controls{
  display:flex;flex-wrap:wrap;align-items:center;gap:.75rem;
}
.controls button{
  background:var(--accent);color:#1a1b26;border:none;
  border-radius:var(--radius);padding:.5rem 1.2rem;
  font-weight:600;font-size:.85rem;cursor:pointer;transition:opacity .15s;
}
.controls button:hover{opacity:.85}
.controls button:active{opacity:.7}
.controls .cb-wrap{display:flex;align-items:center;gap:.35rem}
.controls select,.controls input[type=checkbox]{
  background:var(--bg3);color:var(--fg);border:1px solid var(--border);
  border-radius:4px;padding:.3rem .5rem;font-size:.8rem;cursor:pointer;
}
.controls select{padding-right:1.5rem;appearance:auto}
.hint{font-size:.72rem;color:var(--fg2);opacity:.5;margin-left:auto}

/* Results */
#results{
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);
  padding:1rem 1.25rem;min-height:120px;flex:1;overflow:auto;
  display:flex;flex-direction:column;gap:.6rem;
  font-size:.875rem;line-height:1.55;
}
#results:empty::after{
  content:"Paste a query above and press Validate (Ctrl+Enter)";
  color:var(--fg2);opacity:.35;font-style:italic;
}
.badge{
  display:inline-block;padding:.15rem .6rem;border-radius:4px;
  font-weight:700;font-size:.8rem;
}
.badge-valid{background:rgba(158,206,106,.15);color:var(--green)}
.badge-invalid{background:rgba(247,118,142,.15);color:var(--red)}
.section-title{font-weight:600;font-size:.82rem;margin-top:.4rem}
.error-item,.warn-item{padding-left:1rem;position:relative}
.error-item::before{content:"•";position:absolute;left:0;color:var(--red)}
.warn-item::before{content:"•";position:absolute;left:0;color:var(--yellow)}
.suggestion{font-size:.78rem;color:var(--fg2);padding-left:1rem;opacity:.7}
.pipeline-info{font-size:.78rem;color:var(--fg2);opacity:.5}

/* JSON toggle */
details.json-block{margin-top:.5rem}
details.json-block summary{
  cursor:pointer;font-size:.8rem;color:var(--cyan);user-select:none;
}
details.json-block pre{
  background:var(--bg3);border:1px solid var(--border);border-radius:var(--radius);
  padding:.75rem 1rem;margin-top:.5rem;overflow:auto;max-height:400px;
  font-family:"Cascadia Code","Fira Code",Consolas,monospace;
  font-size:.78rem;line-height:1.5;white-space:pre;color:var(--fg);
  position:relative;
}
.copy-btn{
  position:absolute;top:.5rem;right:.5rem;
  background:var(--bg2);color:var(--fg2);border:1px solid var(--border);
  border-radius:4px;padding:.2rem .5rem;font-size:.7rem;cursor:pointer;
}
.copy-btn:hover{background:var(--accent);color:#1a1b26}

/* Responsive */
@media(max-width:640px){
  main{padding:.75rem}
  #spl-editor{min-height:150px;font-size:.8rem}
  .hint{display:none}
}
</style>
</head>
<body>
<header>
  <h1>SPL Validator</h1>
  <span class="version" id="version"></span>
</header>
<main>
  <label for="spl-editor">SPL Query — paste directly, then Ctrl+Enter to validate</label>
  <textarea id="spl-editor" spellcheck="false"
    placeholder="Paste your SPL query here...&#10;&#10;Example:&#10;index=_internal | head 5 | stats count by sourcetype"></textarea>
  <div class="controls">
    <button id="btn-validate" type="button">Validate (Ctrl+Enter)</button>
    <div class="cb-wrap">
      <input type="checkbox" id="chk-strict">
      <label for="chk-strict">Strict</label>
    </div>
    <div class="cb-wrap">
      <label for="sel-advice">Advice:</label>
      <select id="sel-advice">
        <option value="optimization" selected>optimization</option>
        <option value="all">all</option>
        <option value="none">none</option>
        <option value="limits">limits</option>
        <option value="style">style</option>
        <option value="semantic">semantic</option>
        <option value="diagnostic">diagnostic</option>
      </select>
    </div>
    <div class="cb-wrap">
      <input type="checkbox" id="chk-auto">
      <label for="chk-auto">Auto-validate on paste</label>
    </div>
    <span class="hint">Ctrl+Enter to validate</span>
  </div>
  <div id="results"></div>
</main>

<script>
const editor = document.getElementById("spl-editor");
const results = document.getElementById("results");
const btnValidate = document.getElementById("btn-validate");
const chkStrict = document.getElementById("chk-strict");
const selAdvice = document.getElementById("sel-advice");
const chkAuto = document.getElementById("chk-auto");

let debounceTimer = null;

/* Ctrl+Enter to validate */
editor.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    doValidate();
  }
});

/* Auto-validate on paste / input */
editor.addEventListener("paste", () => {
  if (chkAuto.checked) setTimeout(doValidate, 80);
});
editor.addEventListener("input", () => {
  if (!chkAuto.checked) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(doValidate, 600);
});

btnValidate.addEventListener("click", doValidate);

async function doValidate() {
  const spl = editor.value.trim();
  if (!spl) { results.innerHTML = ""; return; }
  btnValidate.disabled = true;
  btnValidate.textContent = "Validating…";
  try {
    const resp = await fetch("/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spl,
        strict: chkStrict.checked,
        advice: selAdvice.value,
      }),
    });
    const data = await resp.json();
    renderResults(data);
  } catch (err) {
    results.innerHTML = `<span style="color:var(--red)">Request failed: ${esc(err.message)}</span>`;
  } finally {
    btnValidate.disabled = false;
    btnValidate.textContent = "Validate (Ctrl+Enter)";
  }
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function renderResults(data) {
  let html = "";

  /* Validity badge */
  if (data.valid) {
    html += `<span class="badge badge-valid">✅ VALID SPL</span>`;
  } else {
    html += `<span class="badge badge-invalid">❌ INVALID SPL</span>`;
  }

  /* Errors */
  if (data.errors && data.errors.length) {
    html += `<div class="section-title" style="color:var(--red)">Errors (${data.errors.length})</div>`;
    for (const e of data.errors) {
      html += `<div class="error-item"><strong>${esc(e.code)}</strong> ${esc(e.message)}`;
      if (e.line) html += ` <span style="opacity:.45;font-size:.75rem">line ${e.line}:${e.column}</span>`;
      html += `</div>`;
      if (e.suggestion) html += `<div class="suggestion">💡 ${esc(e.suggestion)}</div>`;
    }
  }

  /* Warnings */
  if (data.warnings && data.warnings.length) {
    html += `<div class="section-title" style="color:var(--yellow)">Warnings (${data.warnings.length})</div>`;
    for (const w of data.warnings) {
      html += `<div class="warn-item"><strong>${esc(w.code)}</strong> ${esc(w.message)}`;
      if (w.line) html += ` <span style="opacity:.45;font-size:.75rem">line ${w.line}:${w.column}</span>`;
      html += `</div>`;
      if (w.suggestion) html += `<div class="suggestion">💡 ${esc(w.suggestion)}</div>`;
    }
  }

  if (!data.errors?.length && !data.warnings?.length && data.valid) {
    html += `<div style="color:var(--green);opacity:.7">No issues found.</div>`;
  }

  /* JSON toggle */
  const jsonStr = JSON.stringify(data, null, 2);
  html += `<details class="json-block"><summary>Show JSON output</summary>`;
  html += `<pre id="json-pre"><button class="copy-btn" onclick="copyJSON()">Copy</button>${esc(jsonStr)}</pre></details>`;

  results.innerHTML = html;
}

function copyJSON() {
  const pre = document.getElementById("json-pre");
  if (!pre) return;
  const text = pre.textContent.replace(/^Copy/, "").trim();
  navigator.clipboard.writeText(text).then(() => {
    const btn = pre.querySelector(".copy-btn");
    if (btn) { btn.textContent = "Copied!"; setTimeout(() => btn.textContent = "Copy", 1200); }
  });
}

/* Fetch version on load */
fetch("/health").then(r => r.json()).then(d => {
  document.getElementById("version").textContent = "v" + (d.package_version || "");
}).catch(() => {});
</script>
</body>
</html>
"""
