---
name: neatlogs-py-setup
description: >
  Step-by-step procedure for the Neatlogs wizard agent to instrument a Python project.
  Follow the numbered steps in order. Each step has a verification check.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "1.0"
  language: python
---

# Neatlogs Python Setup — Wizard Procedure

Follow these steps in exact order. Do not skip steps. Each step has a verification check — confirm it passes before moving to the next.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Identify and decorate orchestration functions** → `references/4-decorate-functions.md`
5. **Wrap LLM calls with trace()** → `references/5-wrap-llm-calls.md`
6. **Decorate tool functions** → `references/6-decorate-tools.md`
7. **Add flush/shutdown** → `references/7-flush-shutdown.md`

## Rules (apply to ALL steps)

- Import `neatlogs` at module top level, never inside functions.
- `neatlogs.init()` MUST execute BEFORE any LLM library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Never hardcode API keys in source. Use `os.getenv()` or let the SDK read from env automatically.
- `@neatlogs.span()` goes BELOW framework decorators (`@retry`, `@app.route`, `@tool`) — closest to `def`.
- Minimal edits only. Add decorators + imports. Do not reformat, add comments, or refactor.

## Reference (for decision-making during steps 4-6)

- Span kinds and when to use each → `references/span-kinds.md`
- What auto-instrumentation already covers → `references/auto-instrumented.md`
- LLM call patterns across all libraries → `references/llm-call-patterns.md`
