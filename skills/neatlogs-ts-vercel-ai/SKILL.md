---
name: neatlogs-ts-vercel-ai
description: Use when adding neatlogs observability to a TypeScript/Node.js project that uses the Vercel AI SDK (depends on the `ai` package, calls `generateText`/`streamText`).
compatibility: Neatlogs Wizard Agent
metadata:
  author: neatlogs
  version: "2.0"
  language: typescript
  framework: vercel-ai
---

# Neatlogs TypeScript Setup — Vercel AI SDK (`ai`)

This project uses the Vercel AI SDK (`ai` package: `generateText`, `streamText`, `generateObject`, `streamObject`, `embed`, `embedMany`, `rerank`). Neatlogs instruments it with **`wrapAISDK(ai)` from `neatlogs/ai`** — NOT via an `instrumentations` list. The wrapper opts the AI SDK's native OpenTelemetry support in per call.

## Core mechanism (DIFFERENT from other skills)

1. `await init({ ... })` first (registers the global tracer). **No `instrumentations: ['ai_sdk']` needed — that key is a no-op; the wrapper does the work.**
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
- Do NOT pass `instrumentations: ['ai_sdk']` — it's a no-op. The wrapper is the instrumentation.
- Replace direct `ai` calls with the WRAPPED equivalents: destructure `generateText`/`streamText`/etc. from `wrapAISDK(ai)` and call those. Don't leave bare `import { generateText } from 'ai'` call sites — they won't be traced.
- Do NOT also wrap wrapped calls in `span()`/`trace()` — the wrapper already opens the parent span. (A `span()` WORKFLOW is fine to group multiple AI-SDK calls under one trace, but never wrap a single wrapped call.)
- The AI SDK supports both v3–v6; `wrapAISDK` is version-agnostic.
- Never hardcode API keys — use `process.env`.

## Reference

- **Next.js setup (serverExternalPackages + instrumentation.ts)** → `references/nextjs.md`
- Custom span()/trace() (for grouping) → `references/decorators-and-traces.md`
- Troubleshooting → `references/troubleshooting.md`
