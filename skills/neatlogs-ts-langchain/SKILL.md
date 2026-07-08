---
name: neatlogs-ts-langchain
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses LangChain or LangGraph (depends on `@langchain/*` / `@langchain/langgraph`).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "3.0"
  language: typescript
  framework: langchain
---

# Neatlogs TypeScript Setup — LangChain / LangGraph

This project uses LangChain (`@langchain/*`) or LangGraph (`@langchain/langgraph`). Neatlogs offers **two ways** to instrument it:

1. **`langchainHandler()`** — a LangChain callback handler you attach per call via `{ callbacks: [handler] }`. This is the **recommended, first-class** path. This skill uses it throughout.
2. **`instrumentations: ['langchain']`** on `init()` — zero-touch auto-instrumentation that patches at import time. Use it when you can't thread a handler through your code.

Pick ONE — don't combine them (that double-traces). The rest of this skill shows the handler approach.

## Core mechanism — `langchainHandler()`

Create ONE handler and pass it via `{ callbacks: [handler] }` on the calls you want traced:

```typescript
import { init, langchainHandler, span, flush, shutdown } from 'neatlogs';

await init({ apiKey: process.env.NEATLOGS_API_KEY, workflowName: 'langchain-app' });

const { ChatOpenAI } = await import('@langchain/openai');
const llm = new ChatOpenAI({ model: 'gpt-4o' });

const handler = langchainHandler();
const res = await llm.invoke('Hello', { callbacks: [handler] });
```

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

- `await init(...)` MUST run BEFORE any `@langchain/*` import. Use dynamic `import()` AFTER init.
- This skill uses the **callback handler**; do NOT ALSO pass `instrumentations: ['langchain']` to `init()` — running both double-traces.
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
