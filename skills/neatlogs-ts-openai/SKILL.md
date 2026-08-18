---
name: neatlogs-ts-openai
description: Use when adding neatlogs observability to a TypeScript/Node.js project that calls LLM provider SDKs directly (OpenAI, Anthropic, Google GenAI, Bedrock) and uses no agent framework.
metadata:
  author: neatlogs
  language: typescript
  framework: openai
---

# Neatlogs TypeScript Setup — Direct LLM SDK (OpenAI / Anthropic / Google / Bedrock)

This project calls an LLM provider SDK directly (no agent framework). Neatlogs instruments supported providers with an **explicit `wrap*` helper applied to the client instance**. The wrapper is the sole owner of each provider LLM span. Add `span()` only around your own multi-step orchestration; use a manual `trace({ kind: 'LLM' })` only for an unsupported/raw LLM call that has no wrapper, handler, hook, processor, or instrumentor.

> **`init({ instrumentations: [...] })` throws.** Every provider key is rejected — the underlying instrumentors drive the **global** OpenTelemetry context, which Neatlogs' private provider cannot isolate from a co-tenant tracer (Datadog, etc.). The thrown error names the helper to use instead. Older guidance offered the key as a zero-touch path — that is gone.

## Core mechanism

1. `await init({ apiKey })` once at startup — with NO `instrumentations` key.
2. Wrap each provider client at its construction site: `const client = wrapOpenAI(new OpenAI())`.
3. Call the wrapped client normally. Optionally use `span({ kind: 'WORKFLOW' }, fn)` to group a multi-step user-facing feature. Do **not** add `trace({ kind:'LLM' })` around wrapped calls.

## Provider → helper

| SDK | Helper | Import from |
|---|---|---|
| OpenAI | `wrapOpenAI(new OpenAI())` | `neatlogs/openai` |
| Azure OpenAI | `wrapAzureOpenAI(client)` | `neatlogs/azure-openai` |
| Anthropic | `wrapAnthropic(new Anthropic())` | `neatlogs/anthropic` |
| Google GenAI (Gemini / AI Studio) | `wrapGoogleGenAI(new GoogleGenAI({ apiKey }))` | `neatlogs/google-genai` |
| Google GenAI (Vertex mode) | `wrapVertexAI(client)` | `neatlogs/vertex-ai` |
| AWS Bedrock | `wrapBedrock(new BedrockRuntimeClient({}))` | `neatlogs/bedrock` |

All of these are also re-exported from the root `neatlogs` entry. Wrap once, at construction, and use the returned client everywhere — then call it exactly as normal (`gc.models.generateContent(...)`, `client.chat.completions.create(...)`). Because the helpers patch the **instance** and not the module, there is **no import-order rule**: plain static imports are correct and dynamic `import()` buys nothing.

A provider with no helper (Cohere, Groq, Mistral, Ollama, Together, raw `fetch`) is **not** traced — instrument those calls with a manual `trace({ kind: 'LLM' })` span.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() + wrap the client** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Wrap multi-step orchestration; verify provider calls are not double-wrapped** → `references/4-spans-and-traces.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` runs once at startup. Import order does NOT matter — the helpers patch the client instance, so static imports of the LLM SDK are fine and no dynamic `import()` is needed.
- NEVER pass `instrumentations: [...]` to `init()` — it **throws** for every provider key. Wrap the client instead.
- Every provider client the code constructs must be wrapped; an unwrapped client is silently untraced.
- All lifecycle calls are async: `await init/flush/shutdown`.
- The wrapper captures the provider LLM call (input/output, model, tokens, latency) and auto-opens a WORKFLOW root if the call would be parentless. It is the canonical LLM span.
- NEVER put `trace({ kind:'LLM' })`, `span()`, or another provider/framework instrumentor around a single wrapped call. That creates redundant instrumentation. A WORKFLOW/CHAIN/AGENT span may enclose several wrapped calls to represent real orchestration.
- Use manual `trace({ kind:'LLM' })` only for a provider or raw HTTP call that no supported capture layer owns. Manual spans must record their own input, output, model, usage, and errors.
- Never hardcode API keys — use `process.env`.
- For managed Neatlogs, omit `endpoint`, `baseUrl`, and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print a concise, user-visible progress update before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager after editing. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes; hot reload is not proof that a newly-added startup file loaded. Exercise the actual instrumented route, action, or entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run and has one canonical span per operation, expected input/output, and no duplicate LLM spans. An offline verifier that disables export is not sufficient by itself.
- Do not report completion until every applicable check passes. If execution or ingestion cannot be verified, report the run as incomplete with the exact blocker and next command; never claim success from edits alone.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Custom span()/trace() deep dive → `references/decorators-and-traces.md`
- Sessions & end-users (per-turn `identify()`) → `references/sessions-and-end-users.md`
- Troubleshooting → `references/troubleshooting.md`
