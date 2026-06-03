---
name: neatlogs-py-openai
description: Use when adding neatlogs observability to a Python project that calls LLM provider SDKs directly (OpenAI, Anthropic, Google GenAI, Groq, etc.) and uses no agent framework.
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "3.0"
  language: python
  framework: openai
---

# Neatlogs Python Setup — Direct LLM SDK (OpenAI / Anthropic / Google GenAI / …)

This project calls LLM APIs directly (e.g., `client.chat.completions.create()`). There is no agent framework managing tools or chains. You decorate your own orchestration and tool functions manually.

## Instrumentation — pick the path that matches the provider

There are two equivalent ways to capture LLM/embedding calls. **Prefer `neatlogs.wrap()`** — it is per-instance, explicit, and needs no global config.

### Path A (PREFERRED) — `neatlogs.wrap(client)` for OpenAI / Anthropic / Google GenAI

`neatlogs.wrap()` detects the client type and patches its LLM-relevant resources in place, returning the same instance:

```python
import neatlogs
from openai import OpenAI

client = neatlogs.wrap(OpenAI())        # chat, responses, embeddings, images, audio … all traced
client.chat.completions.create(...)     # → LLM span (model, tokens, latency)
client.embeddings.create(...)           # → EMBEDDING span
```

Supported by `wrap()`: `OpenAI` / `AsyncOpenAI`, `Anthropic` / `AsyncAnthropic`, `google.genai.Client`. Same call for all three — it auto-routes by type. When you use `wrap()`, do NOT pass `instrumentations=` for that provider.

### Path B (fallback) — `instrumentations=[...]` for providers `wrap()` doesn't cover

`wrap()` does NOT support Groq, Cohere, Bedrock, Mistral, Together, LiteLLM, etc. For those, pass the provider name to `init(instrumentations=[...])` (the global auto-instrumentor):

| Provider SDK | Path |
|---|---|
| OpenAI / Anthropic / Google GenAI | `neatlogs.wrap(client)` (Path A) |
| Groq | `init(instrumentations=["groq"])` |
| Cohere | `init(instrumentations=["cohere"])` |
| Bedrock | `init(instrumentations=["bedrock"])` |
| Mistral | `init(instrumentations=["mistralai"])` |
| Together | `init(instrumentations=["together"])` |
| LiteLLM | `init(instrumentations=["litellm"])` |

Mixing is fine: e.g. wrap an OpenAI client AND `init(instrumentations=["groq"])` if the app uses both. Never list a provider in `instrumentations=[]` AND `wrap()` the same client — that double-fires and produces duplicate spans.

## Combine with manual primitives

- `@neatlogs.span(kind="WORKFLOW"|"CHAIN"|"TOOL"|...)` — decorate orchestration / tool functions.
- `neatlogs.trace("name", kind="LLM", system_prompt_template=…, user_prompt_template=…)` — group a call + capture prompt-template structure for the dashboard.
- `neatlogs.log("msg {x}", x=…)` — timestamped steps inside a span.

The captured LLM/EMBEDDING spans nest under whatever `@span`/`trace` is active.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the LLM client(s)** → `references/4-wrap-client.md`
5. **Decorate orchestration functions** → `references/5-decorate-functions.md`
6. **Attach trace() + prompt templates around LLM calls** → `references/6-wrap-llm-calls.md`
7. **Decorate tool functions** → `references/7-decorate-tools.md`
7.5. **Embeddings: wrapped/instrumented = automatic; custom = decorate** → `references/7.5-embeddings.md`
8. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE the LLM library is imported and BEFORE any client is constructed.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Prefer `neatlogs.wrap(client)` for OpenAI/Anthropic/Google GenAI; use `init(instrumentations=[...])` only for providers `wrap()` doesn't support. Never both for the same client.
- Wrap EVERY supported LLM client whose calls you want traced: `client = neatlogs.wrap(client)`. Use the returned reference.
- Never hardcode API keys in source. Use `os.getenv()`.
- Add imports ONLY for what a file actually uses:
  - File calls `neatlogs.wrap(...)` / `neatlogs.span(...)` / `neatlogs.trace(...)` → add `import neatlogs`.
  - File only defines `SystemPromptTemplate`/`UserPromptTemplate` objects → add ONLY `from neatlogs import SystemPromptTemplate, UserPromptTemplate`. Do NOT add a bare `import neatlogs` — it would be unused.
- When present, `import neatlogs` goes at module top level, never inside functions.
- `@neatlogs.span()` goes BELOW framework decorators (`@retry`, `@app.route`) — closest to `def`.
- Minimal edits only. Add wrap()/decorators + imports. Do not reformat, add comments, or refactor.

## What's auto-captured (DO NOT also manually trace)

Once a client is `wrap()`'d (or its provider is in `instrumentations=[]`), these are auto-captured — do not add a TOOL/EMBEDDING span around them:
- `client.chat.completions.create()` / `client.responses.create()` → LLM span (model, tokens, latency, finish reason)
- `client.messages.create()` (Anthropic) → LLM span
- `client.models.generate_content()` (Google GenAI) → LLM span
- `client.embeddings.create()` → EMBEDDING span
- Streaming variants

You DO still add `@span` on your own functions and `neatlogs.trace()` + templates around LLM calls for prompt management.

## Reference

- Span kinds → `references/span-kinds.md`
- LLM call patterns → `references/llm-call-patterns.md`
