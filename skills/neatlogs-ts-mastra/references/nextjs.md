# Reference: Next.js apps (App Router / API routes)

If the Mastra app runs inside Next.js, the critical Next-specific requirement is initializing neatlogs from `instrumentation.ts` with a **dynamic import** (Step 1). Skipping it produces a 500 with `Module not found: Can't resolve 'crypto'` and NO traces.

## 1. `init()` + `wrapMastra` wiring (dynamic import is REQUIRED)

`init()` must run before `@mastra/core` loads. Two common layouts:

**a) init in `instrumentation.ts`, wrap at the agent module:**

**CRITICAL: import `neatlogs` dynamically inside `register()`, not at the top.** A static top-level import makes Next's instrumentation-layer bundler fail with `Can't resolve 'crypto'` (and `serverExternalPackages` does not cover `instrumentation.ts`). Use `await import("neatlogs")`.

```typescript
// src/instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { init, flush, shutdown } = await import("neatlogs"); // dynamic, not top-level
    await init({ apiKey: process.env.NEATLOGS_API_KEY ?? "", workflowName: "my-next-app" });
    const g = async () => { await flush(); await shutdown(); process.exit(0); };
    process.on("SIGTERM", g); process.on("SIGINT", g);
  }
}
```
```typescript
// src/lib/agent.ts — wrap the agent where it's defined/exported
import { wrapMastra } from "neatlogs/mastra";
import { Agent } from "@mastra/core/agent";
export const agent = wrapMastra(new Agent({ id: "pm", name: "PM", instructions: "...", model: "openai/gpt-4o-mini" }));
```
```typescript
// src/app/api/chat/route.ts
import { agent } from "@/lib/agent";   // already wrapped
export async function POST(req: Request) {
  const { prompt } = await req.json();
  const res = await agent.generate(prompt);
  return Response.json({ text: res.text });
}
```

On Next 13/14 also set `experimental.instrumentationHook: true` (on by default in 15+).

## 2. `serverExternalPackages` for `@mastra/core` (recommended)

The dynamic import in Step 1 fixes the `instrumentation.ts` crypto error. Separately, route handlers import `@mastra/core` (heavy, Node-only) — keep it out of the Next bundle:

```typescript
const nextConfig = { serverExternalPackages: ["@mastra/core", "neatlogs"] };          // Next 15+
// const nextConfig = { experimental: { serverComponentsExternalPackages: ["@mastra/core", "neatlogs"] } }; // 13–14
```

## Lifecycle in Next.js

`init()` runs once in `register()`; do NOT flush/shutdown per request. The SIGTERM/SIGINT handlers cover graceful shutdown.

## Verify
- [ ] `init()` runs in `register()` under the `NEXT_RUNTIME === "nodejs"` guard, importing `neatlogs` via DYNAMIC `await import("neatlogs")` (NOT top-level). ← the key crypto fix
- [ ] `next.config` lists `@mastra/core` (and `neatlogs`) in `serverExternalPackages` so routes bundle.
- [ ] Each agent/workflow used in a route is `wrapMastra()`-wrapped and the wrapped reference is imported.
- [ ] Server boots without `Can't resolve 'crypto'`; hitting a route produces AGENT/LLM/TOOL spans.
