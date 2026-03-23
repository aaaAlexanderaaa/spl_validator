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
  --bg:#0f1117;--bg2:#161822;--bg3:#1e2030;--bg-card:#1a1d2e;
  --fg:#cdd6f4;--fg2:#a6adc8;--fg3:#7f849c;
  --accent:#89b4fa;--accent2:#74c7ec;--green:#a6e3a1;--red:#f38ba8;
  --yellow:#f9e2af;--cyan:#89dceb;--mauve:#cba6f7;
  --border:#313244;--border2:#45475a;
  --radius:10px;--radius-sm:6px;
  --shadow:0 4px 24px rgba(0,0,0,.35);
  --font-mono:"JetBrains Mono","Cascadia Code","Fira Code","SF Mono",Consolas,"Liberation Mono",monospace;
  --font-sans:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --transition:all .2s cubic-bezier(.4,0,.2,1);
}
html{font-size:15px;scroll-behavior:smooth}
body{
  font-family:var(--font-sans);background:var(--bg);color:var(--fg);
  min-height:100vh;display:flex;flex-direction:column;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
}

/* Header */
header{
  background:var(--bg2);border-bottom:1px solid var(--border);
  padding:.7rem 1.5rem;display:flex;align-items:center;gap:.75rem;
  position:sticky;top:0;z-index:10;backdrop-filter:blur(12px);
}
header h1{font-size:1.1rem;font-weight:700;letter-spacing:-.01em}
header h1 span{
  background:linear-gradient(135deg,var(--accent),var(--mauve));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}
.version-pill{
  font-size:.65rem;background:var(--bg3);color:var(--fg3);
  padding:.15rem .45rem;border-radius:20px;border:1px solid var(--border);
}

/* Layout */
main{
  flex:1;display:flex;flex-direction:column;padding:1rem 1.5rem;gap:.75rem;
  max-width:960px;width:100%;margin:0 auto;
}
.section-label{
  font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;
  color:var(--fg3);margin-bottom:.25rem;
}

/* Editor */
.editor-wrap{position:relative}
#spl-editor{
  width:100%;min-height:200px;max-height:50vh;resize:vertical;
  font-family:var(--font-mono);font-size:.82rem;line-height:1.65;tab-size:4;
  background:var(--bg2);color:var(--fg);
  border:1.5px solid var(--border);border-radius:var(--radius);
  padding:.75rem 1rem .75rem 1rem;outline:none;
  transition:border-color .2s,box-shadow .2s;
}
#spl-editor:focus{
  border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(137,180,250,.12);
}
#spl-editor::placeholder{color:var(--fg3);opacity:.5}
.editor-meta{
  position:absolute;bottom:.5rem;right:.75rem;
  font-size:.65rem;color:var(--fg3);opacity:.6;pointer-events:none;
  font-family:var(--font-mono);
}

/* Controls */
.controls{
  display:flex;flex-wrap:wrap;align-items:center;gap:.5rem;
}
.btn{
  display:inline-flex;align-items:center;gap:.4rem;
  border:none;border-radius:var(--radius-sm);padding:.45rem 1rem;
  font-weight:600;font-size:.8rem;cursor:pointer;
  transition:var(--transition);font-family:var(--font-sans);
}
.btn-primary{
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  color:var(--bg);box-shadow:0 2px 8px rgba(137,180,250,.2);
}
.btn-primary:hover{filter:brightness(1.1);transform:translateY(-1px);box-shadow:0 4px 16px rgba(137,180,250,.25)}
.btn-primary:active{transform:translateY(0)}
.btn-primary:disabled{opacity:.5;cursor:not-allowed;transform:none}
.ctrl-group{
  display:flex;align-items:center;gap:.35rem;
  background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-sm);
  padding:.25rem .6rem;font-size:.78rem;
}
.ctrl-group label{color:var(--fg2);cursor:pointer;user-select:none;white-space:nowrap}
.ctrl-group select{
  background:transparent;color:var(--fg);border:none;
  font-size:.78rem;cursor:pointer;outline:none;font-family:var(--font-sans);
}
.ctrl-group select option{background:var(--bg3);color:var(--fg)}
.ctrl-group input[type=checkbox]{
  accent-color:var(--accent);cursor:pointer;width:14px;height:14px;
}
.spacer{flex:1}
.kbd{
  font-size:.6rem;background:var(--bg3);border:1px solid var(--border2);
  color:var(--fg3);padding:.1rem .35rem;border-radius:3px;
  font-family:var(--font-mono);
}

