---
name: neatlogs-py-strands
description: Use when adding neatlogs observability to a Python project that uses Strands Agents (imports `strands`, builds a Strands `Agent`).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
  language: python
  framework: strands
---

# Neatlogs Python Setup — Strands Agents

This project uses **Strands Agents** (`strands.Agent`). Strands **self-instruments** via native OpenTelemetry, and `neatlogs.strands_hooks(agent)` enriches those native spans with input/output so they render fully.

## Core mechanism — init() + strands_hooks(agent)

1. `neatlogs.init()` registers the global tracer provider, so Strands' own OTel spans (invoke_agent, execute_tool, model `chat` calls) flow into neatlogs and the attribute mapper classifies them as AGENT / TOOL / LLM (with token usage).
2. **`neatlogs.strands_hooks(agent)` is REQUIRED** to capture prompt/response **content**. Strands records I/O as OTel span *events* (`gen_ai.user.message`, `gen_ai.choice`, …), which neatlogs doesn't render from events. `strands_hooks()` installs a hook on Strands' telemetry that copies that content onto the span as `input.value`/`output.value` — so LLM/TOOL spans show their actual input/output, not just tokens. Without it you get spans + tokens but **empty I/O**.

```python
import neatlogs
neatlogs.init(api_key=os.getenv("NEATLOGS_API_KEY"), workflow_name="my-app")

from strands import Agent
agent = neatlogs.strands_hooks(Agent(model=model, tools=[...]))   # enables I/O capture
agent("Hello")
```

`strands_hooks()` does NOT create its own spans (Strands' native tracing stays the source of truth) and is idempotent — the hook installs once globally. Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration — the native Strands spans nest under your manual spans.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the agent with strands_hooks() + run it** → `references/4-run-agent.md`
5. **Add @span / trace / log to orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST run BEFORE importing `strands` so the tracer provider is registered before Strands reads it. `load_dotenv()` runs before `init()`.
- Do NOT add `instrumentations=[...]` for Strands — init() + Strands' native OTel is the capture path.
- Wrap EVERY agent with `agent = neatlogs.strands_hooks(agent)` — REQUIRED for input/output content (not just tokens). It installs the I/O hook once (idempotent) and returns the same agent; it does NOT create extra spans.
- Strands ships `BedrockModel`; ensure AWS creds + region are set.
- Never hardcode keys/credentials. `import neatlogs` at module top level.

## Reference
- Combining with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
