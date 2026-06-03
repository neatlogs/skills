---
name: neatlogs-py-crewai
description: Use when adding neatlogs observability to a Python project that uses CrewAI (imports `crewai`, builds a Crew/Flow with agents and tasks).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "3.0"
  language: python
  framework: crewai
---

# Neatlogs Python Setup — CrewAI

This project uses CrewAI. Neatlogs instruments it with **`neatlogs.wrap(crew)`** — wrap the Crew (or Flow) instance once and the full span hierarchy is auto-traced.

## Core mechanism — `neatlogs.wrap(crew)`

`neatlogs.wrap()` detects the CrewAI Crew/Flow and patches `kickoff` / `kickoff_async` / `kickoff_for_each`, the crew's agents and tasks, plus installs class-level hooks on `BaseTool.run` (TOOL) and `LLM.call` (LLM). Span tree:

```
WORKFLOW  crew.kickoff()
  ↳ AGENT   each agent's task execution
  ↳ TOOL    BaseTool.run (each tool call)
  ↳ LLM     LLM.call (the underlying model request)
```

**No `instrumentations=` and no provider pairing.** Older guidance paired `"crewai"` with a provider instrumentor (`"openai"`, `"anthropic"`, …) to get LLM spans. `wrap()` patches `LLM.call` directly, so it captures LLM spans regardless of the model backend — you do NOT pass `instrumentations=[...]` and do NOT need to match a provider to the model string.

Combine with `@neatlogs.span` / `neatlogs.trace` / `neatlogs.log` for your own orchestration; the crew spans nest under them.

## Tool spans are VERSION-DEPENDENT (still applies)

`wrap()` patches `BaseTool.run`, which covers tools dispatched through it. But on **`crewai >=1.14`** some native tool calls bypass `BaseTool.run` and those TOOL spans can still be lost — add `with neatlogs.trace(...)` INSIDE those tool bodies. Retrieval/embedding tools should ALWAYS get a `trace(kind="RETRIEVER")` inside the body (any version) to capture `neatlogs.retrieval.*` attributes. Step 7 walks through the version check and patterns.

## What you MUST do

1. `crew = neatlogs.wrap(crew)` on the Crew/Flow instance before `kickoff()`.
2. (Recommended) Add `@neatlogs.span(kind="WORKFLOW")` on YOUR user-facing function that builds + kicks off the crew, so your orchestration code is the trace root and the crew nests under it.
3. (Optional, for prompt management) attach templates to agents/tasks → `references/6-prompt-templates.md`.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the Crew with neatlogs.wrap()** → `references/4-wrap-crew.md`
5. **Add a WORKFLOW span on your entry point** → `references/5-add-workflow.md`
6. **Attach prompt templates (optional)** → `references/6-prompt-templates.md`
7. **Tools — version check + what to trace** → `references/7-verify-tools.md`
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

## Reference

- Span kinds → `references/span-kinds.md`
