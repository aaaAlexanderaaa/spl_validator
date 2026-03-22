import { getApiBase } from "./storage.js";

export async function fetchValidationJson(spl, { strict = false, advice = "all" } = {}) {
  const base = await getApiBase();
  const res = await fetch(`${base}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spl, strict, advice }),
  });
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    // leave json null; caller can inspect text
  }
  return { ok: res.ok, status: res.status, text, json };
}
