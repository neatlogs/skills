---
name: neatlogs-py-agno
description: Use when adding neatlogs observability to a Python project that uses the Agno agent framework (imports `agno`, constructs Agno `Agent`s).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
  language: python
  framework: agno
---

# Neatlogs Python Setup — Agno

This project uses **Agno** (`agno.agent.Agent`, `Team`, `Workflow`). Neatlogs instruments it with **`neatlogs.wrap(agent)`**.

## Core mechanism — `neatlogs.wrap(entity)`

`neatlogs.wrap()` patches `run`/`arun` (incl. streaming) on the Agent/Team/Workflow and installs class-level model (LLM) + tool (TOOL) hooks. Span tree:

```
AGENT / TEAM / WORKFLOW  (run / arun, incl. streaming)
  ↳ LLM   (model invocation)
  ↳ TOOL  (each tool call)
```

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Agent with neatlogs.wrap()** → `references/4-wrap-agent.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `agno` (class-level model/tool hooks patch at import time). `load_dotenv()` runs before `init()`.
- Wrap each Agent/Team/Workflow you want traced: `agent = neatlogs.wrap(agent)`. Returns the same instance.
- `wrap()` creates the AGENT/LLM/TOOL spans — do NOT also wrap a single `agent.run()` in `@span`/`trace`. Use `@span` for YOUR orchestration only.
- Never hardcode API keys — use `os.getenv()`.
- `import neatlogs` at module top level.

## Reference
- Combining wrap() with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
