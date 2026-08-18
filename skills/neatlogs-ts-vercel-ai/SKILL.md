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

> **`init({ instrumentations: ['ai_sdk'] })` throws** — as does every other provider/framework key. The registry's `ai_sdk` instrumentor drives the **global** OpenTelemetry context, which Neatlogs' private provider cannot isolate from a co-tenant tracer (Datadog, etc.), so `init()` rejects the key with a message pointing at `wrapAISDK()`. Older guidance called it a harmless no-op — it is not.

## Core mechanism (DIFFERENT from other skills)

1. `await init({ ... })` first (sets up Neatlogs' private tracer — never registered globally). **Never pass `instrumentations: ['ai_sdk']` — `init()` throws for it; the wrapper does the work.**
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
- NEVER pass `instrumentations: ['ai_sdk']` (or any provider key) — `init()` **throws**. The wrapper is the instrumentation. A provider SDK called DIRECTLY outside the AI SDK needs its own helper (`wrapOpenAI`, `wrapAnthropic`, …).
- Replace direct `ai` calls with the WRAPPED equivalents: destructure `generateText`/`streamText`/etc. from `wrapAISDK(ai)` and call those. Don't leave bare `import { generateText } from 'ai'` call sites — they won't be traced.
- Do NOT also wrap wrapped calls in `span()`/`trace()` — the wrapper already opens the parent span. Add a `WORKFLOW` only when the application entry point owns a real multi-step request/job; keep each wrapped AI-SDK call as its canonical child.
- The AI SDK supports both v3–v6; `wrapAISDK` is version-agnostic.
- Never hardcode API keys — use `process.env`.
- For managed Neatlogs, omit `endpoint`, `baseUrl`, and `NEATLOGS_ENDPOINT`; the SDK already uses `https://ingest.neatlogs.com`.

## Live completion gate (wizard or standalone coding agent)

This skill does not grant platform access. Immediately before exercising the real path, record the current UTC timestamp. After the run, call the already-connected Neatlogs platform MCP's existing `get_trace_context(created_after=<UTC timestamp>)` directly to select the latest trace in the intended project; do not make preliminary MCP discovery calls. While its `status` is `processing` or `finalization_status` is `pending`, poll that same trace with `get_trace_context(trace_id=<trace_id>)`. Once finalized, page with `get_trace_context(trace_id=<trace_id>, offset=<next_offset>)` until `next_offset` is null, and verify that all `span_count` spans were inspected. If MCP is unavailable, ask the user to configure `https://ingest.neatlogs.com/mcp` with the project key stored as a client secret; never print or request the key in chat, and leave verification incomplete.

- Print concise user-visible progress before and after install, code changes, build, restart, runtime verification, and platform confirmation. Never print secrets.
- Run the project's existing build/typecheck/test commands with its detected package manager. Source inspection alone is not verification.
- For servers and startup hooks, build and start a fresh process after instrumentation changes, then exercise the actual instrumented route/action/entry point.
- Run a safe bounded verification through the real instrumented entry point. Inspect the full persisted span tree and attributes, not only a trace-list summary or local debug output. Confirm the latest project trace is the fresh run, with one canonical span per operation and no duplicate LLM/tool/agent spans. An offline/no-export verifier is insufficient by itself.
- Do not claim completion until all applicable checks pass. If runtime or ingestion cannot be confirmed, report the exact blocker and leave the result incomplete.

## Reference

- **Next.js setup (serverExternalPackages + instrumentation.ts)** → `references/nextjs.md`
- Sessions & end-users (per-turn `identify()`) → `references/sessions-and-end-users.md`
- Custom span()/trace() (for real app-owned request/job orchestration) → `references/decorators-and-traces.md`
- Troubleshooting → `references/troubleshooting.md`
