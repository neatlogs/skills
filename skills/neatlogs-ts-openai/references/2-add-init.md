# Step 2: Add init() — BEFORE the LLM SDK import

`await init()` MUST run before the LLM SDK is imported, so auto-instrumentation patches it at load time. Convert the LLM SDK import to a dynamic `import()` AFTER init.

```typescript
import "dotenv/config";
import { init } from "neatlogs";

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? "",
  workflowName: "my-app",
  instrumentations: ["openai"],   // or anthropic / google_genai / bedrock — from detect_stack
});

// LLM SDK imported AFTER init (dynamic) so the instrumentor patches it.
const { OpenAI } = await import("openai");
const client = new OpenAI();
```

## WRONG vs RIGHT (import order)

```typescript
// ❌ WRONG — static top import of the LLM SDK before init. Not patched.
import { OpenAI } from "openai";
await init({ instrumentations: ["openai"] });   // too late

// ✅ RIGHT — init first, dynamic import after.
await init({ instrumentations: ["openai"] });
const { OpenAI } = await import("openai");
```

## Top-level await
If the project isn't ESM/top-level-await friendly, do init inside an async bootstrap that runs before anything else, then dynamically import the modules that use the SDK.

## Do NOT pass endpoint= in code
Leave `endpoint` out of `init()` (SDK defaults to managed cloud). Local/self-hosted endpoints are set via `NEATLOGS_ENDPOINT` env for local testing only.

## Verify
1. `await init(...)` is the first thing after dotenv.
2. The LLM SDK is imported via `await import(...)` AFTER init, not at the top.
3. `instrumentations` lists the detected provider key.
