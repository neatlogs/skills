---
name: neatlogs-ts-mastra
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses the Mastra framework (depends on `@mastra/core`, builds a Mastra agent/workflow).
metadata:
  author: neatlogs
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
- `wrapMastra` captures the LLM call itself (at the agent's resolved model), so you do NOT wrap providers separately — agents using `openai/…`, `anthropic/…`, `google/…`, or `bedrock/…` models all work with just `wrapMastra(agent)`. NEVER pass `instrumentations: [...]` — `init()` **throws** for `'mastra'` and for every provider key. If the same app ALSO calls a provider SDK DIRECTLY outside Mastra (e.g. a raw `openai.chat.completions.create()` helper), wrap that client explicitly with `wrapOpenAI(new OpenAI())`; it never duplicates Mastra-routed spans.
- Call `wrapMastra()` on EACH entity you want traced (agent, workflow, vector store, memory) — or wrap the root `Mastra` instance once to cover all agents/workflows it exposes.
- USE the wrapped reference. `wrapMastra` patches in place AND returns the entity, so `const agent = wrapMastra(rawAgent)` then call `agent.generate(...)`.
- Tool definitions must use the Mastra 1.x signature `execute: async (inputData, context) => ...` — the input fields are on the FIRST argument. The old `({ context }) => ...` form is broken on `@mastra/core >= 1.0`.
- Do NOT manually wrap Mastra methods in `span()`/`trace()` on top of `wrapMastra` — that double-traces.
- All lifecycle calls are async: `await init()`, `await flush()`, `await shutdown()`.
- Never hardcode API keys — use `process.env`.
- For managed Neatlogs, omit `endpoint`, `baseUrl`, and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend; a merged backend change or updated local wizard alone is not proof.

For the representative run, generate a UUID and append `neatlogs.verification.marker=<UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries. Scope it only to the launched process: do not edit source or persistent configuration, and do not treat the marker as a secret. Immediately before exercising the real path, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with that temporary environment value, then continue verification against the same marker.

After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(verification_marker=<same UUID>)` directly; do not make preliminary MCP discovery calls and never fall back to the latest trace if the marker is absent; report that exact blocker and leave verification incomplete. While `status` is `processing` or `finalization_status` is `pending`, poll the same trace with `get_trace_context(trace_id=<trace_id>)`. Only after `finalization_status` is `finalized`, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `trace_id`, or `offset`, or omits `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes, then exercise the actual instrumented route/action/entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the marker-matched project trace is the fresh run, with one canonical span per operation and no duplicate LLM/tool/agent spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the Mastra app runs inside Next.js, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Full span coverage matrix (entities → kinds → attributes, multi-provider, streaming) → `references/span-coverage.md`
- Custom span()/trace() (only for non-Mastra code) → `references/decorators-and-traces.md`
- Sessions & end-users (wrapper-only `identify()` per turn) → `references/sessions-and-end-users.md`
