# Reference: Next.js apps (App Router / API routes)

The Vercel AI SDK is most often used inside a Next.js app (route handlers, server actions). The one Next-specific requirement is initializing neatlogs from `instrumentation.ts` with a **dynamic import** (Step 1 below). Everything else (init options, `wrapAISDK`, importing wrapped functions in routes) is the same as the generic steps.

## 1. `init()` in `instrumentation.ts` via the `register()` hook — use a DYNAMIC import (REQUIRED)

Next.js runs `register()` from `instrumentation.ts` (or `src/instrumentation.ts`) once at server startup — the correct place to call `init()`. Guard on the Node.js runtime so it doesn't run on edge.

**CRITICAL: import `neatlogs` dynamically *inside* `register()`, not at the top of the file.** A static top-level `import { init } from "neatlogs"` makes Next's instrumentation-layer bundler statically analyze the SDK and fail with `Can't resolve 'crypto'`. A dynamic `await import("neatlogs")` defers resolution to runtime, where `node:crypto` exists. (Verified: static import → build 500; dynamic import → works. This is exactly what the `gemini-chatbot` example does.)

```typescript
// src/instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    // Dynamic import — NOT a top-level `import { init } from "neatlogs"`.
    const { init, flush, shutdown } = await import("neatlogs");

    await init({
      apiKey: process.env.NEATLOGS_API_KEY ?? "",
      workflowName: "my-next-app",
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

On Next 13/14 also set `experimental.instrumentationHook: true` in `next.config` (on by default in 15+).

## 2. (Fallback) `serverExternalPackages` if a route still fails to bundle

The dynamic import in Step 1 is normally enough — route handlers only import the wrapped AI-SDK functions (`neatlogs/ai`), which bundle fine. If a specific route or server action statically imports the full `neatlogs` SDK and Next still errors with `Can't resolve 'crypto'`, mark it external:

```typescript
// next.config.ts
const nextConfig = { serverExternalPackages: ["neatlogs"] };          // Next 15+
// const nextConfig = { experimental: { serverComponentsExternalPackages: ["neatlogs"] } }; // Next 13–14
```

Not required for the standard setup (the `gemini-chatbot` example works without it).

## 3. Centralize `wrapAISDK` and import the wrapped fns in routes

Put the wrap in one module and import the wrapped functions from it in every route/server action — never bare `from "ai"`.

```typescript
// src/lib/neatlogs.ts
import { wrapAISDK } from "neatlogs/ai";
import * as ai from "ai";

export const { generateText, streamText, generateObject, streamObject, embed, embedMany } = wrapAISDK(ai);
```

```typescript
// src/app/api/chat/route.ts
import { streamText } from "@/lib/neatlogs";   // ✅ wrapped — NOT from "ai"

export async function POST(req: Request) {
  const { messages } = await req.json();
  const result = streamText({ model: getModel(), messages, tools: allTools });
  return result.toDataStreamResponse();
}
```

## Lifecycle in Next.js

Do NOT flush/shutdown per request — `init()` runs once in `register()`. The SIGTERM/SIGINT handlers in `instrumentation.ts` cover graceful shutdown. Each `streamText`/`generateText` call flushes its own span on completion.

## Verify
- [ ] `instrumentation.ts` calls `init()` inside `register()` under the `NEXT_RUNTIME === "nodejs"` guard, importing `neatlogs` via a DYNAMIC `await import("neatlogs")` (NOT a top-level import). ← the key requirement
- [ ] `experimental.instrumentationHook: true` in `next.config` (Next 13/14 only; default in 15+).
- [ ] Every route/server action imports AI SDK functions from the wrapped module, not `"ai"`.
- [ ] Server boots without `Can't resolve 'crypto'`; hitting a route produces spans. (If a route still errors, add `serverExternalPackages` per Step 2.)
