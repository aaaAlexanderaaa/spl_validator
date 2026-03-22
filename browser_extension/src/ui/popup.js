import { fetchValidationJson } from "../lib/api.js";

async function validate() {
  const spl = document.getElementById("spl").value;
  const out = document.getElementById("out");
  out.textContent = "…";
  try {
    const { text, json } = await fetchValidationJson(spl, { strict: false, advice: "all" });
    out.textContent = json ? JSON.stringify(json, null, 2) : text;
  } catch (e) {
    out.textContent = String(e);
  }
}

document.getElementById("go").addEventListener("click", () => {
  validate();
});
