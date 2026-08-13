---
name: neatlogs-ts-langchain
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses LangChain or LangGraph (depends on `@langchain/*` / `@langchain/langgraph`).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  language: typescript
  framework: langchain
---

# Neatlogs TypeScript Setup — LangChain / LangGraph

This project uses LangChain (`@langchain/*`) or LangGraph (`@langchain/langgraph`). Neatlogs instruments it with **`langchainHandler()`** — a LangChain callback handler you attach via `{ callbacks: [handler] }`. This is the **only** supported path.

> **`init({ instrumentations: ['langchain'] })` throws.** The OpenInference LangChain instrumentor creates and activates spans on the **global** OpenTelemetry context, which Neatlogs' private provider cannot isolate from a co-tenant tracer (Datadog, etc.), so `init()` rejects the key outright with a message pointing at `langchainHandler()`. Older guidance offered it as a zero-touch alternative — that is gone.

## Core mechanism — `langchainHandler()`

Create ONE handler and pass it via `{ callbacks: [handler] }` on the calls you want traced:

```typescript
import { init, langchainHandler, span, flush, shutdown } from 'neatlogs';
import { ChatOpenAI } from '@langchain/openai';

await init({ apiKey: process.env.NEATLOGS_API_KEY, workflowName: 'langchain-app' });

const llm = new ChatOpenAI({ model: 'gpt-4o' });

const handler = langchainHandler();
const res = await llm.invoke('Hello', { callbacks: [handler] });
```

The handler is bound to Neatlogs' private provider, so import order doesn't matter — a static `import` of `@langchain/*` above `init()` is fine.

### LangGraph: attach at the GRAPH invocation — NOT the per-node model call

For LangGraph, attach the handler at the **graph invocation** (`app.invoke(...)` / `stream` / etc.), not on the per-node `llm.invoke()`. LangGraph fires the per-node `on_chain_start` only on the **graph-level callback manager**, so a handler passed to a single node's model call never sees the node boundaries — you get no node spans and the LLM span orphans to the workflow root (flat, no node hierarchy). Attach once at the graph invocation and each node gets its own span with the LLM nested under it.

```typescript
async function analystNode(state) {
  const response = await llm.invoke(messages);                   // no per-node handler
  return { messages: [response] };
}
// ✅ attach at the graph invocation — nodes + nested LLMs all get spans
await app.invoke(state, { callbacks: [handler] });               // graph level ✅
// NOT: await llm.invoke(messages, { callbacks: [handler] });    // per-node ❌ (no node spans, LLM orphans)
```

(Plain LangChain — LCEL chains / bare `llm.invoke()` — is the opposite: attach per model/chain call as in the example above. The graph-level rule is LangGraph-specific.)

## What the handler captures (DO NOT manually wrap)

- Chat-model / LLM calls → LLM span (model, tokens, latency)
- Chain / node execution → CHAIN span
- LangChain tools → TOOL span
- Retrievers → RETRIEVER span

## Steps

1. **Install** → `references/1-install.md`
2. **Add init()** → `references/2-add-init.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Add the WORKFLOW span + attach handler** → `references/4-add-workflow.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` runs once at startup. Import order does NOT matter — the handler binds to Neatlogs' private provider per call, so a static `import` of `@langchain/*` is fine (no dynamic `import()` needed).
- NEVER pass `instrumentations: ['langchain']` to `init()` — it **throws**. The callback handler is the only path.
- Create ONE `langchainHandler()` and pass it via `{ callbacks: [handler] }`. For plain LangChain (LCEL chains / bare model calls) attach per model/chain call. For LangGraph attach at the graph invocation (`app.invoke(..., { callbacks: [handler] })`), NOT the per-node `llm.invoke()`.
- The ONLY manual span you add is `span({ kind:'WORKFLOW' })` on the user-facing entry that runs the chain/graph/agent.
- NEVER wrap individual chains, graph nodes, LangChain tools, or `llm.invoke()` with `span()`/`trace()` — they are auto-traced by the handler; manual wrapping duplicates.
- All lifecycle calls are async. Never hardcode API keys — use `process.env`.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app.
- Custom span()/trace() (rare here) → `references/decorators-and-traces.md`
- Sessions & end-users (per-turn `identify()` wrapper-only) → `references/sessions-and-end-users.md`
- Prompt templates → `references/prompt-templates.md`
- Troubleshooting → `references/troubleshooting.md`
