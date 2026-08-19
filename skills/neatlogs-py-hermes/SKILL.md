---
name: neatlogs-py-hermes
description: Use when adding neatlogs observability to a Python project that uses the Hermes agent (NousResearch/hermes-agent) as a LIBRARY — i.e. it imports `run_agent` / constructs `AIAgent(...)` in its own code.
metadata:
  author: neatlogs
  language: python
  framework: hermes
---

# Neatlogs Python Setup — Hermes (library mode)

This project uses **Hermes** (`from run_agent import AIAgent`) as a library in its
own Python code. Neatlogs instruments it with the **`hermes` instrumentation**
(plus `openai`), enabled in `neatlogs.init(...)`.

> **Are they running the standalone `hermes` CLI instead of writing Python?**
> Then this skill does NOT apply — there's no source to add `init()` to. Use the
> **observer plugin** instead: `pip install neatlogs` and `hermes plugins enable
> neatlogs` (it traces the CLI/gateway with zero code). This skill is only for
> code that imports `run_agent`/`AIAgent`.

## Core mechanism — `neatlogs.init(instrumentations=["hermes"])`

The `hermes` instrumentor patches `AIAgent.run_conversation` (an **AGENT** span)
and `ToolRegistry.dispatch` (a **TOOL** span per tool call). Hermes' LLM calls go
through the `openai` SDK (pointed at OpenRouter) — and `"hermes"` **auto-loads
`openai`** for the **LLM** spans, so you only list `"hermes"`. Span tree:

```
AGENT  hermes.run_conversation   (one agentic run)
  ↳ LLM   chat.completions.create  (via openai → OpenRouter)
  ↳ TOOL  hermes.tool.<name>       (each tool dispatch)
```

`wrap()` is an optional equivalent (`agent = neatlogs.wrap(AIAgent(...))`) — it's
the same class-level patch, so prefer the `instrumentations=[...]` form.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() BEFORE importing run_agent** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Run the agent (no per-call changes needed)** → `references/4-run-agent.md`
5. **Add @span / trace / log to your orchestration** → `references/5-spans-trace-log.md`
6. **Lifecycle (flush/shutdown)** → `references/6-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init(instrumentations=["hermes"])` MUST run BEFORE
  `from run_agent import AIAgent` — the instrumentor patches the class at import
  time, so a later init misses it. `load_dotenv()` runs before `init()`.
  (`"hermes"` auto-loads `openai` for the LLM spans — no need to add it yourself.)
- Hermes isn't on PyPI — it's git-installed (see step 1).
- Hermes routes LLM calls through OpenRouter by default; if you use a non-OpenAI
  provider adapter (anthropic / bedrock / gemini), add that provider to the
  instrumentations list too (e.g. `["hermes", "anthropic"]`).
- The Hermes instrumentor and its selected provider instrumentor own the AGENT,
  TOOL, and LLM spans. Do NOT add manual LLM/tool decorators or wrap the same
  provider client again. Manual spans are only for app-owned surrounding
  orchestration or unsupported calls outside Hermes.
- Never hardcode API keys — use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `import neatlogs` at module top level.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.

For the representative run, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries. Scope it only to the launched process: do not edit source or persistent configuration, and do not treat the marker as a secret. Immediately before exercising the real path, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.

After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; do not make preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing instrumented agent path.
- Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the marker-matched project trace is the fresh run, with one instrumentor-owned hierarchy and no duplicate agent/LLM/tool spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference
- Combining the instrumentation with @span/trace/log → `references/5-spans-trace-log.md`
- Sessions & end-users (group a conversation's runs, attribute to a customer) → `references/sessions-and-end-users.md`
- Span kinds reference → `references/span-kinds.md`
