import { validate, buildValidationJsonDict } from "@spl-validator/core";

function $(id) {
  return document.getElementById(id);
}

$("go").addEventListener("click", () => {
  const spl = $("spl").value;
  const status = $("status");
  const out = $("out");
  status.textContent = "";
  out.textContent = "";
  const result = validate(spl, { strict: false });
  status.innerHTML = result.is_valid
    ? '<span class="ok">Valid</span> (warnings may still apply)'
    : '<span class="bad">Invalid</span>';
  const json = buildValidationJsonDict(result, result.ast, { warningGroups: "all" });
  out.textContent = JSON.stringify(json, null, 2);
});
