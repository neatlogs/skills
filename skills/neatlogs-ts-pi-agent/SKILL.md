---
name: neatlogs-ts-pi-agent
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses maintained `@earendil-works/pi-agent-core` / `@earendil-works/pi-ai` or legacy `@mariozechner` Pi packages, including `Agent`, `AgentHarness`, functional loops, and standalone stream functions.
metadata:
  author: neatlogs
  language: typescript
  framework: pi-agent
---

# Neatlogs TypeScript Setup — Pi Agent

This project uses **Pi Agent** (maintained as `@earendil-works/pi-agent-core`). Neatlogs instruments it with **`piAgentHooks()` from `neatlogs/pi-agent`**. The wrapper also supports legacy `@mariozechner` releases through the same event interface.

## Core mechanism — `piAgentHooks(agent)`

`Agent` exposes `subscribe(listener)` and emits lifecycle events (`agent_*`, `turn_*`, `message_*`, `tool_execution_*`). Neatlogs translates them into spans. For maintained `AgentHarness`, it additionally wraps model-producing `compact()` and summarizing `navigateTree()` operations because those calls occur outside the Agent event loop. There is no import-order rule.

One `agent.prompt()` = **one trace**:

```
AGENT  pi_agent.run                  (agent_start → agent_end)
 ├─ CHAIN pi_agent.turn.1            (turn_start → turn_end)
 │   ├─ LLM  pi_agent.llm.<model>    (message_start → message_end = real provider latency)
 │   └─ TOOL pi_agent.tool.<name>    (tool_execution_start → tool_execution_end)
 └─ CHAIN pi_agent.turn.2            (the post-tool-result turn)
     └─ LLM  pi_agent.llm.<model>
```

| Span | Carries |
|------|---------|
| **AGENT** | run input (first user message), final output, `neatlogs.agent.stop_reason` + `neatlogs.error.message` on an aborted/errored run |
| **CHAIN** | `neatlogs.chain.turn_index`, the message that prompted the turn, the turn's assistant text (or the tool calls it made), `neatlogs.chain.tool_result_count` |
| **LLM** | model / `response_model` / provider / api, input messages, output + `tool_calls.*`, token counts (incl. cache read/write), **exact `cost_usd` from pi-ai's own pricing**, `metrics.ttft_ms`, `is_streaming`, `stop_reason` |
| **TOOL** | tool name, `call_id`, input args, result, `is_error`, `is_streaming` for tools that emit partial updates |

## Steps

1. [Install and check the Pi version](references/1-install.md)
2. [Add `init()` and `piAgentHooks()`](references/2-init-and-wrap.md)
3. [Set environment variables](references/3-set-env.md)
4. [Verify every Agent or harness](references/4-verify.md)
5. [Handle lifecycle and flushing](references/5-lifecycle.md)

## Rules (apply to ALL steps)

- `piAgentHooks` patches the **instance** you pass (it subscribes to it), NOT the module — so **plain static imports are fine**. There is no "init before import" rule for Pi Agent, unlike provider-SDK wrappers.
- USE the wrapped reference. `piAgentHooks` subscribes in place AND returns the agent, so `const agent = piAgentHooks(new Agent({...}))` then call `agent.prompt(...)`.
- Call it on **every** `Agent` instance you want traced. Wrapping is **idempotent** — calling it twice on the same instance is a no-op, so it never double-traces.
- NEVER pass `instrumentations: [...]`. `piAgentHooks` is the sole capture point for Pi-routed model calls; `init()` rejects provider keys.
- Pi calls the model through its `pi-ai` package, not a bare provider SDK, so do **not** also wrap the provider (`wrapOpenAI`, `wrapAnthropic`, …) for Pi-routed calls. Only wrap a provider client the app calls **directly** outside Pi.
- Cost is **not** re-derived from tokens: pi-ai prices each call against its own model registry and neatlogs carries that exact figure through as `neatlogs.llm.cost_usd`.
- Do NOT manually wrap `agent.prompt()` in `span()`/`trace()` on top of `piAgentHooks` — that double-traces. Nesting a wrapped agent INSIDE your own `span()` is fine and correct: the AGENT span parents to it.
- All lifecycle calls are async: `await init()`, `await flush()`, `await shutdown()`.
- Never hardcode API keys — use `process.env`.

## Reference

- [Low-level functional API](references/low-level-api.md) — required for functional loops and standalone stream functions.
- [Full span coverage matrix](references/span-coverage.md) — Agent, AgentHarness, streaming, tools, abort, and state-only methods.
- [Sessions and end-users](references/sessions-and-end-users.md)
- [Custom spans for non-Pi code](references/decorators-and-traces.md)
