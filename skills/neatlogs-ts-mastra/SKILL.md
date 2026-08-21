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

## Doctor gate

Before editing, run this read-only preflight from the application root:

```bash
npx --yes @neatlogs/wizard@latest doctor --local --json --install-dir .
```

Require `doctor_version: 1` and `schema_version: 2`. Treat `application_exercised: false` and `capture_scope: "wizard_sdk_fixture"` literally: local doctor validates static target configuration plus the wizard's normalized in-memory SDK fixture; it is not proof that this application's runtime or the backend worked.

Only remediate a failed check when `fixable: true`: `INSTRUMENTOR_NOT_ACTIVE` means install/initialize using this skill; `ATTRIBUTE_CONFLICT` means apply only the conflict named in the check; `MISSING_API_KEY` means configure the key through the user's secret/environment mechanism, never source or chat. Do not edit for any other code or for warnings such as `PROJECT_OWNERSHIP_AMBIGUOUS`; report the exact check instead.

After the project checks/build and a real-path exercise, run `npx --yes @neatlogs/wizard@latest doctor --probe --json --install-dir .` with `NEATLOGS_API_KEY` supplied through the process environment. If it returns `BACKEND_DIAGNOSTIC_UNAVAILABLE`, no probe was sent: report that deployment blocker and leave diagnostic-stage verification incomplete. Never substitute a local span log, package installation, or an uncorrelated latest trace for doctor/backend evidence. The marker-correlated platform completion gate below remains a separate persistence check.

+## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. The marker-aware `get_trace_context` contract must be deployed on the hosted Neatlogs backend, and the installed SDK or exporter must preserve the resource marker; merged source changes or an updated local wizard alone are not proof.

For the representative run, generate two distinct UUIDs: a process marker and an exercise nonce. Append `neatlogs.verification.marker=<marker UUID>` to `OTEL_RESOURCE_ATTRIBUTES`, preserving existing entries and scoping it only to the launched process; do not edit source or persistent configuration, and do not treat either value as a secret. Put the exact token `neatlogs-verification:<nonce UUID>` in a safe representative user request, prompt, or API argument that exercises the real path and should be captured in a persisted span `input_value`. Immediately before the exercise, record the current UTC timestamp. If the coding agent cannot launch a web UI path, tell the user exactly how to start the app with the temporary marker and which nonce token to submit. If the path cannot safely carry a unique captured input, report that blocker and leave verification incomplete.

After the exercised request finishes, flush telemetry and gracefully stop the marked process or relaunch it without the marker before discovery. If marked trace production cannot be quiesced, leave verification incomplete. Then call the already-connected Neatlogs platform MCP with `get_trace_context(verification_marker=<marker UUID>, candidate_offset=0)`. Enumerate offsets from 0 upward, collecting distinct trace IDs until MCP returns `No project trace found` for the next offset. For every candidate, page its complete span set with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null. A candidate qualifies only when the exact nonce token appears in a persisted span `input_value`, its top-level `name` and `workflow` plus parentless root span match the exercised path, its `created_at` is not earlier than the recorded timestamp, `root_span_count` is 1, and no span has `synthetic_recovery_root: true`. Never select the first or latest marker match. If no trace qualifies yet, poll every 5 seconds and repeat the full enumeration for up to 2 minutes. Restart a scan if offsets shift and duplicate a trace ID; if a complete distinct scan cannot be obtained, offset 100 still returns a candidate, or zero or multiple traces qualify, report the ambiguity and leave verification incomplete.

Once exactly one trace qualifies, poll that exact `trace_id` every 5 seconds for up to 2 minutes while `status` is `processing` or `finalization_status` is `pending`. If it does not reach `finalized` within that bound, leave verification incomplete. Treat a null or unrecognized `finalization_status` as a hosted-contract blocker. After `finalization_status` is `finalized`, require `trace_context_contract_version: 2`, `verification_ready: true`, `span_payload_complete: true`, `span_tree_complete: true`, and `root_span_count: 1`; otherwise report a hosted-contract or incomplete-payload blocker. Page all spans again and perform two identical full marker-candidate enumerations at least 10 seconds apart to confirm that exactly one trace contains the nonce in both scans. Verify that all `span_count` spans were inspected.

If `get_trace_context` rejects `verification_marker`, `candidate_offset`, `trace_id`, or `offset`, or omits `trace_context_contract_version`, `verification_ready`, `span_payload_complete`, `span_tree_complete`, `root_span_count`, `trace_id`, `name`, `workflow`, `created_at`, `spans[].parent_span_id`, `spans[].input_value`, `status`, `finalization_status`, `next_offset`, or `span_count`, treat the hosted MCP as an old contract: stop, report the hosted deployment blocker, and do not claim verification or use another trace query. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes, then exercise the actual instrumented route/action/entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one canonical span per operation and no duplicate LLM/tool/agent spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- **Next.js setup (init via dynamic import in instrumentation.ts)** → `references/nextjs.md` — REQUIRED if the Mastra app runs inside Next.js, else the server 500s with `Can't resolve 'crypto'` and emits no traces.
- Full span coverage matrix (entities → kinds → attributes, multi-provider, streaming) → `references/span-coverage.md`
- Custom span()/trace() (only for non-Mastra code) → `references/decorators-and-traces.md`
- Sessions & end-users (wrapper-only `identify()` per turn) → `references/sessions-and-end-users.md`
