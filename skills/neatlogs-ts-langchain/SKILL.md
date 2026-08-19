---
name: neatlogs-ts-langchain
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses LangChain or LangGraph (depends on `@langchain/*` / `@langchain/langgraph`).
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
4. **Attach the handler; optionally add an app-owned WORKFLOW** → `references/4-add-workflow.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Rules (apply to ALL steps)

- `await init(...)` runs once at startup. Import order does NOT matter — the handler binds to Neatlogs' private provider per call, so a static `import` of `@langchain/*` is fine (no dynamic `import()` needed).
- NEVER pass `instrumentations: ['langchain']` to `init()` — it **throws**. The callback handler is the only path.
- Create ONE `langchainHandler()` and pass it via `{ callbacks: [handler] }`. For plain LangChain (LCEL chains / bare model calls) attach per model/chain call. For LangGraph attach at the graph invocation (`app.invoke(..., { callbacks: [handler] })`), NOT the per-node `llm.invoke()`.
- The handler self-roots a parentless supported run. Add at most one app-owned `span({ kind:'WORKFLOW' })` only when the user-facing entry performs meaningful pre/post work or coordinates multiple runs.
- NEVER wrap individual chains, graph nodes, LangChain tools, or `llm.invoke()` with `span()`/`trace()` — they are auto-traced by the handler; manual wrapping duplicates.
- All lifecycle calls are async. Never hardcode API keys — use `process.env`.
- For managed Neatlogs, omit `endpoint`, `baseUrl`, and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.

For the representative run, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries. Scope it only to the launched process: do not edit source or persistent configuration, and do not treat the marker as a secret. Immediately before exercising the real path, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.

After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; do not make preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes, then exercise the actual instrumented route/action/entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the marker-matched project trace is the fresh run, with one canonical span per operation and no duplicate LLM/chain/node/tool spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app.
- Custom span()/trace() (rare here) → `references/decorators-and-traces.md`
- Sessions & end-users (per-turn `identify()` wrapper-only) → `references/sessions-and-end-users.md`
- Troubleshooting → `references/troubleshooting.md`
