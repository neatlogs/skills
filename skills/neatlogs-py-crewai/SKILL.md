---
name: neatlogs-py-crewai
description: Use when adding neatlogs observability to a Python project that uses CrewAI (imports `crewai`, builds a Crew/Flow with agents and tasks).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "3.1"
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

**No `instrumentations=` and no provider pairing.** Older guidance paired `"crewai"` with a provider instrumentor (`"openai"`, `"anthropic"`, …) to get LLM spans. `wrap()` patches `LLM.call` directly, so it captures LLM spans regardless of the model backend — you do NOT pass `instrumentations=[...]` and do NOT need to match a provider to the model string.

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

`wrap()` traces tool calls on BOTH dispatch paths — `BaseTool.run` (for `BaseTool` subclasses) and `CrewStructuredTool.invoke` (for `@tool` function tools) — on every supported crewai version (0.130.x through 1.15.x). This is NOT version-dependent. Leave plain action tools undecorated: adding `@neatlogs.span` or a manual `trace(kind="TOOL")` inside a plain tool produces a DUPLICATE span. The only manual span is `trace(kind="RETRIEVER")` inside retrieval/embedding tools, to add `neatlogs.retrieval.*` attributes. Step 7 covers this.

## What you MUST do

1. `crew = neatlogs.wrap(crew)` on the Crew/Flow/Agent instance before its run entrypoint (`kickoff` / `train` / `agent.kickoff` / …).
2. (Recommended) Add `@neatlogs.span(kind="WORKFLOW")` on YOUR user-facing function that builds + kicks off the crew, so your orchestration code is the trace root and the crew nests under it.
3. (Optional, for prompt management) attach templates to agents/tasks → `references/6-prompt-templates.md`.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Crew with neatlogs.wrap()** → `references/4-wrap-crew.md`
5. **Add a WORKFLOW span on your entry point** → `references/5-add-workflow.md`
6. **Attach prompt templates (optional)** → `references/6-prompt-templates.md`
7. **Tools — auto-traced; what NOT to add** → `references/7-verify-tools.md`
8. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any crewai / LLM library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Do NOT pass `instrumentations=[...]` to `init()` for CrewAI — `wrap(crew)` captures agents/tasks/tools/LLM.
- Wrap the Crew/Flow instance: `crew = neatlogs.wrap(crew)`. Returns the same instance.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file uses:
  - File calls `neatlogs.wrap(...)`/`neatlogs.span(...)`/`neatlogs.trace(...)`/`neatlogs.bind_templates(...)`/`neatlogs.register_crewai_task(...)` → add `import neatlogs`.
  - File only defines template objects → add ONLY `from neatlogs import SystemPromptTemplate, UserPromptTemplate`. No bare `import neatlogs`.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add wrap()/decorators + imports. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` to `@tool` functions, Agent definitions, or Task definitions — `wrap()` traces them.
- NEVER add a manual `with neatlogs.trace(kind="TOOL")` inside a plain tool body — `wrap()` already emits a TOOL span, so this DUPLICATES it. The only in-tool span is `trace(kind="RETRIEVER")` for retrieval/embedding tools (Step 7).

## Reference

- Span kinds → `references/span-kinds.md`
- Sessions & end-users → `references/sessions-and-end-users.md`
