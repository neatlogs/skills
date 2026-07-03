---
name: neatlogs-py-openai-agents
description: Use when adding neatlogs observability to a Python project that uses the OpenAI Agents SDK (imports `agents` / `openai-agents`, defines `Agent`s and calls `Runner.run`).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "3.0"
  language: python
  framework: openai-agents
---

# Neatlogs Python Setup — OpenAI Agents SDK

This project uses the OpenAI Agents SDK (`from agents import Agent, Runner, function_tool, handoff, ...`). Neatlogs instruments it with a **trace processor** — `neatlogs.openai_agents_processor()` registered via `add_trace_processor()`. This is the first-class OpenAI Agents path (the SDK's own tracing-processor protocol).

## Core mechanism — `add_trace_processor(neatlogs.openai_agents_processor())`

The OpenAI Agents SDK emits its own trace/span events. Registering the neatlogs processor maps them to neatlogs spans:

```
WORKFLOW   trace
  ↳ AGENT       agent span (instructions = prompt)
  ↳ LLM         generation / response span
  ↳ TOOL        @function_tool span
  ↳ AGENT       handoff span
  ↳ GUARDRAIL   guardrail span
```

```python
import neatlogs
from agents import add_trace_processor

add_trace_processor(neatlogs.openai_agents_processor())   # register once, before Runner.run()
```

Register the processor ONCE at startup, after `init()` and after importing `agents`. Everything the SDK runs afterward is traced — agents, tools, handoffs, guardrails, and LLM calls — with nothing to wire up per-agent.

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration; the SDK spans nest under your manual spans.

## What the processor captures (DO NOT manually decorate)

- `Runner.run()` / `Runner.run_sync()` / `Runner.run_streamed()` → the agent run
- Each `Agent` turn (instructions as the system prompt) → AGENT span
- ALL `@function_tool` functions → TOOL span
- Handoffs between agents → AGENT span
- Input/output guardrails → GUARDRAIL span
- Underlying LLM calls → LLM span (model, tokens, prompt)

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Register the trace processor** → `references/4-register-processor.md`
5. **Add a WORKFLOW span on your entry point** → `references/5-add-workflow.md`
6. **Verify agents/tools/guardrails are untouched** → `references/7-verify-tools.md`
7. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any `agents` / openai imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Do NOT pass `instrumentations=["openai_agents"]` to `init()` — the trace processor is the instrumentation path. Listing it would double-fire spans.
- Register the processor ONCE with `add_trace_processor(neatlogs.openai_agents_processor())` at startup, before the first `Runner.run()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file uses: a file that calls `neatlogs.openai_agents_processor(...)` / `neatlogs.span(...)` needs `import neatlogs`; files that only define Agents/tools need NOTHING added.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add the processor registration + the one decorator + imports. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` / `@neatlogs.trace()` to:
  - `@function_tool` functions (traced as TOOL)
  - `Agent(...)` definitions or agent factory functions (traced as AGENT)
  - guardrail functions (`@input_guardrail`/`@output_guardrail` or `*_guardrail_fn`) (traced as GUARDRAIL)
  - handoff functions
- The ONLY `@span(kind="WORKFLOW")` you add is on the `Runner.run()` caller.

## Reference

- Span kinds → `references/span-kinds.md`
- Sessions & end-users (group turns into conversations, tag your customers' end-users via `neatlogs.identify()`) → `references/sessions-and-end-users.md`
