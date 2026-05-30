---
name: neatlogs-py-crewai
description: Instrument a Python project built on CrewAI with the "crewai" auto-instrumentor.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "2.0"
  language: python
  framework: crewai
---

# Neatlogs Python Setup — CrewAI

This project uses CrewAI. The `"crewai"` auto-instrumentor handles most tracing automatically. Your job is minimal: add ONE `@neatlogs.span(kind="WORKFLOW")` on the function that calls `crew.kickoff()`, make sure the right provider instrumentor is paired with `"crewai"`, and (optionally) attach prompt templates to agents/tasks.

## What the "crewai" instrumentor auto-traces (DO NOT manually decorate)

- `crew.kickoff()` / `crew.kickoff_async()` → CrewAI execution spans
- Each Agent's task execution → AGENT spans
- LLM calls dispatched internally (via LiteLLM) → LLM spans — **only if the provider instrumentor is also enabled** (see below)

## Tool spans are VERSION-DEPENDENT (important)

Auto tool-tracing only works on **`crewai >=1.9.3, <1.14`** (the range neatlogs' own examples pin). On **`crewai >=1.14`** native tool calls bypass the instrumentor's hook and TOOL spans are silently lost — you must add `with neatlogs.trace(...)` INSIDE tool bodies. Also, retrieval/embedding tools should ALWAYS get a `trace(kind="RETRIEVER")` inside the body (on any version) to capture `neatlogs.retrieval.*` attributes. Step 6 walks through the version check and exact patterns.

## The provider instrumentor is REQUIRED for LLM spans

CrewAI dispatches LLM calls internally through LiteLLM. The `"crewai"` instrumentor traces agents/tasks/tools but NOT the underlying LLM call — that is captured by the **provider** instrumentor, matched to whatever `crewai.LLM(model=...)` (or the agent's `llm=` / `MODEL`) points at:

| `model=` value | instrumentations |
|---|---|
| `"gpt-4o"`, `"gpt-4o-mini"` (OpenAI proper) | `["crewai", "openai"]` |
| `"azure/..."` | `["crewai", "azure_ai_inference"]` |
| `"gemini/..."` | `["crewai", "google_genai"]` |
| `"claude-..."` | `["crewai", "anthropic"]` |

If you omit the provider key, the LLM call succeeds but produces NO `LLM`-kind span — the trace shows only the Agent parent with no LLM child. The wizard defaults CrewAI to `["crewai", "openai"]` (CrewAI's default backend); **verify the model string and swap the provider if it isn't OpenAI.**

> Do NOT add `"litellm"` alongside a direct provider key — they double-fire and produce duplicate LLM spans.

## What you MUST do manually

1. Add `@neatlogs.span(kind="WORKFLOW")` on the user-facing function that calls `crew.kickoff()`.
2. Confirm `instrumentations=["crewai", "<provider>"]` matches the actual LLM backend.
3. (Optional, for prompt management) attach templates to agents/tasks → `references/5-prompt-templates.md`.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Add WORKFLOW span** → `references/4-add-workflow.md`
5. **Attach prompt templates (optional)** → `references/5-prompt-templates.md`
6. **Verify tools/agents are untouched** → `references/6-verify-tools.md`
7. **Add flush/shutdown** → `references/7-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any crewai / LLM library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file uses:
  - File calls `neatlogs.span(...)`/`neatlogs.trace(...)`/`neatlogs.bind_templates(...)`/`neatlogs.register_crewai_task(...)` → add `import neatlogs`.
  - File only defines template objects → add ONLY `from neatlogs import SystemPromptTemplate, UserPromptTemplate`. No bare `import neatlogs`.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add decorators + imports. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` to `@tool` functions, Agent definitions, or Task definitions — the instrumentor traces them.
- The ONLY `@span(kind="WORKFLOW")` you add is on the `crew.kickoff()` caller.

## Reference

- Span kinds → `references/span-kinds.md`
