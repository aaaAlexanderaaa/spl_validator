# Scalability of the SPL validator

This document summarizes how the current implementation scales with **corpus size**, **SPL length**, and **registry growth** (commands + functions).

## Complexity (as implemented)

| Area | Behavior | Notes |
|------|----------|--------|
| Command lookup | **O(1)** average | `dict` keyed by canonical command name; alias resolution is one extra dict read. |
| Function lookup | **O(1)** average | Static `dict` plus small regex for `percNN` / `pNN` style names. |
| Lexing | **O(n)** | Single pass over input length `n` characters/tokens. |
| Parsing / pipeline build | **O(n × k)** | `n` tokens; `k` is bounded by nesting depth (parens, subsearches). No backtracking over unbounded alternatives. |
| Per-command validation | **O(c)** | `c` = number of commands in the pipeline; each does bounded work (required-args checks, expression walks). |
| Function validation in expressions | **O(f)** | `f` = number of `FunctionCall` nodes in AST; typically small relative to `n`. |
| Batch scan (e.g. 2k YAML files) | **O(m × n̄)** | `m` searches, `n̄` average SPL length; **linear in total bytes processed**. No cross-query cache today. |

Growing `COMMANDS` or `FUNCTIONS` to **hundreds of entries** does not change asymptotic cost: each is still a constant-time hash lookup. Memory grows **linearly** with registry size (small compared to typical SPL strings and ASTs).

## Practical bottlenecks

1. **Repeated lex/parse per query** — Each `validate(spl)` builds a fresh token list and AST. A long-running service validating the same queries repeatedly would benefit from an **external cache** (keyed by hash of SPL string), not implemented here.
2. **Strict mode + incomplete registry** — `strict=True` surfaces many **SPL013** hits for legitimate add-on commands until they are registered. That is a **product/config** concern, not CPU.
3. **Malformed SPL** — Error recovery can emit **multiple** issues per query; cost is still linear in input size but output volume grows.

## Measured ballpark (reference hardware)

On a typical CI runner, validating **~2,000** detection searches from YAML (security_content–sized) completes in **on the order of seconds** using a single process. Throughput is dominated by Python + lex/parse, not registry lookups.

## Future improvements (if needed)

- Optional **LRU cache** for `(spl, strict, schema_hash) → ValidationResult` in API layer.
- **Parallel** batch scans (multiprocessing) over independent files — embarrassingly parallel; watch GIL if using threads only.
- Split **fast path** (lex/parse only) vs **full path** (semantics + functions) for very large corpora.