/* Results */
#results{
  background:var(--bg-card);border:1.5px solid var(--border);border-radius:var(--radius);
  padding:1rem 1.25rem;min-height:100px;flex:1;overflow:auto;
  display:flex;flex-direction:column;gap:.5rem;
  font-size:.85rem;line-height:1.6;
  transition:border-color .3s;
}
#results:empty::after{
  content:"Paste a query above and press Ctrl+Enter";
  color:var(--fg3);opacity:.3;font-style:italic;text-align:center;
  padding:2rem 0;
}
#results.has-results{border-color:var(--border2)}

/* Result components */
.validity{
  display:inline-flex;align-items:center;gap:.5rem;
  padding:.4rem .8rem;border-radius:var(--radius-sm);
  font-weight:700;font-size:.85rem;
}
.validity.valid{background:rgba(166,227,161,.08);color:var(--green)}
.validity.invalid{background:rgba(243,139,168,.08);color:var(--red)}
.validity svg{width:16px;height:16px}
.stat-row{
  display:flex;gap:1rem;flex-wrap:wrap;
  font-size:.72rem;color:var(--fg3);margin:.1rem 0;
}
.stat-row .stat{display:flex;align-items:center;gap:.25rem}

.group-title{
  font-weight:700;font-size:.78rem;margin-top:.5rem;
  padding-bottom:.2rem;border-bottom:1px solid var(--border);
}
.group-title.errors{color:var(--red)}
.group-title.warnings{color:var(--yellow)}
.item{
  padding:.3rem 0 .3rem .85rem;position:relative;
  border-left:2px solid transparent;font-size:.82rem;
}
.item::before{
  content:"";position:absolute;left:-.1rem;top:.65rem;
  width:5px;height:5px;border-radius:50%;
}
.item.error{border-left-color:rgba(243,139,168,.3)}
.item.error::before{background:var(--red)}
.item.warn{border-left-color:rgba(249,226,175,.3)}
.item.warn::before{background:var(--yellow)}
.item code{
  font-family:var(--font-mono);font-size:.72rem;font-weight:700;
  background:var(--bg3);padding:.1rem .35rem;border-radius:3px;
}
.item .loc{font-size:.65rem;color:var(--fg3);margin-left:.25rem}
.item .hint{
  display:block;font-size:.73rem;color:var(--fg2);
  padding-left:.85rem;margin-top:.15rem;opacity:.7;
}
.item .hint::before{content:"💡 "}

/* JSON toggle */
details.json-block{margin-top:.6rem}
details.json-block summary{
  cursor:pointer;font-size:.78rem;color:var(--accent2);
  font-weight:600;user-select:none;
  display:inline-flex;align-items:center;gap:.3rem;
}
details.json-block summary::marker{color:var(--accent2)}
details.json-block[open] summary{margin-bottom:.4rem}
.json-wrap{
  position:relative;background:var(--bg3);border:1px solid var(--border);
  border-radius:var(--radius-sm);overflow:hidden;
}
.json-wrap pre{
  padding:.75rem 1rem;overflow:auto;max-height:400px;
  font-family:var(--font-mono);font-size:.73rem;line-height:1.55;
  white-space:pre;color:var(--fg);margin:0;
}
.copy-btn{
  position:absolute;top:.4rem;right:.4rem;
  background:var(--bg2);color:var(--fg2);border:1px solid var(--border2);
  border-radius:var(--radius-sm);padding:.2rem .55rem;font-size:.65rem;
  cursor:pointer;transition:var(--transition);font-family:var(--font-sans);
}
.copy-btn:hover{background:var(--accent);color:var(--bg);border-color:var(--accent)}

/* Responsive */
@media(max-width:640px){
  main{padding:.75rem}
  #spl-editor{min-height:140px;font-size:.78rem}
  .kbd,.editor-meta{display:none}
  .ctrl-group{padding:.2rem .4rem;font-size:.72rem}
}
</style>
</head>
<body>
<header>
  <h1><span>SPL Validator</span></h1>
  <span class="version-pill" id="version"></span>
</header>
<main>
  <div class="section-label">SPL Query</div>
  <div class="editor-wrap">
    <textarea id="spl-editor" spellcheck="false"
      placeholder="Paste your Splunk SPL query here…"></textarea>
    <div class="editor-meta" id="editor-meta"></div>
  </div>

  <div class="controls">
    <button class="btn btn-primary" id="btn-validate" type="button">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
      Validate
    </button>
    <div class="ctrl-group">
      <input type="checkbox" id="chk-strict">
      <label for="chk-strict">Strict</label>
    </div>
    <div class="ctrl-group">
      <label for="sel-advice">Advice</label>
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
    <div class="ctrl-group">
      <input type="checkbox" id="chk-auto">
      <label for="chk-auto">Auto on paste</label>
    </div>
    <span class="spacer"></span>
    <span class="kbd">Ctrl+Enter</span>
  </div>

  <div class="section-label">Results</div>
  <div id="results"></div>
</main>

