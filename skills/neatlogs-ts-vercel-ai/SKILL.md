---
name: neatlogs-ts-vercel-ai
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses the Vercel AI SDK (depends on the `ai` package, calls `generateText`/`streamText`).
metadata:
  author: neatlogs
  language: typescript
  framework: vercel-ai
---

# Neatlogs TypeScript Setup — Vercel AI SDK (`ai`)

This project uses the Vercel AI SDK (`ai` package: `generateText`, `streamText`, `generateObject`, `streamObject`, `embed`, `embedMany`, `rerank`). Neatlogs instruments it with **`wrapAISDK(ai)` from `neatlogs/ai`** — NOT via an `instrumentations` list. The wrapper opts the AI SDK's native OpenTelemetry support in per call.

> **The legacy public instrumentations loader is unsupported.** The AI SDK instrumentor drives the global OpenTelemetry context, so `init()` rejects it and points to `wrapAISDK()`. Older no-op guidance is obsolete.

## Core mechanism (DIFFERENT from other skills)

1. `await init({ ... })` first (sets up Neatlogs' private tracer — never registered globally). Never pass the legacy instrumentations option; the wrapper does the work.
2. `const { generateText, streamText, ... } = wrapAISDK(ai)` — wrap the `ai` module.
3. Use the WRAPPED functions exactly like the originals. Each wrapped call auto-creates a WORKFLOW/CHAIN parent span + native `ai.doGenerate`/`doStream` LLM children + tool-call TOOL children.

## Steps

1. **Install** → `references/1-install.md`
2. **Add init() + wrapAISDK** → `references/2-init-and-wrap.md`
3. **Set environment variables** → `references/3-set-env.md`
4. **Verify: use wrapped fns, don't double-wrap** → `references/4-verify.md`
5. **Lifecycle (flush/shutdown)** → `references/5-lifecycle.md`

## Running inside Next.js? (most apps are)

If the project is a **Next.js** app (it has `next.config.*` / `app/` route handlers / server actions), follow **`references/nextjs.md`**. The key Next-specific requirement:
- `init()` goes in `instrumentation.ts` via the `register()` hook, importing neatlogs with a **dynamic** `await import("neatlogs")` — NOT a top-level import. A static import 500s the build with `Can't resolve 'crypto'`.

## Rules (apply to ALL steps)

- `await init(...)` runs first (registers the TracerProvider). Then `wrapAISDK(ai)`.
- Never pass the legacy instrumentations option (or any provider key); `init()` throws. The wrapper is the instrumentation. A provider SDK called directly outside the AI SDK needs its own helper (`wrapOpenAI`, `wrapAnthropic`, …).
- Replace direct `ai` calls with the WRAPPED equivalents: destructure `generateText`/`streamText`/etc. from `wrapAISDK(ai)` and call those. Don't leave bare `import { generateText } from 'ai'` call sites — they won't be traced.
- Do NOT also wrap wrapped calls in `span()`/`trace()` — the wrapper already opens the parent span. Add a `WORKFLOW` only when the application entry point owns a real multi-step request/job; keep each wrapped AI-SDK call as its canonical child.
- The AI SDK supports both v3–v6; `wrapAISDK` is version-agnostic.
- Never hardcode API keys — use `process.env`.
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
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and returned semantic fields, not only a trace-list summary or local debug output. Confirm the nonce-qualified project trace is the fresh run, with one canonical span per operation and no duplicate LLM/tool/agent spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- **Next.js setup (serverExternalPackages + instrumentation.ts)** → `references/nextjs.md`
- Sessions & end-users (per-turn `identify()`) → `references/sessions-and-end-users.md`
- Custom span()/trace() (for real app-owned request/job orchestration) → `references/decorators-and-traces.md`
- Troubleshooting → `references/troubleshooting.md`
