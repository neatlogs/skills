---
name: neatlogs-py-crewai
description: Use when adding neatlogs observability to a Python project that uses CrewAI (imports `crewai`, builds a Crew/Flow with agents and tasks).
metadata:
  author: neatlogs
  language: python
  framework: crewai
---

# Neatlogs Python Setup — CrewAI

This project uses CrewAI. Neatlogs instruments it with **`neatlogs.wrap(crew)`** — wrap the Crew (or Flow, or standalone Agent) instance once and the full span hierarchy is auto-traced.

## Core mechanism — `neatlogs.wrap(crew)`

`neatlogs.wrap()` detects the CrewAI Crew/Flow/Agent and patches every run entrypoint, the crew's agents and tasks, plus installs class-level hooks on the tool dispatch paths (`BaseTool.run` AND `CrewStructuredTool.invoke`) and `LLM.call`. Span tree:

```
WORKFLOW  crew.kickoff()
  ↳ AGENT   each agent's task execution
  ↳ TOOL    each tool call (BaseTool.run OR CrewStructuredTool.invoke)
  ↳ LLM     LLM.call (the underlying model request)
```

Covered entrypoints: `kickoff` / `kickoff_async` / `akickoff` / `kickoff_for_each` / `kickoff_for_each_async` / `akickoff_for_each`, plus `train` / `test` / `replay`. Flows: `flow.kickoff` / `kickoff_async` / `akickoff`.

**No provider pairing.** Older guidance paired `"crewai"` with a provider instrumentor (`"openai"`, `"anthropic"`, …) to get LLM spans. Neatlogs patches `LLM.call` directly, so LLM spans are captured regardless of the model backend — never match a provider key to the model string.

**`wrap()` vs `instrumentations=["crewai"]`.** Both install the SAME class-level hooks (`Crew.kickoff`, `Task`, `Agent`, `BaseTool.run`, `LLM.call`), so either one gives a bare crew a full tree. Prefer `wrap(crew)` — it additionally binds workflow metadata and is required for **Flows** and **standalone Agents**, which are routed per instance and NOT covered by the key alone. Passing the key is not an error.

`wrap()` also auto-suppresses CrewAI's own built-in telemetry (the no-I/O `Crew Created` / `Task Created` / `Flow Creation` lifecycle spans), so those don't pollute your traces.

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration; the crew spans nest under them.

## Standalone Agents (no Crew)

`wrap()` also handles a standalone agent run — `agent.kickoff(messages=...)` with no Crew. Wrap the agent before kicking it off:

```python
agent = neatlogs.wrap(Agent(role="...", goal="...", backstory="...", tools=[...]))
result = agent.kickoff(messages="What is 2+2?")
```

Emits an `AGENT` span (`crewai.agent.<role>`) capturing the `messages` input, with tool/LLM calls nested under it.

## Tools are auto-traced — do NOT add manual tool spans

`wrap()` traces tool calls on BOTH dispatch paths — `BaseTool.run` (for `BaseTool` subclasses) and `CrewStructuredTool.invoke` (for `@tool` function tools) — on every supported crewai version (0.130.x through 1.15.x). This is NOT version-dependent. Leave plain action tools undecorated: adding `@neatlogs.span` or a manual `trace(kind="TOOL")` inside a plain tool produces a DUPLICATE span. A tool body may contain a distinct custom operation the wrapper does not capture—for example, a `RETRIEVER` child for custom search or an `EMBEDDING` child for a custom embedder. Step 7 covers this.

## What you MUST do

1. `crew = neatlogs.wrap(crew)` on the Crew/Flow/Agent instance before its run entrypoint (`kickoff` / `train` / `agent.kickoff` / …).
2. (Recommended) Add `@neatlogs.span(kind="WORKFLOW")` on YOUR user-facing function that builds + kicks off the crew, so your orchestration code is the trace root and the crew nests under it.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Crew with neatlogs.wrap()** → `references/4-wrap-crew.md`
5. **Add a WORKFLOW span on your entry point** → `references/5-add-workflow.md`
6. **Tools — auto-traced; what NOT to add** → `references/7-verify-tools.md`
7. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any crewai / LLM library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Instrument via `wrap(crew)`, not `instrumentations=[...]` — it captures agents/tasks/tools/LLM AND binds workflow metadata, and it is the only path that covers Flows / standalone Agents. (`instrumentations=["crewai"]` is a valid key that installs the same class hooks; if a project already has it, leave it — just add the `wrap()`.)
- Wrap the Crew/Flow instance: `crew = neatlogs.wrap(crew)`. Returns the same instance.
- Never hardcode API keys in source. Use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- Add imports ONLY for what a file uses:
  - File calls `neatlogs.wrap(...)`/`neatlogs.span(...)`/`neatlogs.trace(...)` → add `import neatlogs`.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add wrap()/decorators + imports. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` to `@tool` functions, Agent definitions, or Task definitions — `wrap()` traces them.
- NEVER add a manual `with neatlogs.trace(kind="TOOL")` inside a plain tool body — `wrap()` already emits a TOOL span, so this DUPLICATES it. Add a child semantic span only for a distinct unsupported/custom operation (`RETRIEVER` for search, `EMBEDDING` for embedding), never as another record of the tool itself (Step 7).

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Show user-visible progress for install, edits, checks, restart, runtime verification, and platform confirmation; never print secrets.
- Run existing tests plus the project's build/package/type checks, restart the long-running process, and exercise the actual user-facing wrapped path.
- Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run, with one wrapper-owned hierarchy and no duplicate crew/task/agent/LLM/tool spans. Offline/no-export verification alone is insufficient. Otherwise report the exact blocker and leave the result incomplete.

## Reference

- Span kinds → `references/span-kinds.md`
- Sessions & end-users → `references/sessions-and-end-users.md`
