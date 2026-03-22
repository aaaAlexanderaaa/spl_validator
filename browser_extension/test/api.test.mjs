import assert from "node:assert/strict";
import { afterEach, beforeEach, describe, it } from "node:test";

describe("fetchValidationJson", () => {
  let fetchCalls;

  beforeEach(() => {
    fetchCalls = [];
    globalThis.chrome = {
      storage: {
        sync: {
          get: async (_keys, cb) => {
            const result = { apiBase: "http://127.0.0.1:19999" };
            if (typeof cb === "function") {
              cb(result);
            }
            return result;
          },
        },
      },
    };

    globalThis.fetch = async (url, init) => {
      fetchCalls.push({ url, init });
      return {
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            output_schema_version: "1.0",
            package_version: "0.0.0",
            valid: true,
            errors: [],
            warnings: [],
          }),
      };
    };
  });

  afterEach(() => {
    delete globalThis.chrome;
    delete globalThis.fetch;
  });

  it("posts JSON to /validate using storage apiBase", async () => {
    const { fetchValidationJson } = await import(
      new URL("../src/lib/api.js", import.meta.url).href
    );
    const out = await fetchValidationJson("index=web | stats count", {
      strict: false,
      advice: "all",
    });
    assert.equal(out.ok, true);
    assert.equal(out.status, 200);
    assert.equal(out.json.valid, true);
    assert.equal(fetchCalls.length, 1);
    assert.equal(fetchCalls[0].url, "http://127.0.0.1:19999/validate");
    assert.equal(fetchCalls[0].init.method, "POST");
    const body = JSON.parse(fetchCalls[0].init.body);
    assert.equal(body.spl, "index=web | stats count");
    assert.equal(body.strict, false);
    assert.equal(body.advice, "all");
  });
});
