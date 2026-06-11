# Step 2: Add init() — BEFORE the LangChain import

`await init()` MUST run before any `@langchain/*` module is imported, so the langchain instrumentor patches at load time. Convert LangChain imports to dynamic `import()` AFTER init.

```typescript
import "dotenv/config";
import { init } from "neatlogs";

await init({
  apiKey: process.env.NEATLOGS_API_KEY ?? "",
  workflowName: "langchain-app",
  instrumentations: ["langchain"],   // covers LangChain + LangGraph
});

// LangChain modules imported AFTER init (dynamic) so they're patched.
const { ChatOpenAI } = await import("@langchain/openai");
const llm = new ChatOpenAI({ model: "gpt-4o" });
```

## WRONG vs RIGHT

```typescript
// ❌ WRONG — static @langchain import before init.
import { ChatOpenAI } from "@langchain/openai";
await init({ instrumentations: ["langchain"] });   // too late

// ✅ RIGHT — init first, dynamic import after.
await init({ instrumentations: ["langchain"] });
const { ChatOpenAI } = await import("@langchain/openai");
```

## Do NOT pass endpoint= in code
Leave `endpoint` out of `init()` — the SDK defaults to the managed cloud. (Only pass `endpoint` for a self-hosted backend.)

## Verify
1. `await init(...)` runs before any `@langchain/*` import.
2. LangChain modules use `await import(...)` after init.
3. `instrumentations: ['langchain']` present.
