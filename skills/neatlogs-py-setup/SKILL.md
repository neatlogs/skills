---
name: neatlogs-py-setup
description: Use when adding neatlogs observability to a Python LLM/agent project and no framework-specific neatlogs skill matches the stack — i.e. the generic fallback for instrumenting Python apps that call LLMs or run agents.
metadata:
  author: neatlogs
  language: python
---

# Neatlogs Python Setup — Wizard Procedure (generic fallback)

Follow these steps in exact order. Do not skip steps. Each step has a verification check — confirm it passes before moving to the next.

## Prefer a framework-specific skill when one applies

This is the GENERIC procedure. If the project uses a known framework/SDK, use its dedicated skill instead — those teach the exact instrumentation entry point:

| Stack | Skill | Entry point |
|---|---|---|
| Direct OpenAI / Anthropic / Google GenAI | `neatlogs-py-openai` | `neatlogs.wrap(client)` |
| CrewAI | `neatlogs-py-crewai` | `neatlogs.wrap(crew)` |
| Pydantic AI | `neatlogs-py-pydantic-ai` | `neatlogs.wrap(agent)` |
| DSPy | `neatlogs-py-dspy` | `neatlogs.wrap(module)` |
| Agno | `neatlogs-py-agno` | `neatlogs.wrap(agent)` |
| Google ADK | `neatlogs-py-google-adk` | `neatlogs.wrap(runner)` |
| Strands | `neatlogs-py-strands` | native (init only) |
| LangChain / LangGraph | `neatlogs-py-langchain` | `neatlogs.langchain_handler()` |
| OpenAI Agents SDK | `neatlogs-py-openai-agents` | `neatlogs.openai_agents_processor()` |

## Instrumentation model (read first)

Neatlogs instruments LLM/agent calls by **wrapping the client/agent** — not by a global `instrumentations=[...]` list:

- **`neatlogs.wrap(x)`** — auto-detects and patches OpenAI/Anthropic/Google-GenAI clients, CrewAI Crew, Pydantic AI Agent, DSPy module, Agno agent, Google ADK runner. One call per instance. Extra keyword args are stamped on the root WORKFLOW span as `neatlogs.workflow.<key>` (searchable metadata), e.g. `neatlogs.wrap(OpenAI(), route="/api/chat", surface="copilot")` — but session/end-user identity goes through `identify()`, not `wrap()` kwargs.
- **`neatlogs.langchain_handler()`** — LangChain callback handler, passed via `config={"callbacks": [handler]}`.
- **`neatlogs.openai_agents_processor()`** — OpenAI Agents SDK trace processor, registered via `add_trace_processor(...)`.
- **Strands** — self-instruments via native OTel; `init()` alone captures it.
- **`instrumentations=[...]`** — only for providers `wrap()` doesn't cover (Groq, Cohere, Bedrock, Mistral, Together, LiteLLM).

Layer `@neatlogs.span` / `neatlogs.log` only on your own orchestration and custom operations. Never add a manual LLM span on top of a wrapper, callback handler, hook, processor, native framework telemetry, or provider instrumentor.

## Steps

0. **Understand the agentic system first** (read-only; do this before any edits) → `references/understand-first.md`
1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Identify and decorate orchestration functions** → `references/4-decorate-functions.md`
5. **Verify exactly one capture owner per LLM call** → `references/5-wrap-llm-calls.md`
6. **Decorate tool functions** → `references/6-decorate-tools.md`
7. **Add flush/shutdown** → `references/7-flush-shutdown.md`

## Rules (apply to ALL steps)

- Import `neatlogs` at module top level, never inside functions.
- `neatlogs.init()` MUST execute BEFORE any LLM library imports and BEFORE the client/agent is constructed/wrapped.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- `@neatlogs.span()` goes BELOW framework decorators (`@retry`, `@app.route`, `@tool`) — closest to `def`.
- Minimal edits only. Add wrap()/handler/decorators + imports. Do not reformat, add comments, or refactor.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.

For the representative run, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries. Scope it only to the launched process: do not edit source or persistent configuration, and do not treat the marker as a secret. Immediately before exercising the real path, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.

After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; do not make preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, edits, dependency/import checks, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing tests plus its build/package/type checks after editing. Restart the long-running process so startup instrumentation is actually loaded.
- Exercise the actual user-facing instrumented path. Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the marker-matched project trace is the fresh run, with one canonical span per operation and no duplicates. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference (for decision-making during steps 4-6)

- Build the component inventory BEFORE instrumenting → `references/understand-first.md`
- Sessions & end-users (group multi-turn conversations, per-customer analytics) → `references/sessions-and-end-users.md`
- Span kinds and when to use each → `references/span-kinds.md`
- What the wrapper/handler/processor already covers → `references/auto-instrumented.md`
- LLM call patterns across all libraries → `references/llm-call-patterns.md`
- Raw HTTP LLM calls (httpx/requests — wrap() is BLIND, needs manual spans):
  - Per-provider request/response field paths → `references/raw-http-llm-formats.md`
  - Streaming manual-span lifecycle → `references/raw-http-streaming-span.md`
