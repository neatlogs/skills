---
name: neatlogs-ts-mastra
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses the Mastra framework (depends on `@mastra/core`, builds a Mastra agent/workflow).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "3.0"
  language: typescript
  framework: mastra
---

# Neatlogs TypeScript Setup — Mastra

This project uses **Mastra** (`@mastra/core`). Neatlogs instruments it with **`wrapMastra()` from `neatlogs/mastra`** — you wrap each Mastra entity (agent, workflow, vector store, memory) once, and neatlogs captures the full nested trace tree.

## Core mechanism — `wrapMastra(entity)`

`wrapMastra` patches the entity's own methods and emits OpenTelemetry spans, owning the capturing layer (same philosophy as `wrapAISDK` for the Vercel AI SDK). It needs **no extra packages** (`@mastra/observability` / `@neatlogs/instrumentation-mastra` are NOT required) and works on **standalone entities** created with `new Agent({...})` — no root `Mastra` instance needed.

Wrapping an entity produces a full nested span tree:

| You wrap | Parent span | Nested children |
|----------|-------------|-----------------|
| `Agent` (`.generate()` / `.stream()`) | **AGENT** | **LLM** (each model step, incl. streaming `doStream`), **TOOL** (each tool `execute`) |
| `Workflow` (`.createRun().start()`) | **WORKFLOW** | step spans |
| `MastraVector` (`.query` / `.upsert`) | **RETRIEVER** (query) / **VECTOR_STORE** (writes) | — |
| `MastraMemory` (`.recall` / `.saveMessages` …) | **CHAIN** | — |
| root `Mastra` | proxy — wraps every agent/workflow it hands out | delegates |

Plus `wrapMastraRerank(rerank)` for the `@mastra/rag` `rerank()` function → **RERANKER** spans.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() + wrapMastra** → `references/2-init-and-wrap.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Verify: wrap every entity, don't double-wrap** → `references/4-verify.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` MUST run BEFORE any `import` of `@mastra/core` or the LLM provider SDKs. Use **dynamic `import()`** for them AFTER init.
- `wrapMastra` captures the LLM call itself (at the agent's resolved model), so you do NOT wrap providers separately — agents using `openai/…`, `anthropic/…`, `google/…`, or `bedrock/…` models all work with just `wrapMastra(agent)`. `instrumentations` is OPTIONAL for a pure-Mastra app: wrapMastra emits the full AGENT/LLM/TOOL tree even when it's omitted. Only add `instrumentations: ['<provider>']` if the same app ALSO calls a provider SDK DIRECTLY outside Mastra (e.g. a raw `openai.chat.completions.create()` helper) — that's the only thing the provider entry covers, and it never duplicates Mastra-routed spans.
- Call `wrapMastra()` on EACH entity you want traced (agent, workflow, vector store, memory) — or wrap the root `Mastra` instance once to cover all agents/workflows it exposes.
- USE the wrapped reference. `wrapMastra` patches in place AND returns the entity, so `const agent = wrapMastra(rawAgent)` then call `agent.generate(...)`.
- Tool definitions must use the Mastra 1.x signature `execute: async (inputData, context) => ...` — the input fields are on the FIRST argument. The old `({ context }) => ...` form is broken on `@mastra/core >= 1.0`.
- Do NOT manually wrap Mastra methods in `span()`/`trace()` on top of `wrapMastra` — that double-traces.
- All lifecycle calls are async: `await init()`, `await flush()`, `await shutdown()`.
- Never hardcode API keys — use `process.env`.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the Mastra app runs inside Next.js, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Full span coverage matrix (entities → kinds → attributes, multi-provider, streaming) → `references/span-coverage.md`
- Custom span()/trace() (only for non-Mastra code) → `references/decorators-and-traces.md`
