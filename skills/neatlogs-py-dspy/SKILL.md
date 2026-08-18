---
name: neatlogs-py-dspy
description: Use when adding neatlogs observability to a Python project that uses DSPy (imports `dspy`, defines `dspy.Module`s / signatures).
metadata:
  author: neatlogs
  language: python
  framework: dspy
---

# Neatlogs Python Setup — DSPy

This project uses **DSPy** (`dspy.Module`, `dspy.Predict`, `dspy.ChainOfThought`, `dspy.ReAct`). Neatlogs instruments it with **`neatlogs.wrap(module)`**.

## Core mechanism — `neatlogs.wrap(module)`

`neatlogs.wrap()` installs DSPy class-level hooks (idempotent, global), so passing ANY module instance — including your own `dspy.Module` subclass — patches every module call, nested. Span tree:

```
CHAIN  dspy.Module.__call__   (Predict / ChainOfThought / ReAct / custom — every module call, nested)
  ↳ LLM        dspy.LM.__call__       (the underlying model request)
  ↳ RETRIEVER  dspy.Retrieve.__call__ (if used)
```

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration. The DSPy CHAIN/LLM spans nest under your manual spans.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap a DSPy module with neatlogs.wrap()** → `references/4-wrap-module.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `dspy` (so class hooks patch at the right time). `load_dotenv()` runs before `init()`.
- **Use `neatlogs.wrap(module)`, NOT `instrumentations=["dspy"]`.** `wrap()` patches DSPy's classes directly and works on ANY DSPy version. The `instrumentations=["dspy"]` path uses the OpenInference DSPy instrumentor, which **requires DSPy ≥ 2.6.0 and silently emits no spans on older DSPy** — so prefer `wrap()`, especially when the project pins DSPy < 2.6.
- `neatlogs.wrap(module)` installs GLOBAL DSPy class hooks — calling it once on any module instance traces ALL module/LM calls. Wrapping the top-level pipeline module is enough.
- `wrap()` returns the module unchanged; you can keep using your existing variable.
- Do NOT wrap a single module call in `@span`/`trace` — the CHAIN span is created by the hook. Use `@span` for YOUR orchestration only.
- The DSPy hooks own module, LLM, and retriever spans. Do NOT add a manual `trace(kind="LLM")`, LLM decorator, or provider instrumentor around DSPy-owned model calls.
- Never hardcode API keys — use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `import neatlogs` at module top level.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing wrapped path.
- Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run, with one wrapper-owned hierarchy and no duplicate module/LLM spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference
- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users (customer analytics via identify()) → `references/sessions-and-end-users.md`
