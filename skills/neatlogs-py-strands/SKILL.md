---
name: neatlogs-py-strands
description: Use when adding neatlogs observability to a Python project that uses Strands Agents (imports `strands`, builds a Strands `Agent`).
metadata:
  author: neatlogs
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
- Strands native telemetry owns AGENT/LLM/TOOL spans and `strands_hooks()` only enriches them. Do NOT add manual LLM/tool decorators, provider wrappers, or spans around a single `agent(...)` call. Use manual spans only for meaningful surrounding orchestration.
- Strands ships `BedrockModel`; ensure AWS creds + region are set.
- Never hardcode keys/credentials. `import neatlogs` at module top level.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing Strands path.
- Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run, with one native/hooks-owned hierarchy and no duplicate agent/LLM/tool spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference
- Combining with @span/trace/log → `references/5-spans-trace-log.md`
- Span kinds reference → `references/span-kinds.md`
- Sessions & end-users → `references/sessions-and-end-users.md`
