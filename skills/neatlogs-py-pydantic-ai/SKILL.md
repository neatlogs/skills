---
name: neatlogs-py-pydantic-ai
description: Use when adding neatlogs observability to a Python project that uses Pydantic AI (imports `pydantic_ai`, constructs an `Agent`).
metadata:
  author: neatlogs
  language: python
  framework: pydantic-ai
---

# Neatlogs Python Setup — Pydantic AI

This project uses **Pydantic AI** (`pydantic_ai.Agent`). Neatlogs instruments it with **`neatlogs.wrap(agent)`** — wrap each Agent instance once and its run/model/tool calls are auto-traced.

## Core mechanism — `neatlogs.wrap(agent)`

`neatlogs.wrap()` detects the Pydantic AI Agent and patches `run` / `run_sync` / `run_stream` / `iter`, plus installs class-level model (LLM) and tool (TOOL) hooks. Wrapping produces a nested span tree:

```
AGENT  (agent.run / run_sync / run_stream / iter)
  ↳ LLM   (Model.request / request_stream — one per model call)
  ↳ TOOL  (one per tool invocation)
```

Combine it with the manual primitives for your own orchestration code:
- `@neatlogs.span(kind="WORKFLOW"|"CHAIN"|...)` — decorate functions that orchestrate agent calls.
- `neatlogs.trace("name", kind=...)` — create the sole span for an unsupported/custom operation that needs direct canonical attributes or an extended kind such as `RERANKER`, `VECTOR_STORE`, `EVALUATOR`, or raw `LLM`.
- `neatlogs.log("msg {x}", x=...)` — timestamped steps inside a span.

The wrapper's AGENT/LLM/TOOL spans nest correctly under application-owned orchestration. Never put a same-operation `trace()` inside an `@span`, and never put a manual LLM span around the wrapped agent.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Agent with neatlogs.wrap()** → `references/4-wrap-agent.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `pydantic_ai` (so class-level hooks patch at the right time). If `load_dotenv()` exists, it runs before `init()`.
- Wrap EVERY `Agent` instance whose runs you want traced: `agent = neatlogs.wrap(agent)`. `wrap()` returns the same instance (also patches in place); use the returned reference.
- `wrap()` already creates the AGENT/LLM/TOOL spans — do NOT also wrap a single `agent.run()` in `@span`/`trace`. Use `@span` only for YOUR surrounding orchestration functions.
- Never hardcode API keys — use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `import neatlogs` at module top level, never inside functions.
- Minimal edits — add wrap()/decorators + imports, don't reformat.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing wrapped agent path.
- Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run, with one wrapper-owned hierarchy and no duplicate agent/LLM/tool spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference

- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users (customer analytics) → `references/sessions-and-end-users.md`
