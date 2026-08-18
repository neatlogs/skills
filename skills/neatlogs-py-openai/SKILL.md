---
name: neatlogs-py-openai
description: Use when adding neatlogs observability to a Python project that calls LLM provider SDKs directly (OpenAI, Anthropic, Google GenAI, Groq, etc.) and uses no agent framework.
metadata:
  author: neatlogs
  language: python
  framework: openai
---

# Neatlogs Python Setup — Direct LLM SDK (OpenAI / Anthropic / Google GenAI / …)

This project calls LLM APIs directly (e.g., `client.chat.completions.create()`). There is no agent framework managing tools or chains. Wrap supported clients once; decorate only the application's own orchestration and custom tools.

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
- `neatlogs.trace("name", kind="LLM", ...)` — create the canonical LLM span only for an unsupported/raw call that has no wrapper or instrumentor.
- `neatlogs.log("msg {x}", x=…)` — timestamped steps inside a span.

The captured LLM/EMBEDDING spans nest under your orchestration spans. Do not add a second manual LLM layer around them.

## Steps

1. **Install SDK** → `references/1-install-sdk.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap the LLM client(s)** → `references/4-wrap-client.md`
5. **Decorate orchestration functions** → `references/5-decorate-functions.md`
6. **Verify LLM calls have exactly one capture owner** → `references/6-wrap-llm-calls.md`
7. **Decorate tool functions** → `references/7-decorate-tools.md`
7.5. **Embeddings: wrapped/instrumented = automatic; custom = decorate** → `references/7.5-embeddings.md`
8. **Add flush/shutdown** → `references/8-flush-shutdown.md`

## Rules (apply to ALL steps)

- `neatlogs.init()` MUST execute BEFORE the LLM library is imported and BEFORE any client is constructed.
- If `load_dotenv()` exists, it MUST run BEFORE `neatlogs.init()`.
- Prefer `neatlogs.wrap(client)` for OpenAI/Anthropic/Google GenAI; use `init(instrumentations=[...])` only for providers `wrap()` doesn't support. Never both for the same client.
- Wrap EVERY supported LLM client whose calls you want traced: `client = neatlogs.wrap(client)`. Use the returned reference.
- Never hardcode API keys in source. Use `os.getenv()`.
- For managed Neatlogs, omit `endpoint` and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.
- Add imports ONLY for what a file actually uses:
  - File calls `neatlogs.wrap(...)` / `neatlogs.span(...)` / a manual raw-call `neatlogs.trace(...)` → add `import neatlogs`.
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

You may add WORKFLOW/CHAIN/AGENT spans around genuine multi-step orchestration. Do NOT add `neatlogs.trace(kind="LLM")` around any wrapped or instrumented provider call; the automatic span is canonical.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, edits, dependency/import checks, server restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing tests plus its build/package/type checks after editing. Restart the long-running process so startup instrumentation is actually loaded.
- Exercise the actual user-facing instrumented path. Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run, with one canonical span per operation and no duplicate LLM/tool/agent spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- Span kinds → `references/span-kinds.md`
- LLM call patterns → `references/llm-call-patterns.md`
- Sessions & end-users → `references/sessions-and-end-users.md`