<script>
const editor = document.getElementById("spl-editor");
const results = document.getElementById("results");
const btnValidate = document.getElementById("btn-validate");
const chkStrict = document.getElementById("chk-strict");
const selAdvice = document.getElementById("sel-advice");
const chkAuto = document.getElementById("chk-auto");
const editorMeta = document.getElementById("editor-meta");

let debounceTimer = null;

function updateMeta() {
  const v = editor.value;
  const lines = v ? v.split("\n").length : 0;
  const chars = v.length;
  editorMeta.textContent = lines + " line" + (lines !== 1 ? "s" : "") + " · " + chars + " char" + (chars !== 1 ? "s" : "");
}
editor.addEventListener("input", updateMeta);
updateMeta();

editor.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    doValidate();
  }
  if (e.key === "Tab") {
    e.preventDefault();
    const s = editor.selectionStart, end = editor.selectionEnd;
    editor.value = editor.value.substring(0, s) + "  " + editor.value.substring(end);
    editor.selectionStart = editor.selectionEnd = s + 2;
  }
});

editor.addEventListener("paste", () => {
  if (chkAuto.checked) setTimeout(() => { updateMeta(); doValidate(); }, 60);
});
editor.addEventListener("input", () => {
  if (!chkAuto.checked) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(doValidate, 700);
});

btnValidate.addEventListener("click", doValidate);

async function doValidate() {
  const spl = editor.value.trim();
  if (!spl) { results.innerHTML = ""; results.classList.remove("has-results"); return; }
  btnValidate.disabled = true;
  const origText = btnValidate.innerHTML;
  btnValidate.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg> Validating…';
  try {
    const resp = await fetch("/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spl, strict: chkStrict.checked, advice: selAdvice.value }),
    });
    const data = await resp.json();
    renderResults(data);
  } catch (err) {
    results.innerHTML = '<div class="validity invalid"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> Request failed: ' + esc(err.message) + '</div>';
    results.classList.add("has-results");
  } finally {
    btnValidate.disabled = false;
    btnValidate.innerHTML = origText;
  }
}

function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

function renderResults(data) {
  let h = "";

  if (data.valid) {
    h += '<div class="validity valid"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> VALID</div>';
  } else {
    h += '<div class="validity invalid"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg> INVALID</div>';
  }

  const ne = (data.errors || []).length;
  const nw = (data.warnings || []).length;
  h += '<div class="stat-row">';
  h += '<span class="stat">' + (ne ? '<span style="color:var(--red)">' + ne + ' error' + (ne > 1 ? 's' : '') + '</span>' : '<span style="color:var(--green)">0 errors</span>') + '</span>';
  h += '<span class="stat">' + (nw ? '<span style="color:var(--yellow)">' + nw + ' warning' + (nw > 1 ? 's' : '') + '</span>' : '0 warnings') + '</span>';
  h += '</div>';

  if (ne) {
    h += '<div class="group-title errors">Errors</div>';
    for (const e of data.errors) {
      h += '<div class="item error"><code>' + esc(e.code) + '</code> ' + esc(e.message);
      if (e.line) h += '<span class="loc">L' + e.line + ':' + e.column + '</span>';
      h += '</div>';
      if (e.suggestion) h += '<span class="item error hint">' + esc(e.suggestion) + '</span>';
    }
  }

  if (nw) {
    h += '<div class="group-title warnings">Warnings</div>';
    for (const w of data.warnings) {
      h += '<div class="item warn"><code>' + esc(w.code) + '</code> ' + esc(w.message);
      if (w.line) h += '<span class="loc">L' + w.line + ':' + w.column + '</span>';
      h += '</div>';
      if (w.suggestion) h += '<span class="item warn hint">' + esc(w.suggestion) + '</span>';
    }
  }

  if (!ne && !nw && data.valid) {
    h += '<div style="color:var(--green);text-align:center;padding:.5rem 0;opacity:.7">No issues found.</div>';
  }

  const jsonStr = JSON.stringify(data, null, 2);
  h += '<details class="json-block"><summary>JSON output</summary>';
  h += '<div class="json-wrap"><button class="copy-btn" onclick="copyJSON()">Copy</button>';
  h += '<pre id="json-pre">' + esc(jsonStr) + '</pre></div></details>';

  results.innerHTML = h;
  results.classList.add("has-results");
}

function copyJSON() {
  const pre = document.getElementById("json-pre");
  if (!pre) return;
  navigator.clipboard.writeText(pre.textContent).then(() => {
    const btn = pre.parentElement.querySelector(".copy-btn");
    if (btn) { btn.textContent = "Copied!"; setTimeout(() => btn.textContent = "Copy", 1500); }
  });
}

fetch("/health").then(r => r.json()).then(d => {
  document.getElementById("version").textContent = "v" + (d.package_version || "");
}).catch(() => {});
</script>
</body>
</html>
"""
