---
name: neatlogs-py-pydantic-ai
description: Use when adding neatlogs observability to a Python project that uses Pydantic AI (imports `pydantic_ai`, constructs an `Agent`).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
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
- `neatlogs.trace("name")` — group multiple operations / track prompt templates.
- `neatlogs.log("msg {x}", x=...)` — timestamped steps inside a span.

The wrapper's AGENT/LLM/TOOL spans nest correctly under whatever `@span`/`trace` is active.

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
- `import neatlogs` at module top level, never inside functions.
- Minimal edits — add wrap()/decorators + imports, don't reformat.

## Reference

- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users (customer analytics) → `references/sessions-and-end-users.md`
