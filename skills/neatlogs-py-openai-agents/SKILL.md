---
name: neatlogs-py-openai-agents
description: Instrument a Python project built on the OpenAI Agents SDK (the `agents` package) with the "openai_agents" auto-instrumentor.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "2.0"
  language: python
  framework: openai-agents
---

# Neatlogs Python Setup — OpenAI Agents SDK

This project uses the OpenAI Agents SDK (`from agents import Agent, Runner, function_tool, handoff, ...`). The `"openai_agents"` auto-instrumentor handles almost all tracing automatically. Your job is minimal: add ONE `@neatlogs.span(kind="WORKFLOW")` on the function that calls `Runner.run()` / `Runner.run_sync()`.

## What the "openai_agents" instrumentor auto-traces (DO NOT manually decorate)

- `Runner.run()` / `Runner.run_sync()` / `Runner.run_streamed()` → the agent run
- Each `Agent` turn (with its `instructions` as the system prompt) → AGENT spans
- ALL `@function_tool` functions → TOOL spans
- Handoffs between agents → spans
- Input/output guardrails → GUARDRAIL spans
- The underlying LLM calls → LLM spans (model, tokens, the agent's instructions/prompt)

The agent's `instructions`, tool definitions, handoffs, and guardrails are all captured by the instrumentor from the declarative `Agent(...)` definitions — there is nothing to wire up manually for prompts.

## What you MUST do manually

1. Add `@neatlogs.span(kind="WORKFLOW")` on the user-facing function that calls `Runner.run()` (e.g. `main()`, a CLI command, or a route handler).
2. Ensure the provider instrumentor is paired (the SDK runs on OpenAI under the hood) — the wizard adds `["openai_agents", "openai"]` by default.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Add WORKFLOW span** → `references/4-add-workflow.md`
5. **Verify agents/tools/guardrails are untouched** → `references/6-verify-tools.md`
6. **Add flush/shutdown** → `references/7-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any `agents` / openai imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file uses: a file that calls `neatlogs.span(...)` needs `import neatlogs`; files that only define Agents/tools need NOTHING added.
- `@neatlogs.span()` goes BELOW framework decorators, closest to `def`.
- Minimal edits only. Add the one decorator + import. Do not reformat or refactor.
- NEVER add `@neatlogs.span()` / `@neatlogs.trace()` to:
  - `@function_tool` functions (auto-traced as TOOL)
  - `Agent(...)` definitions or agent factory functions (auto-traced as AGENT)
  - guardrail functions (`@input_guardrail`/`@output_guardrail` or `*_guardrail_fn`) (auto-traced as GUARDRAIL)
  - handoff functions
- The ONLY `@span(kind="WORKFLOW")` you add is on the `Runner.run()` caller.

## Reference

- Span kinds → `references/span-kinds.md`
