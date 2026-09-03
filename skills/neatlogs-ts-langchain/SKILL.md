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

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run, generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes, then exercise the actual instrumented route/action/entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one canonical span per operation and no duplicate LLM/chain/node/tool spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the project is a Next.js app.
- Custom span()/trace() (rare here) → `references/decorators-and-traces.md`
- Sessions & end-users (per-turn `identify()` wrapper-only) → `references/sessions-and-end-users.md`
- Troubleshooting → `references/troubleshooting.md`
