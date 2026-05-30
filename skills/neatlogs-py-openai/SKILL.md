---
name: neatlogs-py-openai
description: >
  Instrument a Python project that uses LLM SDKs directly (OpenAI, Anthropic, Groq, etc.) — no agent framework.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "2.0"
  language: python
  framework: openai
---

# Neatlogs Python Setup — Direct LLM SDK (OpenAI/Anthropic/Groq)

This project calls LLM APIs directly (e.g., `client.chat.completions.create()`). There is no agent framework managing tools or chains. You are responsible for decorating orchestration functions and tool functions manually.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Decorate orchestration functions** → `references/4-decorate-functions.md`
5. **Wrap LLM calls with trace() + templates** → `references/5-wrap-llm-calls.md`
6. **Decorate tool functions** → `references/6-decorate-tools.md`
6.5. **Embeddings: decorate ONLY custom ones** → `references/6.5-embeddings.md`
7. **Add flush/shutdown** → `references/7-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE any LLM library imports.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file actually uses:
  - File calls `neatlogs.span(...)` or `neatlogs.trace(...)` → add `import neatlogs`.
  - File only defines `SystemPromptTemplate`/`UserPromptTemplate` objects → add ONLY `from neatlogs import SystemPromptTemplate, UserPromptTemplate`. Do NOT add a bare `import neatlogs` — it would be an unused import.
- When present, `import neatlogs` goes at module top level, never inside functions.
- `@neatlogs.span()` goes BELOW framework decorators (`@retry`, `@app.route`) — closest to `def`.
- Minimal edits only. Add decorators + imports. Do not reformat, add comments, or refactor.

## What auto-instrumentation covers (DO NOT manually trace these)

The `"openai"` / `"anthropic"` / etc. instrumentor automatically captures:
- `client.chat.completions.create()` → LLM span with model, tokens, latency
- `client.messages.create()` → LLM span
- `client.embeddings.create()` → EMBEDDING span (model, token count) — DO NOT manually decorate
- Streaming variants

You DO still need to add `@span` decorators on your functions and `with neatlogs.trace()` + templates around LLM calls for prompt management.

## Reference

- Span kinds → `references/span-kinds.md`
