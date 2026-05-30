# Reference: Next.js apps (App Router / API routes)

If this project is a Next.js app, the key Next-specific requirement is initializing neatlogs from `instrumentation.ts` with a **dynamic import** (Step 1). Skipping it produces a 500 with `Module not found: Can't resolve 'crypto'` and NO traces.

## 1. `init()` in `instrumentation.ts` via the `register()` hook — use a DYNAMIC import (REQUIRED)

Next.js runs `register()` once at server startup — the right place for `init()`. It must run before LangChain loads, so import `@langchain/*` dynamically in your route handlers (they already load per-request, which is after `register()`).

**CRITICAL: import `neatlogs` dynamically *inside* `register()`, not at the top of the file.** A static top-level `import { init } from "neatlogs"` makes Next's instrumentation-layer bundler fail with `Can't resolve 'crypto'`, and `serverExternalPackages` does NOT cover the `instrumentation.ts` compilation. A dynamic `await import("neatlogs")` defers resolution to runtime.

```typescript
// src/instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { init, flush, shutdown } = await import("neatlogs"); // dynamic, not top-level

    await init({
      apiKey: process.env.NEATLOGS_API_KEY ?? "",
      workflowName: "my-next-app",
      instrumentations: ["langchain"],
    });

    const gracefulShutdown = async () => {
      await flush();
      await shutdown();
      process.exit(0);
    };
    process.on("SIGTERM", gracefulShutdown);
    process.on("SIGINT", gracefulShutdown);
  }
}
```

On Next 13/14 also set `experimental.instrumentationHook: true` (on by default in 15+).

## 2. (Fallback) `serverExternalPackages` if a route still fails to bundle

The dynamic import above is normally enough. If a route/server action statically imports the full `neatlogs` SDK and Next still errors with `Can't resolve 'crypto'`, mark it external:

```typescript
const nextConfig = { serverExternalPackages: ["neatlogs"] };          // Next 15+
// const nextConfig = { experimental: { serverComponentsExternalPackages: ["neatlogs"] } }; // 13–14
```

## Lifecycle in Next.js

`init()` runs once in `register()`; do NOT flush/shutdown per request. The SIGTERM/SIGINT handlers cover graceful shutdown.

## Verify
- [ ] `instrumentation.ts` calls `init()` inside `register()` under the `NEXT_RUNTIME === "nodejs"` guard, importing `neatlogs` via DYNAMIC `await import("neatlogs")` (NOT top-level), with `instrumentations: ["langchain"]`. ← the key requirement
- [ ] Server boots without `Can't resolve 'crypto'`; invoking a chain produces spans. (If a route still errors, add `serverExternalPackages` per Step 2.)
