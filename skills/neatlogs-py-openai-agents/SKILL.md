---
name: neatlogs-py-openai-agents
description: Use when adding neatlogs observability to a Python project that uses the OpenAI Agents SDK (imports `agents` / `openai-agents`, defines `Agent`s and calls `Runner.run`).
metadata:
  author: neatlogs
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
5. **Optionally add an app-owned WORKFLOW for real surrounding orchestration** → `references/5-add-workflow.md`
6. **Verify agents/tools/guardrails are untouched** → `references/7-verify-tools.md`
7. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any `agents` / openai imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Do NOT pass `instrumentations=["openai_agents"]` to `init()` — the trace processor is the instrumentation path. Listing it would double-fire spans.
- Register the processor ONCE with `add_trace_processor(neatlogs.openai_agents_processor())` at startup, before the first `Runner.run()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- Add imports ONLY for what a file uses: a file that calls `neatlogs.openai_agents_processor(...)` / `neatlogs.span(...)` needs `import neatlogs`; files that only define Agents/tools need NOTHING added.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add the processor registration and imports; add an outer decorator only when the app owns meaningful surrounding orchestration. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` / `@neatlogs.trace()` to:
  - `@function_tool` functions (traced as TOOL)
  - `Agent(...)` definitions or agent factory functions (traced as AGENT)
  - guardrail functions (`@input_guardrail`/`@output_guardrail` or `*_guardrail_fn`) (traced as GUARDRAIL)
  - handoff functions
- The processor owns the underlying LLM spans too. Do NOT wrap the Agents SDK's
  provider client or add a manual `trace(kind="LLM")` around `Runner` calls.
- The processor already creates the canonical `WORKFLOW` root for a standalone `Runner` trace. Add at most one app-owned `@span(kind="WORKFLOW")` on the user-facing `Runner.run()` caller only when that function has meaningful pre/post work or coordinates multiple runs; never add it merely to make a trace render.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.

For the representative run, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries. Scope it only to the launched process: do not edit source or persistent configuration, and do not treat the marker as a secret. Immediately before exercising the real path, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.

After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; do not make preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing `Runner` path.
- Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the marker-matched project trace is the fresh run, with one processor-owned hierarchy and no duplicate agent/LLM/tool/handoff/guardrail spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference

- Span kinds → `references/span-kinds.md`
- Sessions & end-users (group turns into conversations, tag your customers' end-users via `neatlogs.identify()`) → `references/sessions-and-end-users.md`
