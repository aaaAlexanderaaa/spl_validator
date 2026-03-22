import { getApiBase, setApiBase } from "../lib/storage.js";

document.addEventListener("DOMContentLoaded", async () => {
  const input = document.getElementById("apiBase");
  input.value = await getApiBase();
  const save = async () => {
    await setApiBase(input.value);
  };
  input.addEventListener("change", save);
  input.addEventListener("blur", save);
});
